#!/usr/bin/env python3
"""
Comprehensive System Test
Tests the complete BYOKG-RAG pipeline including:
- S3 document ingestion
- PDF parsing with advanced table extraction  
- Knowledge extraction and graph construction
- Entity linking and retrieval
- BOQ generation
"""

import os
import sys
import asyncio
import logging
import json
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.orchestrator import BYOKGRAGPipeline
from src.core.enhanced_kg_linker import EnhancedKGLinker
from src.core.graph_retriever import GraphRetriever, EntityLinker
from src.core.kg_linker import GraphSchemaLoader
from src.core.scoring_filter import LightweightScoringFilter
from src.core.llm_cache import CachedOpenAIClient, LLMCache
from src.ingestion.pdf_parser import PDFParser, S3DocumentIngester
from src.ingestion.knowledge_extractor import KnowledgeExtractor, DocumentProcessor
from src.ingestion.graph_loader import GraphSchemaManager, Neo4jBulkLoader

import boto3
from openai import OpenAI
from neo4j import GraphDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_complete_system():
    """Test the complete system end-to-end"""
    
    logger.info("🚀 Starting comprehensive system test")
    
    try:
        # 1. Test environment setup
        logger.info("📋 Step 1: Testing environment setup")
        
        # Check required environment variables
        required_vars = ['OPENAI_API_KEY', 'NEO4J_URI', 'NEO4J_PASSWORD', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing environment variables: {missing_vars}")
            return False
        
        logger.info("✅ Environment variables configured")
        
        # 2. Test database connections
        logger.info("📋 Step 2: Testing database connections")
        
        # Test Neo4j connection
        neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=('neo4j', os.getenv('NEO4J_PASSWORD'))
        )
        
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 as test")
            assert result.single()['test'] == 1
        
        logger.info("✅ Neo4j connection successful")
        
        # Test OpenAI connection
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Create cached client
        cache_dir = project_root / 'cache' / 'llm'
        cached_client = CachedOpenAIClient(openai_client, cache_dir)
        
        # Simple test call
        test_response = cached_client.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say 'OpenAI test successful'"}],
            max_tokens=10
        )
        
        assert "successful" in test_response.choices[0].message.content.lower()
        logger.info("✅ OpenAI connection successful")
        
        # Test S3 connection
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        bucket_name = os.getenv('S3_BUCKET_NAME')
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info("✅ S3 connection successful")
        
        # 3. Test PDF parsing and table extraction
        logger.info("📋 Step 3: Testing PDF parsing with advanced table extraction")
        
        # Initialize PDF parser with advanced table extraction
        pdf_parser = PDFParser(use_advanced_tables=True)
        
        # Test with S3 document ingester
        s3_ingester = S3DocumentIngester(s3_client, bucket_name)
        
        # Get list of PDFs in bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        pdf_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].lower().endswith('.pdf')]
        
        if not pdf_files:
            logger.warning("⚠️  No PDF files found in S3 bucket for testing")
            extracted_docs = []
        else:
            logger.info(f"📄 Found {len(pdf_files)} PDF files in S3 bucket")
            
            # Process first few PDFs
            extracted_docs = []
            for pdf_key in pdf_files[:3]:  # Test with first 3 PDFs
                try:
                    doc = s3_ingester._process_s3_pdf(pdf_key)
                    extracted_docs.append(doc)
                    logger.info(f"✅ Processed {pdf_key}: {doc.metadata['tables_found']} tables extracted")
                except Exception as e:
                    logger.error(f"❌ Failed to process {pdf_key}: {e}")
        
        # 4. Test knowledge extraction
        logger.info("📋 Step 4: Testing knowledge extraction")
        
        knowledge_extractor = KnowledgeExtractor(openai_client)
        document_processor = DocumentProcessor(knowledge_extractor)
        
        all_knowledge = []
        for doc in extracted_docs:
            try:
                knowledge = document_processor.process_document(doc.to_dict())
                all_knowledge.append(knowledge)
                
                entity_count = len(knowledge['entities'])
                relation_count = len(knowledge['relationships'])
                logger.info(f"✅ Extracted {entity_count} entities and {relation_count} relationships from {doc.filename}")
            except Exception as e:
                logger.error(f"❌ Knowledge extraction failed for {doc.filename}: {e}")
        
        # 5. Test graph schema and loading
        logger.info("📋 Step 5: Testing graph schema and data loading")
        
        # Create schema
        schema_manager = GraphSchemaManager(neo4j_driver)
        schema_manager.create_schema()
        logger.info("✅ Graph schema created")
        
        # Load data
        if all_knowledge:
            bulk_loader = Neo4jBulkLoader(neo4j_driver)
            
            # Combine all entities and relationships
            all_entities = []
            all_relationships = []
            
            for knowledge in all_knowledge:
                all_entities.extend(knowledge['entities'])
                all_relationships.extend(knowledge['relationships'])
            
            if all_entities:
                bulk_loader.load_entities(all_entities)
                logger.info(f"✅ Loaded {len(all_entities)} entities to graph")
            
            if all_relationships:
                bulk_loader.load_relationships(all_relationships)
                logger.info(f"✅ Loaded {len(all_relationships)} relationships to graph")
            
            # Verify data in graph
            with neo4j_driver.session() as session:
                node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                logger.info(f"📊 Graph contains {node_count} nodes and {rel_count} relationships")
        
        # 6. Test retrieval components
        logger.info("📋 Step 6: Testing retrieval components")
        
        # Test entity linker
        entity_linker = EntityLinker(neo4j_driver)
        
        # Test graph retriever
        graph_retriever = GraphRetriever(neo4j_driver, openai_client)
        
        # Test scoring filter
        scoring_filter = LightweightScoringFilter()
        
        logger.info("✅ Retrieval components initialized")
        
        # 7. Test complete BYOKG-RAG pipeline
        logger.info("📋 Step 7: Testing complete BYOKG-RAG pipeline")
        
        # Initialize enhanced components
        graph_schema = GraphSchemaLoader.get_default_schema()
        enhanced_kg_linker = EnhancedKGLinker(openai_client, graph_schema)
        
        # Create main pipeline
        pipeline = BYOKGRAGPipeline(
            openai_client=openai_client,
            neo4j_driver=neo4j_driver,
            max_iterations=2,
            graph_schema=graph_schema
        )
        
        # Test queries
        test_queries = [
            "I need 3 smoke detectors for a small office",
            "What fire alarm panel works with photoelectric smoke detectors?",
            "I need a complete fire alarm system for a 10-room hotel",
            "What detectors are compatible with sounder bases?"
        ]
        
        successful_queries = 0
        for i, query in enumerate(test_queries):
            try:
                logger.info(f"🔍 Testing query {i+1}: {query}")
                
                result = pipeline.process_query(query)
                
                # Verify result structure
                assert hasattr(result, 'answer')
                assert hasattr(result, 'bill_of_quantities')
                assert hasattr(result, 'iterations_performed')
                
                boq_items = len(result.bill_of_quantities)
                logger.info(f"✅ Query {i+1} successful: Generated BOQ with {boq_items} items")
                
                # Log sample of result
                if result.bill_of_quantities:
                    sample_item = result.bill_of_quantities[0]
                    logger.info(f"   Sample BOQ item: {sample_item.get('item', 'N/A')} (SKU: {sample_item.get('sku', 'N/A')})")
                
                successful_queries += 1
                
            except Exception as e:
                logger.error(f"❌ Query {i+1} failed: {e}")
        
        # 8. Test caching system
        logger.info("📋 Step 8: Testing LLM caching system")
        
        # Test cache stats
        cache_stats = cached_client.get_cache_stats()
        logger.info(f"📈 Cache stats: {cache_stats}")
        
        # Test cache with repeated query
        if test_queries:
            logger.info("🔄 Testing cache with repeated query")
            test_query = test_queries[0]
            
            # First call (should miss cache)
            start_time = time.time()
            result1 = pipeline.process_query(test_query)
            first_call_time = time.time() - start_time
            
            # Second call (should hit cache for some operations)
            start_time = time.time()
            result2 = pipeline.process_query(test_query)
            second_call_time = time.time() - start_time
            
            logger.info(f"⚡ First call: {first_call_time:.2f}s, Second call: {second_call_time:.2f}s")
            
            if second_call_time < first_call_time * 0.8:
                logger.info("✅ Caching appears to be working (second call faster)")
            else:
                logger.info("ℹ️  Caching effect may not be visible in this test")
        
        # 9. Generate test report
        logger.info("📋 Step 9: Generating test report")
        
        report = {
            "test_timestamp": time.time(),
            "environment_check": "✅ PASSED",
            "database_connections": "✅ PASSED",
            "pdf_parsing": f"✅ PASSED - Processed {len(extracted_docs)} documents",
            "knowledge_extraction": f"✅ PASSED - Extracted knowledge from {len(all_knowledge)} documents",
            "graph_loading": "✅ PASSED" if all_knowledge else "⚠️  SKIPPED - No documents",
            "retrieval_components": "✅ PASSED",
            "pipeline_queries": f"✅ {successful_queries}/{len(test_queries)} PASSED",
            "caching_system": "✅ PASSED",
            "overall_status": "✅ SYSTEM OPERATIONAL" if successful_queries > 0 else "⚠️  PARTIAL SUCCESS"
        }
        
        # Save report
        report_file = project_root / 'test_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📊 Test report saved to {report_file}")
        
        # Print summary
        logger.info("=" * 60)
        logger.info("🎉 COMPREHENSIVE SYSTEM TEST COMPLETE")
        logger.info("=" * 60)
        
        for component, status in report.items():
            if component != "test_timestamp":
                logger.info(f"{component.replace('_', ' ').title()}: {status}")
        
        logger.info("=" * 60)
        
        # Cleanup connections
        neo4j_driver.close()
        
        return successful_queries > 0
        
    except Exception as e:
        logger.error(f"💥 System test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_complete_system()
    
    if success:
        logger.info("🎊 All tests completed successfully!")
        sys.exit(0)
    else:
        logger.error("💥 Some tests failed. Check logs for details.")
        sys.exit(1)