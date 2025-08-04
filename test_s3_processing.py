#!/usr/bin/env python3
"""
Test S3 processing with a limited set of files
"""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase
from src.data_ingestion.s3_comprehensive_processor import S3ComprehensiveProcessor

# Load environment
load_dotenv()

def test_s3_processing():
    """Test S3 processing with sample files"""
    
    # Initialize clients
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    neo4j_driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
    )
    
    # Initialize processor
    processor = S3ComprehensiveProcessor(
        bucket_name=os.getenv('AWS_BUCKET_NAME'),
        openai_client=openai_client,
        neo4j_driver=neo4j_driver
    )
    
    # Get first few PDF files only for testing
    all_pdfs = processor.discover_all_pdfs()
    test_pdfs = all_pdfs[:3]  # Process only first 3 files for testing
    
    print(f"Testing with {len(test_pdfs)} files:")
    for pdf in test_pdfs:
        print(f"  - {pdf['key']} ({pdf['size']} bytes)")
    
    # Process the test files
    results = []
    for pdf_info in test_pdfs:
        print(f"\nProcessing: {pdf_info['filename']}")
        result = processor.process_single_pdf(pdf_info)
        results.append(result)
        
        if result['success']:
            print(f"✅ Success: {result['nodes_created']} nodes created")
            if result['pymupdf_result']:
                print(f"   Text pages: {result['pymupdf_result']['successful_pages']}")
            if result['camelot_result']:
                print(f"   Tables: {result['camelot_result']['table_count']}")
        else:
            print(f"❌ Failed: {result['errors']}")
    
    # Get final statistics
    stats = processor.get_graph_statistics()
    print(f"\n=== FINAL STATISTICS ===")
    print(f"Total nodes created: {processor.stats['created_nodes']}")
    print(f"Total pages extracted: {processor.stats['extracted_pages']}")
    print(f"Total tables extracted: {processor.stats['extracted_tables']}")
    print(f"Processing errors: {len(processor.stats['processing_errors'])}")
    
    # Show graph statistics
    print(f"\n=== GRAPH STATISTICS ===")
    if stats:
        print(f"Total nodes in graph: {stats.get('total_nodes', 0)}")
        print(f"Total relationships: {stats.get('total_relationships', 0)}")
        
        if stats.get('nodes_by_label'):
            print("Nodes by type:")
            for label, count in stats['nodes_by_label'].items():
                print(f"  {label}: {count}")
    
    # Cleanup
    neo4j_driver.close()
    
    return results

if __name__ == "__main__":
    test_s3_processing()