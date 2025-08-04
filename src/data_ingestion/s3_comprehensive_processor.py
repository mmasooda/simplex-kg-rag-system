#!/usr/bin/env python3
"""
Comprehensive S3 PDF Processor
Handles all directories and subdirectories with robust error handling
Uses both PyMuPDF and Camelot for complete extraction
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import fitz  # PyMuPDF
import camelot
import tempfile
from io import BytesIO
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.knowledge_extractor import KnowledgeExtractor
from src.core.graph_loader import GraphLoader

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class S3ComprehensiveProcessor:
    """
    Comprehensive S3 PDF processor that handles all directories and subdirectories
    Uses both PyMuPDF and Camelot for complete data extraction
    """
    
    def __init__(self, bucket_name: str, openai_client, neo4j_driver):
        self.bucket_name = bucket_name
        self.openai_client = openai_client
        self.neo4j_driver = neo4j_driver
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3')
            logger.info("S3 client initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        
        # Initialize processing components
        self.knowledge_extractor = KnowledgeExtractor(openai_client)
        self.graph_loader = GraphLoader(neo4j_driver)
        
        # Processing statistics
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'extracted_pages': 0,
            'extracted_tables': 0,
            'created_nodes': 0,
            'processing_errors': []
        }
    
    def discover_all_pdfs(self) -> List[Dict[str, Any]]:
        """
        Discover all PDF files in all directories and subdirectories
        
        Returns:
            List of dictionaries with file information
        """
        logger.info(f"Discovering all PDF files in S3 bucket: {self.bucket_name}")
        
        pdf_files = []
        
        try:
            # List all objects in the bucket
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        
                        # Check if it's a PDF file
                        if key.lower().endswith('.pdf'):
                            pdf_info = {
                                'key': key,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'],
                                'directory': '/'.join(key.split('/')[:-1]) if '/' in key else 'root',
                                'filename': key.split('/')[-1]
                            }
                            pdf_files.append(pdf_info)
                            logger.info(f"Found PDF: {key} ({obj['Size']} bytes)")
            
            logger.info(f"Discovered {len(pdf_files)} PDF files across all directories")
            self.stats['total_files'] = len(pdf_files)
            
            return pdf_files
            
        except ClientError as e:
            logger.error(f"Error discovering PDF files: {e}")
            return []
    
    def download_pdf_from_s3(self, key: str) -> Optional[bytes]:
        """
        Download PDF file from S3
        
        Args:
            key: S3 object key
            
        Returns:
            PDF content as bytes or None if failed
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading {key}: {e}")
            self.stats['processing_errors'].append(f"Download failed for {key}: {str(e)}")
            return None
    
    def extract_text_with_pymupdf(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text and metadata using PyMuPDF (handles missing pages gracefully)
        
        Args:
            pdf_content: PDF content as bytes
            filename: Original filename for logging
            
        Returns:
            Dictionary with extracted content
        """
        extracted_data = {
            'text_content': [],
            'metadata': {},
            'page_count': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'extraction_method': 'PyMuPDF'
        }
        
        try:
            # Open PDF from memory
            pdf_document = fitz.open("pdf", pdf_content)
            extracted_data['page_count'] = pdf_document.page_count
            extracted_data['metadata'] = pdf_document.metadata
            
            logger.info(f"Processing {filename} with PyMuPDF - {pdf_document.page_count} pages")
            
            # Extract text from each page
            for page_num in range(pdf_document.page_count):
                try:
                    page = pdf_document[page_num]
                    text = page.get_text()
                    
                    if text.strip():  # Only add non-empty pages
                        extracted_data['text_content'].append({
                            'page_num': page_num + 1,
                            'text': text.strip(),
                            'char_count': len(text)
                        })
                        extracted_data['successful_pages'] += 1
                    else:
                        logger.warning(f"Page {page_num + 1} in {filename} appears to be empty")
                
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num + 1} from {filename}: {e}")
                    extracted_data['failed_pages'] += 1
                    continue
            
            pdf_document.close()
            
            logger.info(f"PyMuPDF extraction completed for {filename}: "
                       f"{extracted_data['successful_pages']}/{extracted_data['page_count']} pages successful")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"PyMuPDF failed to process {filename}: {e}")
            self.stats['processing_errors'].append(f"PyMuPDF failed for {filename}: {str(e)}")
            return extracted_data
    
    def extract_tables_with_camelot(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract tables using Camelot (handles missing pages gracefully)
        
        Args:
            pdf_content: PDF content as bytes
            filename: Original filename for logging
            
        Returns:
            Dictionary with extracted tables
        """
        extracted_tables = {
            'tables': [],
            'table_count': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'extraction_method': 'Camelot'
        }
        
        try:
            # Save PDF content to temporary file (Camelot requires file path)
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_path = tmp_file.name
            
            try:
                # Extract tables using lattice method (better for lined tables)
                try:
                    tables_lattice = camelot.read_pdf(tmp_path, flavor='lattice', pages='all')
                    logger.info(f"Camelot lattice method found {len(tables_lattice)} tables in {filename}")
                    
                    for i, table in enumerate(tables_lattice):
                        table_data = {
                            'table_id': f"lattice_{i}",
                            'page_num': table.page,
                            'method': 'lattice',
                            'accuracy': table.parsing_report.get('accuracy', 0),
                            'shape': table.shape,
                            'data': table.df.to_dict('records') if not table.df.empty else []
                        }
                        extracted_tables['tables'].append(table_data)
                        extracted_tables['successful_pages'] += 1
                
                except Exception as e:
                    logger.warning(f"Camelot lattice method failed for {filename}: {e}")
                
                # Try stream method as fallback (better for stream tables)
                try:
                    tables_stream = camelot.read_pdf(tmp_path, flavor='stream', pages='all')
                    logger.info(f"Camelot stream method found {len(tables_stream)} tables in {filename}")
                    
                    for i, table in enumerate(tables_stream):
                        table_data = {
                            'table_id': f"stream_{i}",
                            'page_num': table.page,
                            'method': 'stream',
                            'accuracy': table.parsing_report.get('accuracy', 0),
                            'shape': table.shape,
                            'data': table.df.to_dict('records') if not table.df.empty else []
                        }
                        extracted_tables['tables'].append(table_data)
                
                except Exception as e:
                    logger.warning(f"Camelot stream method failed for {filename}: {e}")
                
                extracted_tables['table_count'] = len(extracted_tables['tables'])
                
                logger.info(f"Camelot extraction completed for {filename}: "
                           f"{extracted_tables['table_count']} tables extracted")
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            return extracted_tables
            
        except Exception as e:
            logger.error(f"Camelot failed to process {filename}: {e}")
            self.stats['processing_errors'].append(f"Camelot failed for {filename}: {str(e)}")
            return extracted_tables
    
    def process_single_pdf(self, pdf_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single PDF file with comprehensive extraction
        
        Args:
            pdf_info: Dictionary with PDF file information
            
        Returns:
            Processing results
        """
        key = pdf_info['key']
        filename = pdf_info['filename']
        
        logger.info(f"Processing PDF: {key}")
        
        processing_result = {
            'file_info': pdf_info,
            'success': False,
            'pymupdf_result': None,
            'camelot_result': None,
            'knowledge_extracted': None,
            'nodes_created': 0,
            'processing_time': 0,
            'errors': []
        }
        
        start_time = time.time()
        
        try:
            # Download PDF content
            pdf_content = self.download_pdf_from_s3(key)
            if not pdf_content:
                processing_result['errors'].append("Failed to download PDF")
                return processing_result
            
            # Extract text with PyMuPDF
            logger.info(f"Extracting text with PyMuPDF from {filename}")
            pymupdf_result = self.extract_text_with_pymupdf(pdf_content, filename)
            processing_result['pymupdf_result'] = pymupdf_result
            
            # Extract tables with Camelot
            logger.info(f"Extracting tables with Camelot from {filename}")
            camelot_result = self.extract_tables_with_camelot(pdf_content, filename)
            processing_result['camelot_result'] = camelot_result
            
            # Combine extracted content for knowledge extraction
            combined_content = self._combine_extracted_content(
                pymupdf_result, camelot_result, filename
            )
            
            if combined_content:
                # Extract knowledge using LLM
                logger.info(f"Extracting knowledge from {filename}")
                try:
                    knowledge_result = self.knowledge_extractor.extract_knowledge(
                        combined_content, filename
                    )
                    processing_result['knowledge_extracted'] = knowledge_result
                    
                    # Load into knowledge graph
                    if knowledge_result and knowledge_result.get('entities'):
                        logger.info(f"Loading knowledge into graph for {filename}")
                        nodes_created = self.graph_loader.load_knowledge(
                            knowledge_result, source_file=key
                        )
                        processing_result['nodes_created'] = nodes_created
                        self.stats['created_nodes'] += nodes_created
                
                except Exception as e:
                    logger.error(f"Knowledge extraction failed for {filename}: {e}")
                    processing_result['errors'].append(f"Knowledge extraction failed: {str(e)}")
            
            # Update statistics
            self.stats['extracted_pages'] += pymupdf_result['successful_pages']
            self.stats['extracted_tables'] += camelot_result['table_count']
            
            processing_result['success'] = True
            processing_result['processing_time'] = time.time() - start_time
            
            logger.info(f"Successfully processed {filename} in {processing_result['processing_time']:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            processing_result['errors'].append(f"Processing error: {str(e)}")
            self.stats['processing_errors'].append(f"Processing failed for {filename}: {str(e)}")
        
        return processing_result
    
    def _combine_extracted_content(self, pymupdf_result: Dict, camelot_result: Dict, filename: str) -> str:
        """
        Combine content from PyMuPDF and Camelot extractions
        
        Args:
            pymupdf_result: PyMuPDF extraction result
            camelot_result: Camelot extraction result
            filename: Filename for context
            
        Returns:
            Combined content string
        """
        combined_parts = []
        
        # Add document metadata
        combined_parts.append(f"=== DOCUMENT: {filename} ===")
        
        if pymupdf_result['metadata']:
            combined_parts.append("METADATA:")
            for key, value in pymupdf_result['metadata'].items():
                if value:
                    combined_parts.append(f"  {key}: {value}")
        
        # Add text content
        if pymupdf_result['text_content']:
            combined_parts.append("\n=== TEXT CONTENT ===")
            for page_content in pymupdf_result['text_content']:
                combined_parts.append(f"\nPAGE {page_content['page_num']}:")
                combined_parts.append(page_content['text'])
        
        # Add table content
        if camelot_result['tables']:
            combined_parts.append("\n=== TABLE DATA ===")
            for table in camelot_result['tables']:
                combined_parts.append(f"\nTABLE {table['table_id']} (Page {table['page_num']}):")
                combined_parts.append(f"Method: {table['method']}, Accuracy: {table['accuracy']:.2f}")
                
                if table['data']:
                    # Convert table data to readable format
                    df = pd.DataFrame(table['data'])
                    combined_parts.append(df.to_string(index=False))
        
        return "\n".join(combined_parts)
    
    def process_all_pdfs(self, max_workers: int = 3) -> Dict[str, Any]:
        """
        Process all PDF files in the S3 bucket with parallel processing
        
        Args:
            max_workers: Maximum number of concurrent workers
            
        Returns:
            Processing summary
        """
        logger.info("Starting comprehensive S3 PDF processing")
        
        # Discover all PDF files
        pdf_files = self.discover_all_pdfs()
        
        if not pdf_files:
            logger.warning("No PDF files found in S3 bucket")
            return self.stats
        
        # Process files with parallel execution
        processed_results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all PDF processing tasks
            future_to_pdf = {
                executor.submit(self.process_single_pdf, pdf_info): pdf_info
                for pdf_info in pdf_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pdf):
                pdf_info = future_to_pdf[future]
                try:
                    result = future.result()
                    processed_results.append(result)
                    
                    if result['success']:
                        self.stats['processed_files'] += 1
                        logger.info(f"✅ Successfully processed: {pdf_info['filename']}")
                    else:
                        self.stats['failed_files'] += 1
                        logger.error(f"❌ Failed to process: {pdf_info['filename']}")
                
                except Exception as e:
                    self.stats['failed_files'] += 1
                    logger.error(f"❌ Exception processing {pdf_info['filename']}: {e}")
                    self.stats['processing_errors'].append(f"Exception for {pdf_info['filename']}: {str(e)}")
        
        # Generate final statistics
        final_stats = {
            **self.stats,
            'processing_results': processed_results,
            'success_rate': (self.stats['processed_files'] / self.stats['total_files'] * 100) if self.stats['total_files'] > 0 else 0
        }
        
        logger.info("=== COMPREHENSIVE S3 PROCESSING COMPLETE ===")
        logger.info(f"Total files: {final_stats['total_files']}")
        logger.info(f"Processed successfully: {final_stats['processed_files']}")
        logger.info(f"Failed: {final_stats['failed_files']}")
        logger.info(f"Success rate: {final_stats['success_rate']:.1f}%")
        logger.info(f"Pages extracted: {final_stats['extracted_pages']}")
        logger.info(f"Tables extracted: {final_stats['extracted_tables']}")
        logger.info(f"Knowledge nodes created: {final_stats['created_nodes']}")
        
        return final_stats

def main():
    """Main function for standalone execution"""
    from dotenv import load_dotenv
    from openai import OpenAI 
    from neo4j import GraphDatabase
    
    # Load environment
    load_dotenv()
    
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
    
    # Process all PDFs
    results = processor.process_all_pdfs(max_workers=2)
    
    # Save results
    results_file = Path(__file__).parent.parent.parent / "s3_processing_results.json"
    with open(results_file, 'w') as f:
        # Convert datetime objects to strings for JSON serialization
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Processing results saved to: {results_file}")
    
    # Cleanup
    neo4j_driver.close()

if __name__ == "__main__":
    main()