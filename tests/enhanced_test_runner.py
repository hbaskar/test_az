#!/usr/bin/env python3
"""
Enhanced Azure Function Test Runner
==================================

Provides comprehensive testing capabilities for Azure Functions with:
- Interactive test selection
- Command-line test execution
- Enhanced error handling and diagnostics
- Retry logic for flaky tests
- Detailed reporting and logging

Usage:
    python enhanced_test_runner.py              # Interactive mode
    python enhanced_test_runner.py health       # Run health check
    python enhanced_test_runner.py employee     # Run employee PDF test
    python enhanced_test_runner.py retry        # Run with retry logic
    python enhanced_test_runner.py all          # Run all tests
"""

import requests
import base64
import json
import os
import sys
import time
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# PDF processing imports
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️ PyPDF2 not available. PDF text extraction will be limited.")

try:
    import io
    IO_AVAILABLE = True
except ImportError:
    IO_AVAILABLE = False

class ChunkDatabaseManager:
    """Manages SQLite database for chunk preprocessing and tracking"""
    
    def __init__(self, db_path: str = "chunks_preprocessing.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT UNIQUE,
                    content_preview TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP NULL,
                    processing_status TEXT DEFAULT 'pending'
                )
            """)
            
            # Create chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    chunk_index INTEGER,
                    chunk_content TEXT,
                    chunk_size INTEGER,
                    chunk_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    upload_status TEXT DEFAULT 'pending',
                    error_message TEXT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
            
            # Create processing_sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_end TIMESTAMP NULL,
                    total_chunks INTEGER,
                    successful_chunks INTEGER DEFAULT 0,
                    failed_chunks INTEGER DEFAULT 0,
                    processing_time_seconds REAL NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
            
            # Create azure_function_chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS azure_function_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    document_id INTEGER,
                    azure_chunk_index INTEGER,
                    azure_chunk_content TEXT,
                    azure_chunk_size INTEGER,
                    azure_chunk_hash TEXT,
                    upload_status TEXT DEFAULT 'pending',
                    error_message TEXT NULL,
                    processing_time_ms REAL NULL,
                    key_phrases TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES processing_sessions (id),
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
            
            conn.commit()
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
    
    def add_document(self, filename: str, file_content: bytes) -> Tuple[int, bool]:
        """Add document to database and return (document_id, is_new)"""
        file_hash = self.calculate_file_hash(file_content)
        file_size = len(file_content)
        
        # Create content preview (first 200 chars of decoded content)
        try:
            content_preview = file_content.decode('utf-8', errors='ignore')[:200] + '...'
        except:
            content_preview = f"Binary file ({file_size} bytes)"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if document already exists
            cursor.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,))
            existing = cursor.fetchone()
            
            if existing:
                return existing[0], False  # Return existing document ID and False (not new)
            
            # Insert new document
            cursor.execute("""
                INSERT INTO documents (filename, file_size, file_hash, content_preview)
                VALUES (?, ?, ?, ?)
            """, (filename, file_size, file_hash, content_preview))
            
            conn.commit()
            return cursor.lastrowid, True  # Return new document ID and True (is new)
    
    def add_chunks(self, document_id: int, chunks: List[str], preserve_existing: bool = True) -> List[int]:
        """Add chunks to database and return list of chunk_ids"""
        chunk_ids = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if preserve_existing:
                # Check if chunks already exist for this document
                cursor.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (document_id,))
                existing_count = cursor.fetchone()[0]
                
                if existing_count > 0:
                    # Return existing chunk IDs instead of creating duplicates
                    cursor.execute("SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,))
                    existing_chunks = cursor.fetchall()
                    return [chunk[0] for chunk in existing_chunks]
            
            for i, chunk_content in enumerate(chunks):
                chunk_hash = hashlib.sha256(chunk_content.encode('utf-8')).hexdigest()
                chunk_size = len(chunk_content)
                
                # Check for duplicate chunk by hash (optional extra safety)
                if preserve_existing:
                    cursor.execute("SELECT id FROM chunks WHERE chunk_hash = ?", (chunk_hash,))
                    existing_chunk = cursor.fetchone()
                    if existing_chunk:
                        chunk_ids.append(existing_chunk[0])
                        continue
                
                cursor.execute("""
                    INSERT INTO chunks (document_id, chunk_index, chunk_content, chunk_size, chunk_hash)
                    VALUES (?, ?, ?, ?, ?)
                """, (document_id, i, chunk_content, chunk_size, chunk_hash))
                
                chunk_ids.append(cursor.lastrowid)
            
            conn.commit()
        
        return chunk_ids
    
    def start_processing_session(self, document_id: int, total_chunks: int) -> int:
        """Start a processing session and return session_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processing_sessions (document_id, total_chunks)
                VALUES (?, ?)
            """, (document_id, total_chunks))
            conn.commit()
            return cursor.lastrowid
    
    def update_chunk_status(self, chunk_id: int, status: str, error_message: str = None):
        """Update chunk processing status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chunks 
                SET upload_status = ?, error_message = ?
                WHERE id = ?
            """, (status, error_message, chunk_id))
            conn.commit()
    
    def end_processing_session(self, session_id: int, successful: int, failed: int):
        """End processing session with results"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Calculate processing time
            cursor.execute("SELECT session_start FROM processing_sessions WHERE id = ?", (session_id,))
            start_time = cursor.fetchone()[0]
            
            processing_time = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds()
            
            cursor.execute("""
                UPDATE processing_sessions 
                SET session_end = CURRENT_TIMESTAMP, 
                    successful_chunks = ?, 
                    failed_chunks = ?,
                    processing_time_seconds = ?
                WHERE id = ?
            """, (successful, failed, processing_time, session_id))
            conn.commit()
    
    def get_preprocessing_stats(self, document_id: int = None) -> Dict:
        """Get preprocessing statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if document_id:
                # Stats for specific document
                cursor.execute("""
                    SELECT 
                        d.filename,
                        d.file_size,
                        COUNT(c.id) as total_chunks,
                        AVG(c.chunk_size) as avg_chunk_size,
                        MAX(c.chunk_size) as max_chunk_size,
                        MIN(c.chunk_size) as min_chunk_size
                    FROM documents d
                    LEFT JOIN chunks c ON d.id = c.document_id
                    WHERE d.id = ?
                    GROUP BY d.id
                """, (document_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'filename': result[0],
                        'file_size': result[1],
                        'total_chunks': result[2],
                        'avg_chunk_size': round(result[3] or 0, 2),
                        'max_chunk_size': result[4] or 0,
                        'min_chunk_size': result[5] or 0
                    }
            else:
                # Overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT d.id) as total_documents,
                        COUNT(c.id) as total_chunks,
                        AVG(c.chunk_size) as avg_chunk_size,
                        SUM(d.file_size) as total_file_size
                    FROM documents d
                    LEFT JOIN chunks c ON d.id = c.document_id
                """)
                
                result = cursor.fetchone()
                return {
                    'total_documents': result[0] or 0,
                    'total_chunks': result[1] or 0,
                    'avg_chunk_size': round(result[2] or 0, 2),
                    'total_file_size': result[3] or 0
                }
        
        return {}
    
    def get_failed_chunks(self, document_id: int = None) -> List[Dict]:
        """Get details of failed chunks"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    c.id, c.chunk_index, c.chunk_content, c.error_message, d.filename
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.upload_status = 'failed'
            """
            
            params = []
            if document_id:
                query += " AND d.id = ?"
                params.append(document_id)
            
            query += " ORDER BY d.filename, c.chunk_index"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return [
                {
                    'chunk_id': row[0],
                    'chunk_index': row[1],
                    'content_preview': row[2][:100] + '...' if row[2] else '',
                    'error_message': row[3],
                    'filename': row[4]
                }
                for row in results
            ]
    
    def reset_database(self, confirm: bool = False) -> bool:
        """Reset/clear all database tables"""
        if not confirm:
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear all tables (order matters due to foreign keys)
                cursor.execute("DELETE FROM azure_function_chunks")
                cursor.execute("DELETE FROM processing_sessions")
                cursor.execute("DELETE FROM chunks") 
                cursor.execute("DELETE FROM documents")
                
                # Reset auto-increment counters
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('documents', 'chunks', 'processing_sessions', 'azure_function_chunks')")
                
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error resetting database: {str(e)}")
            return False
    
    def get_database_size_info(self) -> Dict:
        """Get database size and table information"""
        import os
        
        info = {
            'file_size_bytes': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
            'file_path': self.db_path
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table counts
                tables = ['documents', 'chunks', 'processing_sessions']
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    info[f'{table}_count'] = cursor.fetchone()[0]
                
                # Get total size estimate
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                result = cursor.fetchone()
                info['database_size_bytes'] = result[0] if result else 0
                
        except Exception as e:
            info['error'] = str(e)
        
        return info
    
    def get_all_documents(self) -> List[Dict]:
        """Get all documents from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, file_size, file_hash, content_preview, 
                       created_at, processed_at, processing_status
                FROM documents 
                ORDER BY created_at DESC
            """)
            
            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'filename': row[1],
                    'file_size': row[2],
                    'file_hash': row[3][:12] + '...' if row[3] else '',
                    'content_preview': row[4],
                    'created_at': row[5],
                    'processed_at': row[6],
                    'processing_status': row[7]
                }
                for row in results
            ]
    
    def get_document_chunks(self, document_id: int) -> List[Dict]:
        """Get all chunks for a specific document"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, chunk_index, chunk_content, chunk_size, chunk_hash,
                       created_at, upload_status, error_message
                FROM chunks 
                WHERE document_id = ?
                ORDER BY chunk_index
            """, (document_id,))
            
            results = cursor.fetchall()
            return [
                {
                    'chunk_id': row[0],
                    'chunk_index': row[1],
                    'content_preview': row[2][:150] + '...' if len(row[2]) > 150 else row[2],
                    'full_content': row[2],
                    'chunk_size': row[3],
                    'chunk_hash': row[4][:12] + '...' if row[4] else '',
                    'created_at': row[5],
                    'upload_status': row[6],
                    'error_message': row[7]
                }
                for row in results
            ]
    
    def get_processing_sessions(self, document_id: int = None) -> List[Dict]:
        """Get processing sessions"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if document_id:
                query = """
                    SELECT ps.id, ps.document_id, d.filename, ps.session_start, 
                           ps.session_end, ps.total_chunks, ps.successful_chunks, 
                           ps.failed_chunks, ps.processing_time_seconds
                    FROM processing_sessions ps
                    JOIN documents d ON ps.document_id = d.id
                    WHERE ps.document_id = ?
                    ORDER BY ps.session_start DESC
                """
                cursor.execute(query, (document_id,))
            else:
                query = """
                    SELECT ps.id, ps.document_id, d.filename, ps.session_start, 
                           ps.session_end, ps.total_chunks, ps.successful_chunks, 
                           ps.failed_chunks, ps.processing_time_seconds
                    FROM processing_sessions ps
                    JOIN documents d ON ps.document_id = d.id
                    ORDER BY ps.session_start DESC
                """
                cursor.execute(query)
            
            results = cursor.fetchall()
            return [
                {
                    'session_id': row[0],
                    'document_id': row[1],
                    'filename': row[2],
                    'session_start': row[3],
                    'session_end': row[4],
                    'total_chunks': row[5],
                    'successful_chunks': row[6],
                    'failed_chunks': row[7],
                    'processing_time_seconds': row[8]
                }
                for row in results
            ]
    
    def add_azure_function_chunks(self, session_id: int, document_id: int, azure_chunks: List[Dict]) -> List[int]:
        """Add Azure Function chunks to tracking table"""
        chunk_ids = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for chunk_data in azure_chunks:
                chunk_content = chunk_data.get('content', '')
                chunk_index = chunk_data.get('index', 0)
                chunk_size = len(chunk_content)
                chunk_hash = hashlib.sha256(chunk_content.encode('utf-8')).hexdigest()
                
                cursor.execute("""
                    INSERT INTO azure_function_chunks 
                    (session_id, document_id, azure_chunk_index, azure_chunk_content, 
                     azure_chunk_size, azure_chunk_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, document_id, chunk_index, chunk_content, chunk_size, chunk_hash))
                
                chunk_ids.append(cursor.lastrowid)
            
            conn.commit()
        
        return chunk_ids
    
    def update_azure_chunk_status(self, azure_chunk_id: int, status: str, 
                                 error_message: str = None, processing_time_ms: float = None,
                                 key_phrases: str = None):
        """Update Azure Function chunk processing status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE azure_function_chunks 
                SET upload_status = ?, error_message = ?, processing_time_ms = ?, key_phrases = ?
                WHERE id = ?
            """, (status, error_message, processing_time_ms, key_phrases, azure_chunk_id))
            conn.commit()
    
    def get_azure_function_chunks(self, session_id: int = None, document_id: int = None) -> List[Dict]:
        """Get Azure Function chunks with their processing status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT afc.id, afc.session_id, afc.document_id, d.filename,
                       afc.azure_chunk_index, afc.azure_chunk_content, afc.azure_chunk_size,
                       afc.upload_status, afc.error_message, afc.processing_time_ms,
                       afc.key_phrases, afc.created_at
                FROM azure_function_chunks afc
                JOIN documents d ON afc.document_id = d.id
            """
            
            conditions = []
            params = []
            
            if session_id:
                conditions.append("afc.session_id = ?")
                params.append(session_id)
            
            if document_id:
                conditions.append("afc.document_id = ?")
                params.append(document_id)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY afc.document_id, afc.azure_chunk_index"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return [
                {
                    'azure_chunk_id': row[0],
                    'session_id': row[1],
                    'document_id': row[2],
                    'filename': row[3],
                    'azure_chunk_index': row[4],
                    'content_preview': row[5][:150] + '...' if len(row[5]) > 150 else row[5],
                    'full_content': row[5],
                    'azure_chunk_size': row[6],
                    'upload_status': row[7],
                    'error_message': row[8],
                    'processing_time_ms': row[9],
                    'key_phrases': row[10],
                    'created_at': row[11]
                }
                for row in results
            ]
    
    def get_failed_azure_chunks(self, session_id: int = None, document_id: int = None) -> List[Dict]:
        """Get details of failed Azure Function chunks"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT afc.id, afc.azure_chunk_index, afc.azure_chunk_content, 
                       afc.error_message, d.filename, afc.session_id
                FROM azure_function_chunks afc
                JOIN documents d ON afc.document_id = d.id
                WHERE afc.upload_status = 'failed'
            """
            
            params = []
            if session_id:
                query += " AND afc.session_id = ?"
                params.append(session_id)
            
            if document_id:
                query += " AND afc.document_id = ?"
                params.append(document_id)
            
            query += " ORDER BY d.filename, afc.azure_chunk_index"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return [
                {
                    'azure_chunk_id': row[0],
                    'azure_chunk_index': row[1],
                    'content_preview': row[2][:100] + '...' if row[2] else '',
                    'error_message': row[3],
                    'filename': row[4],
                    'session_id': row[5]
                }
                for row in results
            ]

class AzureFunctionTester:
    """Enhanced Azure Function testing class with comprehensive capabilities"""
    
    def __init__(self, base_url: str = "http://localhost:7071", verbose: bool = False, 
                 enable_db: bool = True):
        """Initialize the tester with base URL, verbose mode, and database support"""
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.verbose = verbose
        self.enable_db = enable_db
        
        # Initialize database if enabled
        if self.enable_db:
            self.db = ChunkDatabaseManager()
            self.log_info("📊 Database initialization complete")
        else:
            self.db = None
        
        # Test statistics
        self.stats = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    def log_success(self, message: str):
        """Log success message with formatting"""
        print(f"✅ {message}")
    
    def log_error(self, message: str):
        """Log error message with formatting"""
        print(f"❌ {message}")
    
    def log_info(self, message: str):
        """Log info message with formatting"""
        print(f"ℹ️ {message}")
    
    def log_warning(self, message: str):
        """Log warning message with formatting"""
        print(f"⚠️ {message}")
    
    def log_debug(self, message: str):
        """Log debug message with formatting (only in verbose mode)"""
        if self.verbose:
            print(f"🔍 {message}")
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text content from PDF bytes"""
        if not PDF_AVAILABLE or not IO_AVAILABLE:
            self.log_warning("PDF text extraction not available - PyPDF2 or io module missing")
            return "PDF content extraction not available"
        
        try:
            # Create a BytesIO object from the PDF bytes
            pdf_file = io.BytesIO(file_bytes)
            
            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from all pages
            text_content = ""
            total_pages = len(pdf_reader.pages)
            
            self.log_debug(f"PDF has {total_pages} pages")
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():  # Only add non-empty pages
                        text_content += f"\n--- Page {page_num + 1} ---\n"
                        text_content += page_text
                        text_content += "\n"
                    
                    self.log_debug(f"Extracted {len(page_text)} characters from page {page_num + 1}")
                    
                except Exception as e:
                    self.log_warning(f"Failed to extract text from page {page_num + 1}: {str(e)}")
                    continue
            
            if text_content.strip():
                self.log_success(f"Successfully extracted {len(text_content)} characters from PDF")
                return text_content.strip()
            else:
                self.log_warning("No text content found in PDF - may be image-based or protected")
                return "No extractable text content found in PDF"
                
        except Exception as e:
            self.log_error(f"Error extracting PDF text: {str(e)}")
            return f"PDF text extraction failed: {str(e)}"
    
    def get_file_text_content(self, file_path: str, file_bytes: bytes) -> str:
        """Get text content from file based on its type"""
        filename = os.path.basename(file_path).lower()
        
        # Handle PDF files
        if filename.endswith('.pdf'):
            self.log_info("📄 Extracting text from PDF...")
            return self.extract_text_from_pdf(file_bytes)
        
        # Handle text files
        elif filename.endswith(('.txt', '.md', '.json', '.csv', '.log')):
            try:
                return file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return file_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    return f"Text file encoding not supported ({len(file_bytes)} bytes)"
        
        # Handle other document types that might have text
        elif filename.endswith(('.docx', '.doc', '.rtf')):
            self.log_warning("Word document detected - text extraction not implemented")
            return f"Word document content ({len(file_bytes)} bytes) - text extraction not available"
        
        # Handle unknown/binary files
        else:
            self.log_warning(f"Unknown file type: {filename}")
            return f"Binary file content ({len(file_bytes)} bytes) - text extraction not available"
    
    def show_response_details(self, response, max_length: int = 1000):
        """Show detailed response information for debugging"""
        if not self.verbose:
            return
            
        self.log_debug("Response Details:")
        self.log_info(f"Status Code: {response.status_code}")
        self.log_info(f"Headers: {dict(response.headers)}")
        
        content = response.text
        if len(content) > max_length:
            self.log_info(f"Response Content (first {max_length} chars): {content[:max_length]}...")
        else:
            self.log_info(f"Response Content: {content}")
    
    def start_test_session(self):
        """Start a test session and initialize statistics"""
        self.stats['start_time'] = time.time()
        self.stats['tests_run'] = 0
        self.stats['tests_passed'] = 0
        self.stats['tests_failed'] = 0
        print("🧪 Starting Azure Function Test Session")
        print("=" * 50)
    
    def end_test_session(self):
        """End test session and display summary"""
        self.stats['end_time'] = time.time()
        duration = self.stats['end_time'] - self.stats['start_time']
        
        print("\n" + "=" * 50)
        print("📊 Test Session Summary")
        print("=" * 50)
        print(f"Total Tests: {self.stats['tests_run']}")
        print(f"Passed: {self.stats['tests_passed']} ✅")
        print(f"Failed: {self.stats['tests_failed']} ❌")
        print(f"Duration: {duration:.2f} seconds")
        
        if self.stats['tests_failed'] == 0 and self.stats['tests_run'] > 0:
            print("🎉 All tests passed!")
        elif self.stats['tests_failed'] > 0:
            print(f"🔧 {self.stats['tests_failed']} test(s) need attention")
    
    def record_test_result(self, test_name: str, passed: bool):
        """Record test result in statistics"""
        self.stats['tests_run'] += 1
        if passed:
            self.stats['tests_passed'] += 1
            self.log_success(f"Test '{test_name}' passed")
        else:
            self.stats['tests_failed'] += 1
            self.log_error(f"Test '{test_name}' failed")
    
    def test_health_check(self) -> bool:
        """Test the health endpoint of the Azure Function"""
        print("🔍 Testing Azure Function Health...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/process-document", timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.log_success("Function is healthy and responsive")
                    self.log_info(f"Status: {data.get('status', 'Unknown')}")
                    return True
                except json.JSONDecodeError:
                    self.log_success("Function is responsive (non-JSON response)")
                    return True
            else:
                self.log_error(f"Health check failed with status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            self.log_error("Cannot connect to Azure Function")
            self.log_info("Make sure the function is running on http://localhost:7071")
            self.log_info("Run: func host start")
            return False
        except requests.exceptions.Timeout:
            self.log_error("Health check timed out")
            return False
        except Exception as e:
            self.log_error(f"Unexpected error during health check: {str(e)}")
            return False
    
    def encode_file_to_base64(self, file_path: str) -> Optional[str]:
        """Encode a file to base64 string"""
        try:
            with open(file_path, 'rb') as file:
                return base64.b64encode(file.read()).decode('utf-8')
        except Exception as e:
            self.log_error(f"Failed to encode file {file_path}: {str(e)}")
            return None
    
    def simulate_chunk_preprocessing(self, file_content: str, filename: str) -> List[str]:
        """
        Simulate chunk creation preprocessing step
        This mimics how the Azure Function would break down the document
        """
        # Handle empty or minimal content
        if not file_content or len(file_content.strip()) < 50:
            self.log_warning("File content too short for meaningful chunking")
            return [file_content] if file_content else ["Empty file content"]
        
        # Chunking strategy based on file type
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            # PDF-specific chunking - handle page breaks and sections
            max_chunk_size = 1500  # PDFs often have more dense content
            min_chunk_size = 200   # Longer minimum for meaningful PDF chunks
            
            # First try to split by page markers
            if "--- Page" in file_content:
                page_sections = file_content.split("--- Page")
                chunks = []
                current_chunk = ""
                
                for section in page_sections:
                    section = section.strip()
                    if not section:
                        continue
                    
                    # If this is a page marker line, add it to track pages
                    if section.split('\n')[0].strip().endswith('---'):
                        page_header = "--- Page" + section.split('\n')[0]
                        section_content = '\n'.join(section.split('\n')[1:])
                    else:
                        page_header = ""
                        section_content = section
                    
                    # Add page content in chunks
                    paragraphs = section_content.split('\n\n')
                    for paragraph in paragraphs:
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                        
                        full_paragraph = f"{page_header}\n{paragraph}" if page_header else paragraph
                        page_header = ""  # Only add header to first paragraph of page
                        
                        if len(current_chunk) + len(full_paragraph) + 2 > max_chunk_size and len(current_chunk) >= min_chunk_size:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = full_paragraph
                        else:
                            if current_chunk:
                                current_chunk += "\n\n" + full_paragraph
                            else:
                                current_chunk = full_paragraph
                
                # Add final chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                # Fall back to paragraph-based chunking for PDFs
                chunks = self._chunk_by_paragraphs(file_content, max_chunk_size, min_chunk_size)
        else:
            # Standard text file chunking
            max_chunk_size = 1000
            min_chunk_size = 100
            chunks = self._chunk_by_paragraphs(file_content, max_chunk_size, min_chunk_size)
        
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]
        
        if not chunks:
            chunks = [file_content[:1000] + "..." if len(file_content) > 1000 else file_content]
        
        self.log_info(f"📄 Preprocessed into {len(chunks)} chunks")
        if self.verbose:
            for i, chunk in enumerate(chunks):
                preview = chunk[:150] + '...' if len(chunk) > 150 else chunk
                self.log_debug(f"Chunk {i+1}: {len(chunk)} chars - {preview}")
        
        return chunks
    
    def _chunk_by_paragraphs(self, content: str, max_size: int, min_size: int) -> List[str]:
        """Helper method for paragraph-based chunking"""
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            if len(current_chunk) + len(paragraph) + 2 > max_size and len(current_chunk) >= min_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the last chunk
        if current_chunk and len(current_chunk) >= min_size:
            chunks.append(current_chunk.strip())
        elif current_chunk and chunks:
            chunks[-1] += "\n\n" + current_chunk.strip()
        elif current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _capture_azure_function_chunks(self, azure_response: Dict, session_id: int, document_id: int):
        """Capture and store Azure Function chunks from the response for tracking"""
        try:
            self.log_debug("📊 Capturing Azure Function chunks for analysis...")
            
            # Parse chunks from different possible response formats
            azure_chunks = []
            
            # Check for chunks in various response formats
            if 'chunks' in azure_response and isinstance(azure_response['chunks'], list):
                # Format: {"chunks": [{"content": "...", "index": 0}, ...]}
                azure_chunks = azure_response['chunks']
            elif 'chunk_details' in azure_response and isinstance(azure_response['chunk_details'], list):
                # Format: {"chunk_details": [{"content": "...", "chunk_id": "doc_1", "title": "...", "status": "success"}, ...]}
                azure_chunks = []
                for i, chunk in enumerate(azure_response['chunk_details']):
                    # Extract chunk ID number from string like "doc_1" or use index
                    chunk_id = chunk.get('chunk_id', str(i))
                    try:
                        # Try to extract number from chunk_id like "filename_3" -> 3
                        index = int(chunk_id.split('_')[-1]) if '_' in chunk_id else int(chunk_id)
                    except (ValueError, IndexError):
                        index = i
                    
                    azure_chunks.append({
                        'content': chunk.get('content', ''),
                        'title': chunk.get('title', ''),
                        'index': index - 1,  # Convert to 0-based index
                        'status': chunk.get('status', 'unknown'),
                        'error': chunk.get('error'),
                        'keyphrases': chunk.get('keyphrases', []),
                        'content_size': chunk.get('content_size', len(chunk.get('content', '')))
                    })
            elif 'failed_chunk_details' in azure_response:
                # At least capture failed chunks
                failed_chunks = azure_response['failed_chunk_details']
                azure_chunks = [
                    {
                        'content': chunk.get('content', ''),
                        'index': int(chunk.get('chunk_id', i)) if chunk.get('chunk_id') else i,
                        'status': 'failed',
                        'error': chunk.get('error', 'Unknown error')
                    }
                    for i, chunk in enumerate(failed_chunks)
                ]
            else:
                # Try to infer chunks from summary info
                chunks_created = azure_response.get('chunks_created', 0)
                successful = azure_response.get('successful_uploads', 0)
                failed = azure_response.get('failed_uploads', 0)
                
                if chunks_created > 0:
                    self.log_info(f"🔍 Inferring {chunks_created} chunks from summary (no detailed chunk data available)")
                    # Create placeholder entries for tracking
                    for i in range(chunks_created):
                        status = 'failed' if i >= successful else 'success'
                        azure_chunks.append({
                            'content': f'Azure Function Chunk {i+1} (content not available)',
                            'index': i,
                            'status': status,
                            'error': 'Chunk processing failed' if status == 'failed' else None
                        })
            
            if azure_chunks:
                # Store Azure Function chunks
                chunk_ids = self.db.add_azure_function_chunks(session_id, document_id, azure_chunks)
                
                # Update statuses for chunks that have status information
                for i, (chunk_data, chunk_id) in enumerate(zip(azure_chunks, chunk_ids)):
                    status = chunk_data.get('status', 'pending')
                    error_message = chunk_data.get('error')
                    
                    if status != 'pending':
                        self.db.update_azure_chunk_status(
                            chunk_id, 
                            status, 
                            error_message=error_message
                        )
                
                self.log_success(f"📊 Captured {len(azure_chunks)} Azure Function chunks for analysis")
                
                # Show chunk analysis
                success_count = sum(1 for chunk in azure_chunks if chunk.get('status') == 'success')
                failed_count = sum(1 for chunk in azure_chunks if chunk.get('status') == 'failed')
                pending_count = len(azure_chunks) - success_count - failed_count
                
                self.log_info(f"   ✅ Successful: {success_count}")
                if failed_count > 0:
                    self.log_warning(f"   ❌ Failed: {failed_count}")
                if pending_count > 0:
                    self.log_info(f"   ⏳ Pending: {pending_count}")
            else:
                self.log_warning("⚠️ No Azure Function chunk details found in response")
                
        except Exception as e:
            self.log_error(f"Error capturing Azure Function chunks: {str(e)}")
    
    def preprocess_and_store_chunks(self, file_path: str) -> Optional[Dict]:
        """
        Preprocess file into chunks and store in database before Azure Function processing
        Returns document_id and chunk information
        """
        if not self.enable_db:
            self.log_warning("Database not enabled - skipping preprocessing step")
            return None
        
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            # Extract text content based on file type
            filename = os.path.basename(file_path)
            file_content = self.get_file_text_content(file_path, file_bytes)
            
            # Store document in database
            self.log_info("💾 Storing document in preprocessing database...")
            file_hash = self.db.calculate_file_hash(file_bytes)
            self.log_debug(f"File hash: {file_hash[:12]}...")
            document_id, is_new_document = self.db.add_document(filename, file_bytes)
            
            if is_new_document:
                # Create chunks only for new documents
                self.log_info("⚙️ Creating chunks in preprocessing step...")
                chunks = self.simulate_chunk_preprocessing(file_content, filename)
                
                # Store chunks in database
                chunk_ids = self.db.add_chunks(document_id, chunks, preserve_existing=True)
                
                self.log_success("✅ Preprocessing complete - new document processed!")
                self.log_info(f"Document ID: {document_id} (NEW)")
                self.log_info(f"Total chunks created: {len(chunks)}")
            else:
                # Document already exists, get existing chunks
                self.log_info("📋 Document already exists in database - reusing existing chunks...")
                chunk_ids = self.db.add_chunks(document_id, [], preserve_existing=True)  # Will return existing chunk IDs
                chunks = []  # We don't need to recreate chunks for existing docs
                
                self.log_success("✅ Preprocessing complete - reusing existing document and chunks!")
                self.log_info(f"Document ID: {document_id} (EXISTING - NO DUPLICATES CREATED)")
                self.log_info(f"Total existing chunks reused: {len(chunk_ids)}")
            
            # Get preprocessing stats
            stats = self.db.get_preprocessing_stats(document_id)
            
            self.log_info(f"Average chunk size: {stats.get('avg_chunk_size', 0)} chars")
            self.log_info(f"Chunk size range: {stats.get('min_chunk_size', 0)} - {stats.get('max_chunk_size', 0)} chars")
            
            return {
                'document_id': document_id,
                'total_chunks': len(chunk_ids),  # Use chunk_ids length for both new and existing
                'chunk_ids': chunk_ids,
                'stats': stats,
                'is_new_document': is_new_document
            }
            
        except Exception as e:
            self.log_error(f"Error during preprocessing: {str(e)}")
            return None
    
    def test_document_processing(self, file_path: Optional[str] = None, 
                               force_reindex: bool = False) -> bool:
        """Test document processing endpoint with preprocessing"""
        print(f"📄 Testing Document Processing...")
        
        # Create test file if none provided
        if file_path is None:
            file_path = self.create_test_file()
        
        if not os.path.exists(file_path):
            self.log_error(f"Test file not found: {file_path}")
            return False
        
        # Get file information
        file_size = os.path.getsize(file_path)
        self.log_info(f"Processing file: {file_path}")
        self.log_info(f"File size: {file_size:,} bytes")
        
        # PREPROCESSING STEP: Create and store chunks before Azure Function processing
        preprocessing_result = None
        processing_session_id = None
        
        if self.enable_db:
            print("\n🔧 PREPROCESSING STEP:")
            print("=" * 30)
            preprocessing_result = self.preprocess_and_store_chunks(file_path)
            
            if preprocessing_result:
                # Start processing session
                processing_session_id = self.db.start_processing_session(
                    preprocessing_result['document_id'], 
                    preprocessing_result['total_chunks']
                )
                self.log_info(f"Started processing session: {processing_session_id}")
            
            print("=" * 30)
            print("🚀 AZURE FUNCTION PROCESSING:")
        else:
            self.log_info("Database disabled - skipping preprocessing step")
        
        # Encode file
        file_content = self.encode_file_to_base64(file_path)
        if file_content is None:
            return False
        
        # Prepare request
        payload = {
            "filename": os.path.basename(file_path),
            "file_content": file_content,
            "force_reindex": force_reindex
        }
        
        try:
            print("🚀 Sending document to Azure Function...")
            
            # Set timeout based on file size (larger files need more time)
            timeout = max(180, file_size // 1000 + 60)  # Base 60s + 1s per KB, min 180s
            self.log_debug(f"Using timeout: {timeout} seconds for {file_size:,} byte file")
            
            response = self.session.post(
                f"{self.base_url}/api/process-document",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # Log processing details
                    self.log_success("Document processed successfully!")
                    
                    # Show full response in verbose mode
                    if self.verbose:
                        self.log_debug("Full response:")
                        self.log_info(f"Response keys: {list(result.keys())}")
                        for key, value in result.items():
                            if key == 'chunk_details' and isinstance(value, list):
                                self.log_info(f"{key}: list with {len(value)} items")
                                # Show first few chunk details for debugging
                                for i, chunk in enumerate(value[:3]):  # Show first 3 chunks
                                    content_preview = chunk.get('content', '')[:100] + '...' if len(chunk.get('content', '')) > 100 else chunk.get('content', '')
                                    self.log_info(f"   Chunk {i+1}: {len(chunk.get('content', ''))} chars - {content_preview}")
                                if len(value) > 3:
                                    self.log_info(f"   ... and {len(value) - 3} more chunks")
                            elif isinstance(value, (dict, list)) and len(str(value)) > 200:
                                self.log_info(f"{key}: {type(value).__name__} with {len(value)} items")
                            else:
                                self.log_info(f"{key}: {value}")
                    
                    # Show processing results
                    if 'chunks_created' in result:
                        chunks = result['chunks_created']
                        self.log_info(f"Chunks created: {chunks}")
                    
                    # Show upload results
                    successful = result.get('successful_uploads', 0)
                    failed = result.get('failed_uploads', 0)
                    
                    # Capture Azure Function chunks for tracking
                    if self.enable_db:
                        # Create a document entry if preprocessing failed
                        if preprocessing_result is None:
                            try:
                                # Get or create document for Azure Function chunk tracking
                                file_name = os.path.basename(file_path)
                                with open(file_path, 'rb') as f:
                                    file_bytes = f.read()
                                
                                document_id, is_new = self.db.add_document(file_name, file_bytes)
                                
                                # Start a processing session for Azure Function chunks
                                if processing_session_id is None:
                                    processing_session_id = self.db.start_processing_session(document_id, 0)
                                
                                self._capture_azure_function_chunks(result, processing_session_id, document_id)
                            except Exception as e:
                                self.log_warning(f"Failed to capture Azure Function chunks without preprocessing: {str(e)}")
                        else:
                            self._capture_azure_function_chunks(result, processing_session_id, preprocessing_result['document_id'])
                    
                    # Update database with processing results
                    if self.enable_db and processing_session_id:
                        self.db.end_processing_session(processing_session_id, successful, failed)
                        self.log_debug(f"Updated processing session {processing_session_id}")
                    
                    if successful > 0 or failed > 0:
                        self.log_info(f"Upload results: {successful} successful, {failed} failed")
                        
                        # Show details about failed chunks if any
                        if failed > 0:
                            self.log_warning(f"⚠️  {failed} chunk(s) failed to process!")
                            
                            # Look for failed chunks details in the response
                            if 'failed_chunk_details' in result:
                                failed_chunks = result['failed_chunk_details']
                                self.log_error("Failed chunks details:")
                                for i, chunk_error in enumerate(failed_chunks[:5], 1):  # Show first 5 failed chunks
                                    chunk_id = chunk_error.get('chunk_id', f'Chunk {i}')
                                    error_msg = chunk_error.get('error', 'Unknown error')
                                    content_preview = chunk_error.get('content', '')[:100] + '...' if chunk_error.get('content') else 'No content'
                                    print(f"   ❌ {chunk_id}: {error_msg}")
                                    print(f"      Content: {content_preview}")
                                if len(failed_chunks) > 5:
                                    print(f"   ... and {len(failed_chunks) - 5} more failed chunks")
                            
                            # Look for error details in other parts of the response
                            elif 'processing_errors' in result:
                                errors = result['processing_errors']
                                self.log_error("Processing errors:")
                                for i, error in enumerate(errors[:3], 1):  # Show first 3 errors
                                    print(f"   ❌ Error {i}: {error}")
                                if len(errors) > 3:
                                    print(f"   ... and {len(errors) - 3} more errors")
                            
                            elif 'errors' in result:
                                errors = result['errors']
                                self.log_error("Processing errors:")
                                for i, error in enumerate(errors[:3], 1):  # Show first 3 errors
                                    print(f"   ❌ Error {i}: {error}")
                                if len(errors) > 3:
                                    print(f"   ... and {len(errors) - 3} more errors")
                            
                            else:
                                self.log_warning("No detailed error information available in response")
                                self.log_info("Check the Azure Function logs for more details")
                        else:
                            self.log_success(f"All {successful} chunks processed successfully!")
                    
                    if 'key_phrases' in result:
                        phrases = result['key_phrases']
                        if phrases:
                            self.log_success(f"Extracted {len(phrases)} key phrases:")
                            for i, phrase in enumerate(phrases[:5], 1):  # Show first 5
                                print(f"   {i}. {phrase}")
                            if len(phrases) > 5:
                                print(f"   ... and {len(phrases) - 5} more")
                        else:
                            self.log_warning("No key phrases extracted")
                    
                    return True
                    
                except json.JSONDecodeError as e:
                    self.log_error(f"Invalid JSON response: {str(e)}")
                    self.log_info(f"Response content: {response.text[:500]}...")
                    return False
            else:
                self.log_error(f"Processing failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    self.log_error(f"Error: {error_data.get('error', 'Unknown error')}")
                    
                    # Show additional error details if available
                    if 'details' in error_data:
                        self.log_info(f"Error details: {error_data['details']}")
                    
                    if 'failed_chunks' in error_data:
                        failed_chunks = error_data['failed_chunks']
                        self.log_error(f"Failed to process {len(failed_chunks)} chunks:")
                        for i, chunk_error in enumerate(failed_chunks[:3], 1):
                            chunk_id = chunk_error.get('chunk_id', f'Chunk {i}')
                            error_msg = chunk_error.get('error', 'Unknown error')
                            print(f"   ❌ {chunk_id}: {error_msg}")
                        if len(failed_chunks) > 3:
                            print(f"   ... and {len(failed_chunks) - 3} more failed chunks")
                    
                except json.JSONDecodeError:
                    self.log_error(f"Non-JSON error response: {response.text}")
                    self.show_response_details(response)
                except Exception as e:
                    self.log_error(f"Error parsing error response: {str(e)}")
                    self.show_response_details(response)
                return False
                
        except requests.exceptions.Timeout:
            self.log_error("Document processing timed out")
            return False
        except Exception as e:
            self.log_error(f"Error during document processing: {str(e)}")
            return False
        finally:
            # Clean up test file if we created it
            if file_path == "test_document.txt":
                try:
                    os.remove(file_path)
                    self.log_info("Cleaned up test file")
                except:
                    pass
    
    def create_test_file(self) -> str:
        """Create a test document file"""
        content = """Azure Functions Test Document
===========================

This is a test document for Azure Functions processing.

Key Information:
• Azure Functions is a serverless compute service
• Supports multiple programming languages including Python
• Enables event-driven programming
• Scales automatically based on demand

Features:
1. HTTP triggers for REST APIs
2. Timer triggers for scheduled tasks  
3. Event-driven processing
4. Integration with Azure services
5. Monitoring and logging capabilities

This document contains various technical concepts that should be 
extracted as key phrases during processing. The AI should identify 
terms related to cloud computing, serverless architecture, and 
Azure platform capabilities.
"""
        
        file_path = "test_document.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return file_path
    
    def test_employee_pdf(self) -> bool:
        """Test processing employee.pdf file"""
        print("📚 Testing Employee PDF Processing...")
        
        pdf_path = "employee.pdf"
        if not os.path.exists(pdf_path):
            self.log_error(f"Employee PDF not found: {pdf_path}")
            self.log_info("Make sure employee.pdf exists in the tests directory")
            return False
        
        return self.test_document_processing(pdf_path, force_reindex=True)
    
    def test_employee_pdf_with_retry(self, max_retries: int = 3) -> bool:
        """Test employee PDF processing with retry logic"""
        print(f"📚 Testing Employee PDF with Retry Logic (max {max_retries} attempts)...")
        
        for attempt in range(max_retries):
            print(f"\n🔄 Attempt {attempt + 1}/{max_retries}")
            
            success = self.test_employee_pdf()
            if success:
                self.log_success(f"Employee PDF processing succeeded on attempt {attempt + 1}")
                return True
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                self.log_info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        self.log_error(f"Employee PDF processing failed after {max_retries} attempts")
        return False
    
    def show_database_stats(self):
        """Display database statistics and failed chunks"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        print("\n📊 PREPROCESSING DATABASE STATISTICS")
        print("=" * 50)
        
        # Overall stats
        stats = self.db.get_preprocessing_stats()
        self.log_info(f"Total documents processed: {stats.get('total_documents', 0)}")
        self.log_info(f"Total preprocessing chunks: {stats.get('total_chunks', 0)}")
        self.log_info(f"Average chunk size: {stats.get('avg_chunk_size', 0)} characters")
        self.log_info(f"Total file size processed: {stats.get('total_file_size', 0):,} bytes")
        
        # Azure Function chunks stats
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get Azure Function chunk counts
                cursor.execute("SELECT COUNT(*) FROM azure_function_chunks")
                azure_total = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM azure_function_chunks WHERE upload_status = 'success'")
                azure_success = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM azure_function_chunks WHERE upload_status = 'failed'")
                azure_failed = cursor.fetchone()[0]
                
                if azure_total > 0:
                    print(f"\n📊 AZURE FUNCTION CHUNKS:")
                    print("-" * 30)
                    self.log_info(f"Total Azure Function chunks: {azure_total}")
                    self.log_info(f"Successful: {azure_success} ✅")
                    if azure_failed > 0:
                        self.log_warning(f"Failed: {azure_failed} ❌")
                    else:
                        self.log_success("No failed Azure chunks! 🎉")
        except Exception as e:
            self.log_debug(f"Could not get Azure Function chunk stats: {str(e)}")
        
        # Failed preprocessing chunks
        failed_chunks = self.db.get_failed_chunks()
        if failed_chunks:
            print(f"\n❌ FAILED PREPROCESSING CHUNKS ({len(failed_chunks)} total):")
            print("-" * 30)
            for chunk in failed_chunks[:10]:  # Show first 10
                print(f"📄 {chunk['filename']} - Chunk {chunk['chunk_index'] + 1}")
                print(f"   Error: {chunk['error_message']}")
                print(f"   Content: {chunk['content_preview']}")
                print()
            
            if len(failed_chunks) > 10:
                print(f"... and {len(failed_chunks) - 10} more failed chunks")
        
        # Failed Azure Function chunks
        failed_azure_chunks = self.db.get_failed_azure_chunks()
        if failed_azure_chunks:
            print(f"\n❌ FAILED AZURE FUNCTION CHUNKS ({len(failed_azure_chunks)} total):")
            print("-" * 30)
            for chunk in failed_azure_chunks[:10]:  # Show first 10
                print(f"📄 {chunk['filename']} - Azure Chunk {chunk['azure_chunk_index'] + 1} (Session {chunk['session_id']})")
                print(f"   Error: {chunk['error_message']}")
                print(f"   Content: {chunk['content_preview']}")
                print()
            
            if len(failed_azure_chunks) > 10:
                print(f"... and {len(failed_azure_chunks) - 10} more failed Azure chunks")
        
        if not failed_chunks and not failed_azure_chunks:
            self.log_success("No failed chunks found! 🎉")
    
    def reset_database_interactive(self):
        """Interactive database reset with confirmation"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        print("\n🗑️ DATABASE RESET")
        print("=" * 40)
        
        # Show current database info
        db_info = self.db.get_database_size_info()
        self.log_warning("⚠️ This will permanently delete ALL database content!")
        print(f"Current database: {db_info['file_path']}")
        print(f"File size: {db_info['file_size_bytes']:,} bytes")
        
        if 'error' not in db_info:
            print(f"Documents: {db_info.get('documents_count', 0)}")
            print(f"Chunks: {db_info.get('chunks_count', 0)}")
            print(f"Processing Sessions: {db_info.get('processing_sessions_count', 0)}")
        
        print("\n⚠️ WARNING: This action cannot be undone!")
        print("All preprocessed documents, chunks, and processing history will be lost.")
        
        # Double confirmation
        confirm1 = input("\nAre you sure you want to reset the database? (type 'yes' to confirm): ").strip().lower()
        
        if confirm1 == 'yes':
            confirm2 = input("Type 'DELETE ALL DATA' to confirm: ").strip()
            
            if confirm2 == 'DELETE ALL DATA':
                print("\n🔄 Resetting database...")
                success = self.db.reset_database(confirm=True)
                
                if success:
                    self.log_success("✅ Database reset completed successfully!")
                    self.log_info("All tables cleared and auto-increment counters reset")
                    
                    # Show new database state
                    new_info = self.db.get_database_size_info()
                    print(f"New file size: {new_info['file_size_bytes']:,} bytes")
                else:
                    self.log_error("❌ Database reset failed!")
            else:
                self.log_info("Database reset cancelled - confirmation text didn't match")
        else:
            self.log_info("Database reset cancelled")
    
    def view_database_contents(self):
        """Interactive database contents viewer"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        while True:
            print("\n📋 DATABASE CONTENTS VIEWER")
            print("=" * 40)
            print("1. List All Documents")
            print("2. View Document Details")
            print("3. View Processing Sessions")
            print("4. View Failed Chunks")
            print("5. View Azure Function Chunks")
            print("6. View Failed Azure Function Chunks")
            print("7. Raw SQL Query")
            print("8. Reset Database (Clear All Data)")
            print("0. Back to Main Menu")
            
            try:
                choice = input("\nSelect option (0-8): ").strip()
                
                if choice == "0":
                    break
                
                elif choice == "1":
                    # List all documents
                    documents = self.db.get_all_documents()
                    if documents:
                        print(f"\n📄 ALL DOCUMENTS ({len(documents)} total):")
                        print("-" * 60)
                        for doc in documents:
                            print(f"ID: {doc['id']} | File: {doc['filename']}")
                            print(f"   Size: {doc['file_size']:,} bytes | Hash: {doc['file_hash']}")
                            print(f"   Status: {doc['processing_status']} | Created: {doc['created_at']}")
                            print(f"   Preview: {doc['content_preview']}")
                            print()
                    else:
                        self.log_info("No documents found in database")
                
                elif choice == "2":
                    # View document details
                    doc_id = input("Enter document ID: ").strip()
                    try:
                        doc_id = int(doc_id)
                        chunks = self.db.get_document_chunks(doc_id)
                        if chunks:
                            print(f"\n📄 DOCUMENT {doc_id} CHUNKS ({len(chunks)} total):")
                            print("-" * 60)
                            for chunk in chunks:
                                status_icon = "✅" if chunk['upload_status'] == 'success' else "❌" if chunk['upload_status'] == 'failed' else "⏳"
                                print(f"{status_icon} Chunk {chunk['chunk_index']+1} (ID: {chunk['chunk_id']})")
                                print(f"   Size: {chunk['chunk_size']} chars | Hash: {chunk['chunk_hash']}")
                                print(f"   Status: {chunk['upload_status']} | Created: {chunk['created_at']}")
                                if chunk['error_message']:
                                    print(f"   Error: {chunk['error_message']}")
                                print(f"   Content: {chunk['content_preview']}")
                                print()
                            
                            # Ask if user wants to see full content of a chunk
                            show_full = input("\nShow full content of a chunk? (chunk number or 'n'): ").strip()
                            if show_full.lower() != 'n':
                                try:
                                    chunk_num = int(show_full) - 1
                                    if 0 <= chunk_num < len(chunks):
                                        print(f"\n📝 FULL CONTENT - Chunk {chunk_num + 1}:")
                                        print("-" * 60)
                                        print(chunks[chunk_num]['full_content'])
                                        print("-" * 60)
                                    else:
                                        print("Invalid chunk number")
                                except ValueError:
                                    print("Invalid chunk number")
                        else:
                            self.log_info(f"No chunks found for document ID {doc_id}")
                    except ValueError:
                        print("Invalid document ID")
                
                elif choice == "3":
                    # View processing sessions
                    sessions = self.db.get_processing_sessions()
                    if sessions:
                        print(f"\n🔄 PROCESSING SESSIONS ({len(sessions)} total):")
                        print("-" * 60)
                        for session in sessions:
                            success_rate = 0
                            if session['total_chunks'] > 0:
                                success_rate = (session['successful_chunks'] / session['total_chunks']) * 100
                            
                            print(f"Session {session['session_id']} | Document: {session['filename']}")
                            print(f"   Started: {session['session_start']}")
                            print(f"   Ended: {session['session_end'] or 'In Progress'}")
                            print(f"   Chunks: {session['successful_chunks']}/{session['total_chunks']} successful ({success_rate:.1f}%)")
                            if session['failed_chunks'] > 0:
                                print(f"   Failed: {session['failed_chunks']}")
                            if session['processing_time_seconds']:
                                print(f"   Duration: {session['processing_time_seconds']:.2f} seconds")
                            print()
                    else:
                        self.log_info("No processing sessions found")
                
                elif choice == "4":
                    # View failed chunks
                    failed_chunks = self.db.get_failed_chunks()
                    if failed_chunks:
                        print(f"\n❌ FAILED CHUNKS ({len(failed_chunks)} total):")
                        print("-" * 60)
                        for chunk in failed_chunks:
                            print(f"📄 {chunk['filename']} - Chunk {chunk['chunk_index'] + 1}")
                            print(f"   Chunk ID: {chunk['chunk_id']}")
                            print(f"   Error: {chunk['error_message']}")
                            print(f"   Content: {chunk['content_preview']}")
                            print()
                    else:
                        self.log_success("No failed chunks found! 🎉")
                
                elif choice == "5":
                    # View Azure Function chunks
                    session_id = input("Enter session ID (or press Enter for all): ").strip()
                    session_id = int(session_id) if session_id.isdigit() else None
                    
                    azure_chunks = self.db.get_azure_function_chunks(session_id=session_id)
                    if azure_chunks:
                        print(f"\n🔧 AZURE FUNCTION CHUNKS ({len(azure_chunks)} total):")
                        print("-" * 60)
                        for chunk in azure_chunks:
                            status_icon = "✅" if chunk['upload_status'] == 'success' else "❌" if chunk['upload_status'] == 'failed' else "⏳"
                            print(f"{status_icon} Azure Chunk {chunk['azure_chunk_index']+1} (ID: {chunk['azure_chunk_id']})")
                            print(f"   File: {chunk['filename']} | Session: {chunk['session_id']}")
                            print(f"   Size: {chunk['azure_chunk_size']} chars | Status: {chunk['upload_status']}")
                            if chunk['error_message']:
                                print(f"   Error: {chunk['error_message']}")
                            if chunk['key_phrases']:
                                print(f"   Key Phrases: {chunk['key_phrases'][:100]}...")
                            print(f"   Content: {chunk['content_preview']}")
                            print()
                    else:
                        self.log_info("No Azure Function chunks found")
                
                elif choice == "6":
                    # View failed Azure Function chunks
                    failed_azure_chunks = self.db.get_failed_azure_chunks()
                    if failed_azure_chunks:
                        print(f"\n❌ FAILED AZURE FUNCTION CHUNKS ({len(failed_azure_chunks)} total):")
                        print("-" * 60)
                        for chunk in failed_azure_chunks:
                            print(f"📄 {chunk['filename']} - Azure Chunk {chunk['azure_chunk_index'] + 1}")
                            print(f"   Session ID: {chunk['session_id']} | Chunk ID: {chunk['azure_chunk_id']}")
                            print(f"   Error: {chunk['error_message']}")
                            print(f"   Content: {chunk['content_preview']}")
                            print()
                    else:
                        self.log_success("No failed Azure Function chunks found! 🎉")
                
                elif choice == "7":
                    # Raw SQL query
                    print("\n💾 RAW SQL QUERY")
                    print("Available tables: documents, chunks, processing_sessions")
                    print("Example: SELECT * FROM documents LIMIT 5")
                    
                    query = input("Enter SQL query: ").strip()
                    if query:
                        try:
                            with sqlite3.connect(self.db.db_path) as conn:
                                cursor = conn.cursor()
                                cursor.execute(query)
                                
                                if query.upper().startswith('SELECT'):
                                    results = cursor.fetchall()
                                    columns = [description[0] for description in cursor.description]
                                    
                                    if results:
                                        print(f"\n📊 QUERY RESULTS ({len(results)} rows):")
                                        print("-" * 60)
                                        print(" | ".join(columns))
                                        print("-" * 60)
                                        for row in results[:20]:  # Limit to first 20 rows
                                            formatted_row = []
                                            for item in row:
                                                if isinstance(item, str) and len(item) > 50:
                                                    formatted_row.append(item[:47] + "...")
                                                else:
                                                    formatted_row.append(str(item))
                                            print(" | ".join(formatted_row))
                                        if len(results) > 20:
                                            print(f"... and {len(results) - 20} more rows")
                                    else:
                                        self.log_info("No results found")
                                else:
                                    conn.commit()
                                    self.log_success("Query executed successfully")
                        except Exception as e:
                            self.log_error(f"SQL Error: {str(e)}")
                
                elif choice == "8":
                    # Reset database
                    print("\n🗑️ RESET DATABASE")
                    print("-" * 30)
                    
                    # Show current database info
                    db_info = self.db.get_database_size_info()
                    print("⚠️ This will permanently delete ALL database content!")
                    print(f"Current database: {db_info['file_path']}")
                    
                    if 'error' not in db_info:
                        print(f"Documents: {db_info.get('documents_count', 0)}")
                        print(f"Chunks: {db_info.get('chunks_count', 0)}")
                        print(f"Sessions: {db_info.get('processing_sessions_count', 0)}")
                    
                    confirm = input("\nType 'DELETE ALL' to confirm reset: ").strip()
                    
                    if confirm == 'DELETE ALL':
                        success = self.db.reset_database(confirm=True)
                        if success:
                            print("✅ Database reset successfully!")
                        else:
                            print("❌ Database reset failed!")
                    else:
                        print("Reset cancelled - confirmation didn't match")
                
                else:
                    print("❌ Invalid choice. Please select 0-8.")
                    
            except KeyboardInterrupt:
                print("\n📋 Returning to main menu...")
                break
            except Exception as e:
                self.log_error(f"Error: {str(e)}")
                
            if choice != "0":
                input("\nPress Enter to continue...")  # Pause between operations
    
    def run_interactive_tests(self):
        """Interactive test runner"""
        print("🔧 Azure Function Testing Suite - Interactive Mode")
        print("=" * 50)
        
        while True:
            print("\nAvailable Tests:")
            print("1. Health Check")
            print("2. Document Processing (sample file)")
            print("3. Employee PDF (basic)")
            print("4. Employee PDF (with retry)")
            print("5. Run All Tests")
            print("6. Toggle Verbose Mode (currently: {})".format("ON" if self.verbose else "OFF"))
            print("7. Show Database Statistics")
            if self.enable_db:
                print("8. Toggle Database Mode (currently: ON)")
                print("9. View Database Contents")
                print("R. Reset Database (Clear All Data)")
            else:
                print("8. Toggle Database Mode (currently: OFF)")
            print("0. Exit")
            
            try:
                choice = input("\nSelect test (0-9, R): ").strip()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                    
                self.start_test_session()
                
                if choice == "1":
                    result = self.test_health_check()
                    self.record_test_result("Health Check", result)
                    
                elif choice == "2":
                    result = self.test_document_processing()
                    self.record_test_result("Document Processing", result)
                    
                elif choice == "3":
                    result = self.test_employee_pdf()
                    self.record_test_result("Employee PDF", result)
                    
                elif choice == "4":
                    result = self.test_employee_pdf_with_retry()
                    self.record_test_result("Employee PDF (Retry)", result)
                    
                elif choice == "5":
                    # Run all tests
                    health_ok = self.test_health_check()
                    self.record_test_result("Health Check", health_ok)
                    
                    if health_ok:
                        doc_ok = self.test_document_processing()
                        self.record_test_result("Document Processing", doc_ok)
                        
                        pdf_ok = self.test_employee_pdf()
                        self.record_test_result("Employee PDF", pdf_ok)
                
                elif choice == "6":
                    # Toggle verbose mode
                    self.verbose = not self.verbose
                    status = "ON" if self.verbose else "OFF"
                    self.log_info(f"Verbose mode is now {status}")
                    continue  # Don't start/end test session for this option
                
                elif choice == "7":
                    # Show database statistics
                    self.show_database_stats()
                    continue  # Don't start/end test session for this option
                
                elif choice == "8":
                    # Toggle database mode
                    self.enable_db = not self.enable_db
                    if self.enable_db and not self.db:
                        self.db = ChunkDatabaseManager()
                        self.log_info("📊 Database initialized")
                    status = "ON" if self.enable_db else "OFF"
                    self.log_info(f"Database mode is now {status}")
                    continue  # Don't start/end test session for this option
                
                elif choice == "9":
                    # View database contents
                    if self.enable_db:
                        self.view_database_contents()
                    else:
                        self.log_warning("Database mode is disabled. Enable it first (option 8).")
                    continue  # Don't start/end test session for this option
                
                elif choice.upper() == "R":
                    # Reset database
                    if self.enable_db:
                        self.reset_database_interactive()
                    else:
                        self.log_warning("Database mode is disabled. Enable it first (option 8).")
                    continue  # Don't start/end test session for this option
                
                else:
                    print("❌ Invalid choice. Please select 0-9 or R.")
                    continue
                
                self.end_test_session()
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                self.log_error(f"Error: {str(e)}")

def main():
    """Main entry point"""
    # Check for flags
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    enable_db = "--no-db" not in sys.argv  # Database enabled by default
    
    # Remove flags from argv for test name parsing
    sys.argv = [arg for arg in sys.argv if arg not in ["--verbose", "-v", "--no-db"]]
    
    tester = AzureFunctionTester(verbose=verbose, enable_db=enable_db)
    
    if len(sys.argv) > 1:
        # Command line mode
        test_name = sys.argv[1].lower()
        
        tester.start_test_session()
        
        if test_name == "health":
            result = tester.test_health_check()
            tester.record_test_result("Health Check", result)
            
        elif test_name == "document":
            result = tester.test_document_processing()
            tester.record_test_result("Document Processing", result)
            
        elif test_name in ["employee", "pdf"]:
            result = tester.test_employee_pdf()
            tester.record_test_result("Employee PDF", result)
            
        elif test_name == "retry":
            result = tester.test_employee_pdf_with_retry()
            tester.record_test_result("Employee PDF (Retry)", result)
            
        elif test_name == "all":
            # Run all tests
            health_ok = tester.test_health_check()
            tester.record_test_result("Health Check", health_ok)
            
            if health_ok:
                doc_ok = tester.test_document_processing()
                tester.record_test_result("Document Processing", doc_ok)
                
                pdf_ok = tester.test_employee_pdf()
                tester.record_test_result("Employee PDF", pdf_ok)
        
        elif test_name == "stats":
            # Show database statistics
            tester.show_database_stats()
            return  # Don't start/end test session for stats
        
        elif test_name in ["view", "db", "database"]:
            # View database contents
            if tester.enable_db:
                tester.view_database_contents()
            else:
                print("❌ Database mode is disabled. Enable it by removing --no-db flag.")
            return  # Don't start/end test session for database viewer
        
        elif test_name in ["reset", "clear"]:
            # Reset database
            if tester.enable_db:
                tester.reset_database_interactive()
            else:
                print("❌ Database mode is disabled. Enable it by removing --no-db flag.")
            return  # Don't start/end test session for database reset
        
        else:
            print("❌ Unknown test. Available tests:")
            print("  health    - Health check")
            print("  document  - Document processing")
            print("  employee  - Employee PDF processing")
            print("  retry     - Employee PDF with retry")
            print("  all       - All tests")
            print("  stats     - Show database statistics")
            print("  view      - View database contents (interactive)")
            print("  reset     - Reset database (clear all data)")
            print("\nOptions:")
            print("  --verbose, -v  - Enable detailed logging and debugging output")
            print("  --no-db        - Disable database preprocessing (enabled by default)")
            print("\nUsage: python enhanced_test_runner.py [test_name] [--verbose] [--no-db]")
        
        tester.end_test_session()
    else:
        # Interactive mode
        tester.run_interactive_tests()

if __name__ == "__main__":
    main()