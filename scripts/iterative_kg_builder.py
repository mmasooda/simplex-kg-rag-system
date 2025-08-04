#!/usr/bin/env python3
"""
Iterative Knowledge Graph Builder with Vectorization
Runs for 1 hour with continuous refinement and optimization
"""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import boto3
from neo4j import GraphDatabase
from openai import OpenAI
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from tqdm import tqdm
import pandas as pd

from src.ingestion.pdf_parser import S3DocumentIngester, PDFParser
from src.ingestion.knowledge_extractor import KnowledgeExtractor
from src.ingestion.graph_loader import Neo4jBulkLoader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IterativeKGBuilder:
    """Builds and refines knowledge graph iteratively with vectorization"""
    
    def __init__(self):
        load_dotenv()
        
        # Initialize clients
        self.s3_client = boto3.client('s3')
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        # Sentence transformer for vectorization
        logger.info("Loading sentence transformer model...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # FAISS index for vector search
        self.dimension = 384  # all-MiniLM-L6-v2 output dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        self.text_store = []
        
        # Metrics tracking
        self.metrics = {
            'pdfs_processed': 0,
            'tables_extracted': 0,
            'entities_created': 0,
            'relationships_created': 0,
            'vectors_indexed': 0,
            'iterations_completed': 0,
            'api_calls_made': 0,
            'start_time': datetime.now()
        }
        
    def extract_from_pdfs(self, bucket_name='simplezdatasheet'):
        """Extract tables and text from PDFs with rate limiting"""
        logger.info(f"Starting PDF extraction from bucket: {bucket_name}")
        
        parser = PDFParser(use_advanced_tables=True)
        
        # List S3 objects
        response = self.s3_client.list_objects_v2(Bucket=bucket_name)
        pdf_files = [obj['Key'] for obj in response.get('Contents', []) 
                    if obj['Key'].lower().endswith('.pdf')]
        
        all_documents = []
        
        for pdf_key in pdf_files[:5]:  # Limit to 5 PDFs initially
            try:
                logger.info(f"Processing {pdf_key}...")
                
                # Download PDF
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    self.s3_client.download_file(bucket_name, pdf_key, tmp_file.name)
                    
                    # Extract content
                    doc = parser.extract_from_pdf(Path(tmp_file.name))
                    doc.metadata['s3_key'] = pdf_key
                    all_documents.append(doc)
                    
                    self.metrics['pdfs_processed'] += 1
                    self.metrics['tables_extracted'] += len(doc.tables)
                    
                    # Clean up
                    os.unlink(tmp_file.name)
                    
                # Rate limiting
                time.sleep(2)  # 2 second delay between PDFs
                
            except Exception as e:
                logger.error(f"Error processing {pdf_key}: {e}")
                
        return all_documents
    
    def extract_entities_from_tables(self, documents):
        """Extract structured entities from tables with LLM assistance"""
        logger.info("Extracting entities from tables...")
        
        all_entities = []
        all_relationships = []
        
        for doc in documents:
            for idx, table in enumerate(doc.tables):
                try:
                    # Convert table to string
                    table_text = table.to_string()
                    
                    # Use LLM to extract entities (with rate limiting)
                    prompt = f"""Extract Simplex fire alarm product information from this table:

{table_text}

Return JSON with:
{{
  "products": [
    {{
      "sku": "product SKU",
      "name": "product name",
      "type": "Panel|Module|Device|Detector|Base",
      "category": "specific category",
      "description": "description",
      "attributes": {{}}
    }}
  ],
  "relationships": [
    {{
      "from_sku": "SKU1",
      "to_sku": "SKU2",
      "type": "COMPATIBLE_WITH|REQUIRES|HAS_MODULE|ALTERNATIVE_TO"
    }}
  ]
}}"""

                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=1000
                    )
                    
                    self.metrics['api_calls_made'] += 1
                    
                    # Parse response
                    result = json.loads(response.choices[0].message.content)
                    all_entities.extend(result.get('products', []))
                    all_relationships.extend(result.get('relationships', []))
                    
                    # Rate limiting
                    time.sleep(1)  # 1 second between API calls
                    
                except Exception as e:
                    logger.warning(f"Error extracting from table {idx}: {e}")
                    
        return all_entities, all_relationships
    
    def vectorize_content(self, documents, entities):
        """Create vector embeddings for all content"""
        logger.info("Creating vector embeddings...")
        
        texts_to_embed = []
        
        # Add document text
        for doc in documents:
            # Split text into chunks
            chunks = self._chunk_text(doc.text_content, chunk_size=500)
            for chunk in chunks:
                texts_to_embed.append({
                    'text': chunk,
                    'source': doc.filename,
                    'type': 'document_text'
                })
        
        # Add entity descriptions
        for entity in entities:
            entity_text = f"{entity.get('sku', '')} {entity.get('name', '')} {entity.get('description', '')}"
            texts_to_embed.append({
                'text': entity_text,
                'source': entity.get('sku', 'unknown'),
                'type': 'entity'
            })
        
        # Create embeddings in batches
        batch_size = 32
        for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="Vectorizing"):
            batch = texts_to_embed[i:i+batch_size]
            batch_texts = [item['text'] for item in batch]
            
            # Generate embeddings
            embeddings = self.embedder.encode(batch_texts)
            
            # Add to FAISS index
            self.index.add(embeddings)
            self.text_store.extend(batch)
            self.metrics['vectors_indexed'] += len(batch)
            
        logger.info(f"Indexed {self.metrics['vectors_indexed']} vectors")
    
    def refine_knowledge_graph(self):
        """Iteratively refine the knowledge graph"""
        logger.info("Refining knowledge graph...")
        
        with self.neo4j_driver.session() as session:
            # Get all entities
            result = session.run("""
                MATCH (n)
                WHERE n:Panel OR n:Module OR n:Device OR n:Detector OR n:Base
                RETURN n.sku as sku, n.name as name, labels(n) as labels
            """)
            
            entities = list(result)
            
            # Find missing relationships
            for i, entity1 in enumerate(entities):
                for entity2 in entities[i+1:]:
                    # Check if relationship should exist
                    if self._should_have_relationship(entity1, entity2):
                        # Create relationship
                        session.run("""
                            MATCH (a {sku: $sku1}), (b {sku: $sku2})
                            MERGE (a)-[:COMPATIBLE_WITH]->(b)
                        """, sku1=entity1['sku'], sku2=entity2['sku'])
                        
                        self.metrics['relationships_created'] += 1
            
            # Add technical specifications
            self._enrich_entities_with_specs(session)
            
        self.metrics['iterations_completed'] += 1
    
    def _should_have_relationship(self, entity1, entity2):
        """Determine if two entities should have a relationship"""
        # Panels are compatible with modules and devices
        if 'Panel' in entity1['labels'] and ('Module' in entity2['labels'] or 'Device' in entity2['labels']):
            return True
        
        # Detectors require bases
        if 'Detector' in entity1['labels'] and 'Base' in entity2['labels']:
            return True
            
        return False
    
    def _enrich_entities_with_specs(self, session):
        """Add technical specifications to entities"""
        # Query vector store for additional information
        sample_entities = session.run("""
            MATCH (n)
            WHERE n:Panel OR n:Module OR n:Device
            RETURN n.sku as sku, n.name as name
            LIMIT 10
        """)
        
        for entity in sample_entities:
            # Search vector store for related content
            query = f"{entity['sku']} {entity['name']} specifications"
            query_vector = self.embedder.encode([query])
            
            # Find nearest neighbors
            k = 5
            distances, indices = self.index.search(query_vector, k)
            
            # Aggregate relevant information
            relevant_texts = [self.text_store[idx]['text'] for idx in indices[0]]
            
            # Update entity with enriched data
            enriched_desc = self._summarize_texts(relevant_texts, entity['sku'])
            
            if enriched_desc:
                session.run("""
                    MATCH (n {sku: $sku})
                    SET n.enriched_description = $desc,
                        n.last_updated = datetime()
                """, sku=entity['sku'], desc=enriched_desc)
    
    def _summarize_texts(self, texts, sku):
        """Summarize multiple texts into enriched description"""
        if not texts:
            return None
            
        combined = " ".join(texts[:3])  # Limit to avoid token limits
        
        prompt = f"""Summarize technical specifications for Simplex product {sku} based on:
{combined[:2000]}

Return a concise technical description (max 200 words)."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            self.metrics['api_calls_made'] += 1
            return response.choices[0].message.content
        except:
            return None
    
    def _chunk_text(self, text, chunk_size=500):
        """Split text into chunks"""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks
    
    def test_combined_pipeline(self):
        """Test the combined KG + Vector retrieval pipeline"""
        logger.info("Testing combined pipeline...")
        
        test_query = "I need a fire alarm system for a 10-story office building with voice evacuation"
        
        # Vector search
        query_vector = self.embedder.encode([test_query])
        distances, indices = self.index.search(query_vector, k=10)
        
        vector_results = [self.text_store[idx] for idx in indices[0]]
        
        # Knowledge graph search
        with self.neo4j_driver.session() as session:
            kg_results = session.run("""
                MATCH (p:Panel {voice_capability: true})-[:COMPATIBLE_WITH]-(m)
                RETURN p, m LIMIT 10
            """)
            
            kg_data = list(kg_results)
        
        logger.info(f"Vector results: {len(vector_results)}")
        logger.info(f"KG results: {len(kg_data)}")
        
        # Combine results for LLM
        combined_context = self._format_combined_context(vector_results, kg_data)
        
        # Generate final answer
        final_prompt = f"""Based on the following knowledge graph and document information:

{combined_context}

User Query: {test_query}

Provide a detailed technical recommendation for a Simplex fire alarm system."""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.2,
            max_tokens=1000
        )
        
        logger.info("Final Answer:")
        logger.info(response.choices[0].message.content)
        
        return response.choices[0].message.content
    
    def _format_combined_context(self, vector_results, kg_results):
        """Format combined context from vector and KG results"""
        context = "RELEVANT DOCUMENTS:\n"
        for vr in vector_results[:5]:
            context += f"- {vr['text'][:200]}...\n"
        
        context += "\nKNOWLEDGE GRAPH DATA:\n"
        for kg in kg_results[:5]:
            context += f"- {kg}\n"
            
        return context
    
    def run_for_duration(self, duration_hours=1):
        """Run the iterative builder for specified duration"""
        end_time = datetime.now() + timedelta(hours=duration_hours)
        iteration = 0
        
        logger.info(f"Starting iterative KG building for {duration_hours} hour(s)")
        logger.info(f"Will run until: {end_time}")
        
        while datetime.now() < end_time:
            iteration += 1
            logger.info(f"\n=== ITERATION {iteration} ===")
            
            try:
                # Step 1: Extract from PDFs (first iteration only)
                if iteration == 1:
                    documents = self.extract_from_pdfs()
                    
                    # Step 2: Extract entities
                    entities, relationships = self.extract_entities_from_tables(documents)
                    
                    # Step 3: Load to Neo4j
                    self._load_to_neo4j(entities, relationships)
                    
                    # Step 4: Vectorize content
                    self.vectorize_content(documents, entities)
                
                # Step 5: Refine knowledge graph
                self.refine_knowledge_graph()
                
                # Step 6: Test pipeline (every 5 iterations)
                if iteration % 5 == 0:
                    self.test_combined_pipeline()
                
                # Print metrics
                self._print_metrics()
                
                # Rate limiting between iterations
                time.sleep(30)  # 30 second pause between iterations
                
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                time.sleep(60)  # Wait 1 minute on error
        
        logger.info("\n=== FINAL METRICS ===")
        self._print_metrics()
        
        # Save final state
        self._save_final_state()
    
    def _load_to_neo4j(self, entities, relationships):
        """Load entities and relationships to Neo4j"""
        with self.neo4j_driver.session() as session:
            # Create entities
            for entity in entities:
                labels = entity.get('type', 'Device')
                session.run(f"""
                    MERGE (n:{labels} {{sku: $sku}})
                    SET n += $props
                """, sku=entity['sku'], props=entity)
                
                self.metrics['entities_created'] += 1
            
            # Create relationships
            for rel in relationships:
                session.run(f"""
                    MATCH (a {{sku: $from_sku}}), (b {{sku: $to_sku}})
                    MERGE (a)-[:{rel['type']}]->(b)
                """, from_sku=rel['from_sku'], to_sku=rel['to_sku'])
                
                self.metrics['relationships_created'] += 1
    
    def _print_metrics(self):
        """Print current metrics"""
        runtime = datetime.now() - self.metrics['start_time']
        logger.info(f"""
Current Metrics:
- Runtime: {runtime}
- PDFs Processed: {self.metrics['pdfs_processed']}
- Tables Extracted: {self.metrics['tables_extracted']}
- Entities Created: {self.metrics['entities_created']}
- Relationships Created: {self.metrics['relationships_created']}
- Vectors Indexed: {self.metrics['vectors_indexed']}
- Iterations Completed: {self.metrics['iterations_completed']}
- API Calls Made: {self.metrics['api_calls_made']}
""")
    
    def _save_final_state(self):
        """Save the final state and metrics"""
        # Save metrics
        with open('kg_build_metrics.json', 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        # Save vector index
        faiss.write_index(self.index, 'simplex_vectors.index')
        
        # Save text store
        with open('text_store.json', 'w') as f:
            json.dump(self.text_store, f, indent=2)
        
        logger.info("Final state saved!")

if __name__ == "__main__":
    builder = IterativeKGBuilder()
    builder.run_for_duration(duration_hours=1)