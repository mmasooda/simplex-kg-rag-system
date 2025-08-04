"""
PDF Parser Module for Simplex Product Documentation
Handles extraction of text and tables from PDF files
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ExtractedDocument:
    """Represents extracted content from a PDF document"""
    filename: str
    text_content: str
    tables: List[pd.DataFrame]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "filename": self.filename,
            "text_content": self.text_content,
            "tables": [table.to_dict(orient="records") for table in self.tables],
            "metadata": self.metadata
        }

class PDFParser:
    """
    Hybrid PDF parser using PyMuPDF for text and simplified table extraction
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def extract_from_pdf(self, pdf_path: Path) -> ExtractedDocument:
        """
        Extract text and tables from a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ExtractedDocument containing extracted content
        """
        try:
            import fitz  # PyMuPDF
            
            self.logger.info(f"Processing PDF: {pdf_path}")
            
            text_content = ""
            tables = []
            
            # Extract text using PyMuPDF
            doc = fitz.open(pdf_path)
            try:
                page_count = len(doc)
                for page_num in range(page_count):
                    page = doc[page_num]
                    text_content += f"\n--- Page {page_num + 1} ---\n"
                    text_content += page.get_text()
            finally:
                doc.close()
            
            # Extract tables using pandas (simplified approach)
            # For production, you would use camelot-py or similar
            tables = self._extract_tables_simple(text_content)
            
            metadata = {
                "page_count": page_count,
                "file_size": pdf_path.stat().st_size,
                "extraction_method": "PyMuPDF"
            }
            
            return ExtractedDocument(
                filename=pdf_path.name,
                text_content=text_content,
                tables=tables,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
    
    def _extract_tables_simple(self, text: str) -> List[pd.DataFrame]:
        """
        Simple table extraction based on text patterns
        This is a placeholder - in production use camelot-py
        """
        tables = []
        
        # Look for table-like patterns in text
        lines = text.split('\n')
        current_table = []
        in_table = False
        
        for line in lines:
            # Simple heuristic: lines with multiple tabs or consistent spacing
            if '\t' in line or '  ' in line:
                if not in_table:
                    in_table = True
                    current_table = []
                current_table.append(line)
            else:
                if in_table and len(current_table) > 2:
                    # Try to parse as table
                    try:
                        df = self._parse_table_lines(current_table)
                        if df is not None and not df.empty:
                            tables.append(df)
                    except:
                        pass
                in_table = False
                current_table = []
        
        return tables
    
    def _parse_table_lines(self, lines: List[str]) -> Optional[pd.DataFrame]:
        """Parse lines into a DataFrame"""
        try:
            # Split by tabs or multiple spaces
            rows = []
            for line in lines:
                if '\t' in line:
                    row = line.split('\t')
                else:
                    row = [x.strip() for x in line.split('  ') if x.strip()]
                if row:
                    rows.append(row)
            
            if rows:
                # Use first row as header
                df = pd.DataFrame(rows[1:], columns=rows[0])
                return df
        except:
            return None
        
        return None

class S3DocumentIngester:
    """
    Handles ingestion of documents from S3 bucket
    """
    
    def __init__(self, s3_client, bucket_name: str):
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.parser = PDFParser()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def ingest_all_documents(self, prefix: str = "") -> List[ExtractedDocument]:
        """
        Ingest all PDF documents from S3 bucket
        
        Args:
            prefix: S3 prefix to filter documents
            
        Returns:
            List of extracted documents
        """
        extracted_docs = []
        
        try:
            # List all objects in bucket
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                self.logger.warning(f"No objects found in bucket {self.bucket_name}")
                return extracted_docs
            
            for obj in response['Contents']:
                if obj['Key'].lower().endswith('.pdf'):
                    try:
                        # Download and process PDF
                        doc = self._process_s3_pdf(obj['Key'])
                        extracted_docs.append(doc)
                    except Exception as e:
                        self.logger.error(f"Failed to process {obj['Key']}: {str(e)}")
            
            self.logger.info(f"Successfully processed {len(extracted_docs)} documents")
            return extracted_docs
            
        except Exception as e:
            self.logger.error(f"Error listing S3 objects: {str(e)}")
            raise
    
    def _process_s3_pdf(self, s3_key: str) -> ExtractedDocument:
        """Download and process a single PDF from S3"""
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp_file:
            # Download from S3
            self.logger.info(f"Downloading {s3_key} from S3")
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                tmp_file.name
            )
            
            # Parse PDF
            doc = self.parser.extract_from_pdf(Path(tmp_file.name))
            doc.metadata['s3_key'] = s3_key
            
            return doc
    
    def save_extracted_documents(self, documents: List[ExtractedDocument], output_dir: Path):
        """Save extracted documents to JSON files"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for doc in documents:
            output_file = output_dir / f"{doc.filename}.json"
            with open(output_file, 'w') as f:
                json.dump(doc.to_dict(), f, indent=2)
            
            self.logger.info(f"Saved extracted content to {output_file}")