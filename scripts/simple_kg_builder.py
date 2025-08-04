#!/usr/bin/env python3
"""
Simple Iterative Knowledge Graph Builder
Runs for 1 hour with continuous refinement without heavy ML dependencies
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
import hashlib
from tqdm import tqdm

from src.ingestion.pdf_parser import S3DocumentIngester, PDFParser
from src.ingestion.knowledge_extractor import KnowledgeExtractor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleKGBuilder:
    """Builds and refines knowledge graph iteratively"""
    
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
        
        # Simple text store for embeddings
        self.text_store = []
        self.embeddings_cache = {}
        
        # Metrics tracking
        self.metrics = {
            'pdfs_processed': 0,
            'tables_extracted': 0,
            'entities_created': 0,
            'relationships_created': 0,
            'text_chunks_stored': 0,
            'iterations_completed': 0,
            'api_calls_made': 0,
            'start_time': datetime.now()
        }
        
    def get_simple_embedding(self, text):
        """Get embedding using OpenAI API with caching"""
        # Simple cache using text hash
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        if text_hash in self.embeddings_cache:
            return self.embeddings_cache[text_hash]
        
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Limit to 8000 chars
            )
            embedding = response.data[0].embedding
            self.embeddings_cache[text_hash] = embedding
            self.metrics['api_calls_made'] += 1
            return embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
        
    def extract_from_pdfs(self, bucket_name='simplezdatasheet'):
        """Extract tables and text from PDFs with rate limiting"""
        logger.info(f"Starting PDF extraction from bucket: {bucket_name}")
        
        parser = PDFParser(use_advanced_tables=True)
        
        # List S3 objects
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket_name)
            pdf_files = [obj['Key'] for obj in response.get('Contents', []) 
                        if obj['Key'].lower().endswith('.pdf')]
        except Exception as e:
            logger.error(f"Error listing S3 objects: {e}")
            return []
        
        all_documents = []
        
        for pdf_key in pdf_files[:3]:  # Process 3 PDFs at a time
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
            # Limit tables per document to control API usage
            tables_to_process = min(len(doc.tables), 5)
            
            for idx in range(tables_to_process):
                table = doc.tables[idx]
                try:
                    # Convert table to string
                    table_text = table.to_string()
                    
                    # Skip very small tables
                    if len(table_text) < 50:
                        continue
                    
                    # Use LLM to extract entities
                    prompt = f"""Extract Simplex fire alarm product information from this table.
Focus on: SKU/Part numbers, Product names, Types (Panel/Module/Device/Detector/Base), Compatibility.

Table:
{table_text[:1500]}

Return JSON with products and relationships only if found:
{{
  "products": [
    {{
      "sku": "SKU",
      "name": "name",
      "type": "Panel|Module|Device|Detector|Base",
      "description": "brief description"
    }}
  ],
  "relationships": [
    {{
      "from_sku": "SKU1",
      "to_sku": "SKU2",
      "type": "COMPATIBLE_WITH|REQUIRES"
    }}
  ]
}}"""

                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500
                    )
                    
                    self.metrics['api_calls_made'] += 1
                    
                    # Parse response
                    content = response.choices[0].message.content
                    # Extract JSON from response
                    if '{' in content and '}' in content:
                        json_str = content[content.find('{'):content.rfind('}')+1]
                        result = json.loads(json_str)
                        all_entities.extend(result.get('products', []))
                        all_relationships.extend(result.get('relationships', []))
                    
                    # Rate limiting
                    time.sleep(2)  # 2 seconds between API calls
                    
                except Exception as e:
                    logger.warning(f"Error extracting from table {idx}: {e}")
                    
        return all_entities, all_relationships
    
    def store_text_chunks(self, documents):
        """Store text chunks with simple embeddings"""
        logger.info("Storing text chunks...")
        
        for doc in documents:
            # Split text into chunks
            chunks = self._chunk_text(doc.text_content, chunk_size=500)
            
            for chunk in chunks[:10]:  # Limit chunks per document
                if len(chunk) > 50:  # Skip very small chunks
                    self.text_store.append({
                        'text': chunk,
                        'source': doc.filename,
                        'type': 'document_text'
                    })
                    self.metrics['text_chunks_stored'] += 1
    
    def refine_knowledge_graph(self):
        """Iteratively refine the knowledge graph"""
        logger.info("Refining knowledge graph...")
        
        with self.neo4j_driver.session() as session:
            # Get entity counts
            result = session.run("""
                MATCH (n)
                WHERE n:Panel OR n:Module OR n:Device OR n:Detector OR n:Base
                RETURN count(n) as count, labels(n)[0] as type
            """)
            
            counts = {row['type']: row['count'] for row in result}
            logger.info(f"Current entity counts: {counts}")
            
            # Add missing compatibility relationships
            session.run("""
                // Panels compatible with all modules
                MATCH (p:Panel), (m:Module)
                WHERE NOT (p)-[:COMPATIBLE_WITH]-(m)
                MERGE (p)-[:COMPATIBLE_WITH]->(m)
            """)
            
            # Add detector-base relationships
            session.run("""
                // Detectors require bases
                MATCH (d:Detector), (b:Base)
                WHERE NOT (d)-[:REQUIRES_BASE]-(b)
                AND (
                    (d.name CONTAINS 'Heat' AND b.name CONTAINS 'Temperature')
                    OR (d.name CONTAINS 'Smoke' AND b.name CONTAINS 'Standard')
                    OR NOT EXISTS(d.base_type)
                )
                MERGE (d)-[:REQUIRES_BASE]->(b)
            """)
            
            # Count relationships
            rel_count = session.run("""
                MATCH ()-[r]->()
                RETURN count(r) as count
            """).single()['count']
            
            logger.info(f"Total relationships: {rel_count}")
            
        self.metrics['iterations_completed'] += 1
    
    def enrich_with_context(self):
        """Enrich entities with context from stored text"""
        logger.info("Enriching entities with context...")
        
        with self.neo4j_driver.session() as session:
            # Get a sample of entities to enrich
            entities = session.run("""
                MATCH (n)
                WHERE (n:Panel OR n:Module OR n:Device)
                AND NOT EXISTS(n.enriched_description)
                RETURN n.sku as sku, n.name as name
                LIMIT 5
            """)
            
            for entity in entities:
                # Find relevant text chunks
                relevant_chunks = []
                for chunk in self.text_store:
                    if entity['sku'] in chunk['text'] or entity['name'] in chunk['text']:
                        relevant_chunks.append(chunk['text'])
                
                if relevant_chunks:
                    # Summarize using LLM
                    combined = " ".join(relevant_chunks[:3])[:1500]
                    
                    prompt = f"""Based on the following text, provide a technical summary for {entity['name']} ({entity['sku']}):

{combined}

Provide a 2-3 sentence technical description."""

                    try:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.1,
                            max_tokens=200
                        )
                        
                        description = response.choices[0].message.content
                        self.metrics['api_calls_made'] += 1
                        
                        # Update entity
                        session.run("""
                            MATCH (n {sku: $sku})
                            SET n.enriched_description = $desc,
                                n.last_enriched = datetime()
                        """, sku=entity['sku'], desc=description)
                        
                        time.sleep(2)  # Rate limiting
                        
                    except Exception as e:
                        logger.error(f"Error enriching {entity['sku']}: {e}")
    
    def test_combined_pipeline(self):
        """Test the combined KG + text retrieval pipeline"""
        logger.info("Testing combined pipeline...")
        
        test_queries = [
            "I need a fire alarm system for a 10-story office building",
            "What detectors are compatible with 4100ES panel?",
            "I need smoke detectors with relay bases"
        ]
        
        for query in test_queries:
            logger.info(f"\nTesting query: {query}")
            
            # Find relevant text chunks
            relevant_texts = []
            for chunk in self.text_store[:20]:  # Check first 20 chunks
                if any(word in chunk['text'].lower() for word in query.lower().split()):
                    relevant_texts.append(chunk['text'])
            
            # Knowledge graph search
            with self.neo4j_driver.session() as session:
                # Extract key terms
                if "4100ES" in query:
                    kg_query = """
                        MATCH (p:Panel {sku: '4100ES'})-[:COMPATIBLE_WITH]-(n)
                        RETURN p, n LIMIT 5
                    """
                elif "detector" in query.lower():
                    kg_query = """
                        MATCH (d:Detector)-[:REQUIRES_BASE]-(b:Base)
                        RETURN d, b LIMIT 5
                    """
                else:
                    kg_query = """
                        MATCH (p:Panel)-[:COMPATIBLE_WITH]-(m:Module)
                        RETURN p, m LIMIT 5
                    """
                
                kg_results = list(session.run(kg_query))
            
            # Combine results
            context = "KNOWLEDGE GRAPH DATA:\n"
            for result in kg_results:
                context += f"- {result}\n"
            
            context += "\nRELEVANT DOCUMENTS:\n"
            for text in relevant_texts[:3]:
                context += f"- {text[:200]}...\n"
            
            # Generate answer
            final_prompt = f"""Based on the following knowledge:

{context}

User Query: {query}

Provide a specific technical recommendation using Simplex products."""

            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": final_prompt}],
                    temperature=0.2,
                    max_tokens=500
                )
                
                answer = response.choices[0].message.content
                self.metrics['api_calls_made'] += 1
                
                logger.info(f"Answer: {answer[:200]}...")
                
                # Save result
                with open(f'test_result_{datetime.now().strftime("%H%M%S")}.txt', 'w') as f:
                    f.write(f"Query: {query}\n")
                    f.write(f"Context: {context}\n")
                    f.write(f"Answer: {answer}\n")
                
                time.sleep(3)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error generating answer: {e}")
    
    def _chunk_text(self, text, chunk_size=500):
        """Split text into chunks"""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks
    
    def _load_to_neo4j(self, entities, relationships):
        """Load entities and relationships to Neo4j"""
        with self.neo4j_driver.session() as session:
            # Create entities
            for entity in entities:
                if not entity.get('sku'):
                    continue
                    
                labels = entity.get('type', 'Device')
                props = {k: v for k, v in entity.items() if v is not None}
                
                session.run(f"""
                    MERGE (n:{labels} {{sku: $sku}})
                    SET n += $props
                """, sku=entity['sku'], props=props)
                
                self.metrics['entities_created'] += 1
            
            # Create relationships  
            for rel in relationships:
                if rel.get('from_sku') and rel.get('to_sku'):
                    session.run(f"""
                        MATCH (a {{sku: $from_sku}}), (b {{sku: $to_sku}})
                        MERGE (a)-[:{rel.get('type', 'RELATED_TO')}]->(b)
                    """, from_sku=rel['from_sku'], to_sku=rel['to_sku'])
                    
                    self.metrics['relationships_created'] += 1
    
    def run_for_duration(self, duration_hours=1):
        """Run the iterative builder for specified duration"""
        end_time = datetime.now() + timedelta(hours=duration_hours)
        iteration = 0
        
        logger.info(f"Starting iterative KG building for {duration_hours} hour(s)")
        logger.info(f"Will run until: {end_time}")
        
        # Initial data loading
        logger.info("\n=== INITIAL DATA LOADING ===")
        documents = self.extract_from_pdfs()
        
        if documents:
            # Extract entities
            entities, relationships = self.extract_entities_from_tables(documents)
            
            # Load to Neo4j
            self._load_to_neo4j(entities, relationships)
            
            # Store text chunks
            self.store_text_chunks(documents)
        
        # Iterative refinement
        while datetime.now() < end_time:
            iteration += 1
            logger.info(f"\n=== ITERATION {iteration} ===")
            
            try:
                # Refine knowledge graph
                self.refine_knowledge_graph()
                
                # Enrich with context (every 3 iterations)
                if iteration % 3 == 0:
                    self.enrich_with_context()
                
                # Test pipeline (every 5 iterations)
                if iteration % 5 == 0:
                    self.test_combined_pipeline()
                
                # Load more data (every 10 iterations)
                if iteration % 10 == 0 and iteration > 0:
                    logger.info("Loading additional documents...")
                    new_docs = self.extract_from_pdfs()
                    if new_docs:
                        entities, relationships = self.extract_entities_from_tables(new_docs)
                        self._load_to_neo4j(entities, relationships)
                        self.store_text_chunks(new_docs)
                
                # Print metrics
                self._print_metrics()
                
                # Wait before next iteration
                wait_time = 60 if iteration < 10 else 120  # Longer waits later
                logger.info(f"Waiting {wait_time} seconds before next iteration...")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                time.sleep(60)  # Wait 1 minute on error
        
        logger.info("\n=== FINAL METRICS ===")
        self._print_metrics()
        self._save_final_state()
    
    def _print_metrics(self):
        """Print current metrics"""
        runtime = datetime.now() - self.metrics['start_time']
        logger.info(f"""
Metrics after {runtime}:
- PDFs Processed: {self.metrics['pdfs_processed']}
- Tables Extracted: {self.metrics['tables_extracted']}  
- Entities Created: {self.metrics['entities_created']}
- Relationships Created: {self.metrics['relationships_created']}
- Text Chunks Stored: {self.metrics['text_chunks_stored']}
- Iterations Completed: {self.metrics['iterations_completed']}
- API Calls Made: {self.metrics['api_calls_made']}
""")
    
    def _save_final_state(self):
        """Save the final state and metrics"""
        # Save metrics
        with open('kg_build_metrics.json', 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        # Save text store
        with open('text_store.json', 'w') as f:
            json.dump(self.text_store, f, indent=2)
        
        # Export knowledge graph summary
        with self.neo4j_driver.session() as session:
            summary = session.run("""
                MATCH (n)
                WHERE n:Panel OR n:Module OR n:Device OR n:Detector OR n:Base
                RETURN labels(n)[0] as type, count(n) as count
                ORDER BY count DESC
            """)
            
            kg_summary = list(summary)
            
            rel_summary = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)
            
            rel_summary = list(rel_summary)
        
        with open('kg_summary.json', 'w') as f:
            json.dump({
                'nodes': kg_summary,
                'relationships': rel_summary,
                'metrics': self.metrics
            }, f, indent=2, default=str)
        
        logger.info("Final state saved to kg_build_metrics.json, text_store.json, and kg_summary.json")

if __name__ == "__main__":
    builder = SimpleKGBuilder()
    builder.run_for_duration(duration_hours=1)