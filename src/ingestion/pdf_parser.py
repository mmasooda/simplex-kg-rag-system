"""
PDF Parser Module for Simplex Product Documentation
Handles extraction of text and tables from PDF files with advanced table extraction
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
from dataclasses import dataclass, asdict
import camelot
import tabula

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
    Advanced PDF parser using PyMuPDF for text and camelot/tabula for table extraction
    """
    
    def __init__(self, use_advanced_tables: bool = True):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.use_advanced_tables = use_advanced_tables
        
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
            
            # Extract tables using advanced methods
            if self.use_advanced_tables:
                tables = self._extract_tables_advanced(pdf_path)
            else:
                tables = self._extract_tables_simple(text_content)
            
            metadata = {
                "page_count": page_count,
                "file_size": pdf_path.stat().st_size,
                "extraction_method": "PyMuPDF + Advanced Tables" if self.use_advanced_tables else "PyMuPDF",
                "tables_found": len(tables)
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
    
    def _extract_tables_advanced(self, pdf_path: Path) -> List[pd.DataFrame]:
        """
        Advanced table extraction using camelot and tabula libraries
        """
        tables = []
        
        try:
            # Method 1: Try camelot (lattice method for tables with clear borders)
            self.logger.info(f"Attempting camelot lattice extraction from {pdf_path}")
            camelot_tables = camelot.read_pdf(str(pdf_path), flavor='lattice', pages='all')
            
            for table in camelot_tables:
                if table.df is not None and not table.df.empty:
                    # Clean the table
                    cleaned_df = self._clean_table(table.df)
                    if cleaned_df is not None and not cleaned_df.empty:
                        tables.append(cleaned_df)
                        self.logger.info(f"Camelot found table with shape {cleaned_df.shape}")
            
        except Exception as e:
            self.logger.warning(f"Camelot lattice extraction failed: {e}")
        
        try:
            # Method 2: Try camelot stream method (for tables without borders)  
            self.logger.info(f"Attempting camelot stream extraction from {pdf_path}")
            camelot_stream = camelot.read_pdf(str(pdf_path), flavor='stream', pages='all')
            
            for table in camelot_stream:
                if table.df is not None and not table.df.empty:
                    cleaned_df = self._clean_table(table.df)
                    if cleaned_df is not None and not cleaned_df.empty and not self._is_duplicate_table(cleaned_df, tables):
                        tables.append(cleaned_df)
                        self.logger.info(f"Camelot stream found table with shape {cleaned_df.shape}")
                        
        except Exception as e:
            self.logger.warning(f"Camelot stream extraction failed: {e}")
        
        try:
            # Method 3: Try tabula as fallback
            self.logger.info(f"Attempting tabula extraction from {pdf_path}")
            tabula_tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
            
            for table in tabula_tables:
                if table is not None and not table.empty:
                    cleaned_df = self._clean_table(table)
                    if cleaned_df is not None and not cleaned_df.empty and not self._is_duplicate_table(cleaned_df, tables):
                        tables.append(cleaned_df)
                        self.logger.info(f"Tabula found table with shape {cleaned_df.shape}")
                        
        except Exception as e:
            self.logger.warning(f"Tabula extraction failed: {e}")
        
        # If advanced methods fail, fallback to simple extraction
        if not tables:
            self.logger.info("Advanced table extraction found no tables, falling back to simple method")
            # Read text for fallback
            try:
                import fitz
                doc = fitz.open(pdf_path)
                text_content = ""
                for page_num in range(len(doc)):
                    text_content += doc[page_num].get_text()
                doc.close()
                tables = self._extract_tables_simple(text_content)
            except Exception as e:
                self.logger.error(f"Fallback simple extraction also failed: {e}")
        
        self.logger.info(f"Total tables extracted: {len(tables)}")
        return tables
    
    def _clean_table(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Clean and validate extracted table"""
        try:
            # Remove empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            # Skip tables that are too small
            if df.shape[0] < 2 or df.shape[1] < 2:
                return None
            
            # Remove header/footer rows that might be page numbers or repeated headers
            if df.shape[0] > 3:
                # Check if first/last rows contain only page numbers or common headers
                first_row_str = ' '.join(str(df.iloc[0]).lower())
                last_row_str = ' '.join(str(df.iloc[-1]).lower())
                
                if any(word in first_row_str for word in ['page', 'simplex', 'product', 'catalog']):
                    df = df.iloc[1:]
                if any(word in last_row_str for word in ['page', 'www.', 'simplex']):
                    df = df.iloc[:-1]
            
            # Reset index
            df = df.reset_index(drop=True)
            
            # Set first row as header if it looks like a header
            if df.shape[0] > 1:
                first_row = df.iloc[0].astype(str).str.lower()
                if any(header_word in ' '.join(first_row) for header_word in ['sku', 'model', 'product', 'part', 'description', 'type']):
                    df.columns = df.iloc[0]
                    df = df.iloc[1:].reset_index(drop=True)
            
            return df if not df.empty else None
            
        except Exception as e:
            self.logger.warning(f"Error cleaning table: {e}")
            return None
    
    def _is_duplicate_table(self, new_table: pd.DataFrame, existing_tables: List[pd.DataFrame]) -> bool:
        """Check if table is a duplicate of existing tables"""
        try:
            for existing in existing_tables:
                # Compare shapes
                if new_table.shape == existing.shape:
                    # Compare content similarity (first few cells)
                    if new_table.shape[0] > 0 and new_table.shape[1] > 0:
                        new_sample = str(new_table.iloc[0, 0])[:50]
                        existing_sample = str(existing.iloc[0, 0])[:50]
                        if new_sample == existing_sample:
                            return True
            return False
        except:
            return False
    
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