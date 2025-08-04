#!/usr/bin/env python3
"""
Main ingestion pipeline script
Orchestrates the complete document processing and graph loading workflow
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

import logging
import json
from dotenv import load_dotenv
import boto3
from neo4j import GraphDatabase
from openai import OpenAI

from src.ingestion.pdf_parser import S3DocumentIngester
from src.ingestion.knowledge_extractor import KnowledgeExtractor, DocumentProcessor
from src.ingestion.graph_loader import GraphSchemaManager, Neo4jBulkLoader, CSVExporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the complete ingestion pipeline"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize clients
    logger.info("Initializing clients...")
    
    # S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
    
    # OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Neo4j driver
    neo4j_driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    try:
        # Step 1: Extract documents from S3
        logger.info("Step 1: Extracting documents from S3...")
        ingester = S3DocumentIngester(
            s3_client=s3_client,
            bucket_name=os.getenv('AWS_BUCKET_NAME')
        )
        
        extracted_docs = ingester.ingest_all_documents()
        logger.info(f"Extracted {len(extracted_docs)} documents")
        
        # Save extracted documents
        data_dir = Path(__file__).parent.parent / "data"
        raw_dir = data_dir / "raw"
        processed_dir = data_dir / "processed"
        
        ingester.save_extracted_documents(extracted_docs, raw_dir)
        
        # Step 2: Extract knowledge using LLM
        logger.info("Step 2: Extracting knowledge using LLM...")
        extractor = KnowledgeExtractor(openai_client)
        processor = DocumentProcessor(extractor)
        
        knowledge_data = []
        for i, doc in enumerate(extracted_docs):
            logger.info(f"Processing document {i+1}/{len(extracted_docs)}: {doc.filename}")
            
            # Convert to dict for processing
            doc_dict = doc.to_dict()
            
            # Extract knowledge
            knowledge = processor.process_document(doc_dict)
            knowledge_data.append(knowledge)
            
            # Save processed knowledge
            output_file = processed_dir / f"{doc.filename}_knowledge.json"
            with open(output_file, 'w') as f:
                json.dump(knowledge, f, indent=2)
        
        # Step 3: Create graph schema
        logger.info("Step 3: Creating graph schema...")
        schema_manager = GraphSchemaManager(neo4j_driver)
        schema_manager.create_schema()
        
        # Step 4: Load data into Neo4j
        logger.info("Step 4: Loading data into Neo4j...")
        loader = Neo4jBulkLoader(neo4j_driver)
        
        # Collect all entities and relationships
        all_entities = []
        all_relationships = []
        
        for doc_knowledge in knowledge_data:
            all_entities.extend(doc_knowledge.get('entities', []))
            all_relationships.extend(doc_knowledge.get('relationships', []))
        
        # Load entities
        logger.info(f"Loading {len(all_entities)} entities...")
        loader.load_entities(all_entities)
        
        # Load relationships
        logger.info(f"Loading {len(all_relationships)} relationships...")
        loader.load_relationships(all_relationships)
        
        # Step 5: Export to CSV for bulk import (optional)
        logger.info("Step 5: Exporting to CSV format...")
        csv_dir = data_dir / "csv_export"
        exporter = CSVExporter(csv_dir)
        exporter.export_to_csv(knowledge_data)
        
        logger.info("Ingestion pipeline completed successfully!")
        
        # Print summary statistics
        with neo4j_driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            
            logger.info(f"Graph statistics:")
            logger.info(f"  Total nodes: {node_count}")
            logger.info(f"  Total relationships: {rel_count}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    main()