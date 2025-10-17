#!/usr/bin/env python3
"""
Azure SQL Database Manager for Chunk Processing
==============================================

Provides Azure SQL database functionality similar to SQLite implementation
for tracking document processing and Azure Function chunks.

Requirements:
    pip install pyodbc

Usage:
    from azure_sql_chunk_manager import AzureSQLChunkManager
    
    db_manager = AzureSQLChunkManager(
        server='your-server.database.windows.net',
        database='your-database',
        username='your-username',
        password='your-password'
    )
"""

import pyodbc
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

class AzureSQLChunkManager:
    """Manages Azure SQL database for chunk preprocessing and tracking"""
    
    def __init__(self, server: str, database: str, username: str, password: str, 
                 driver: str = "ODBC Driver 18 for SQL Server"):
        """Initialize Azure SQL connection and create tables"""
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        
        # Connection string - detect authentication type
        if "@" in username and "." in username:
            # Azure AD authentication for email-based usernames
            self.connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"Authentication=ActiveDirectoryPassword;"
                f"UID={username};"
                f"PWD={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
        else:
            # SQL Server authentication
            self.connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
        
        self.init_database()
    
    def get_connection(self):
        """Get a new database connection"""
        return pyodbc.connect(self.connection_string)
    
    def init_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create documents table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='documents' AND xtype='U')
                CREATE TABLE documents (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    filename NVARCHAR(255) NOT NULL,
                    file_size INT,
                    file_hash NVARCHAR(64) UNIQUE,
                    content_preview NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETUTCDATE(),
                    processed_at DATETIME2 NULL,
                    processing_status NVARCHAR(50) DEFAULT 'pending'
                )
            """)
            
            # Create chunks table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='chunks' AND xtype='U')
                CREATE TABLE chunks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    document_id INT,
                    chunk_index INT,
                    chunk_content NVARCHAR(MAX),
                    chunk_size INT,
                    chunk_hash NVARCHAR(64),
                    created_at DATETIME2 DEFAULT GETUTCDATE(),
                    upload_status NVARCHAR(50) DEFAULT 'pending',
                    error_message NVARCHAR(MAX) NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
            
            # Create processing_sessions table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='processing_sessions' AND xtype='U')
                CREATE TABLE processing_sessions (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    document_id INT,
                    session_start DATETIME2 DEFAULT GETUTCDATE(),
                    session_end DATETIME2 NULL,
                    total_chunks INT,
                    successful_chunks INT DEFAULT 0,
                    failed_chunks INT DEFAULT 0,
                    processing_time_seconds REAL NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
            
            # Create azure_function_chunks table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='azure_function_chunks' AND xtype='U')
                CREATE TABLE azure_function_chunks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    session_id INT,
                    document_id INT,
                    azure_chunk_index INT,
                    azure_chunk_content NVARCHAR(MAX),
                    azure_chunk_size INT,
                    azure_chunk_hash NVARCHAR(64),
                    upload_status NVARCHAR(50) DEFAULT 'pending',
                    error_message NVARCHAR(MAX) NULL,
                    processing_time_ms REAL NULL,
                    key_phrases NVARCHAR(MAX) NULL,
                    created_at DATETIME2 DEFAULT GETUTCDATE(),
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
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if document already exists
            cursor.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,))
            existing = cursor.fetchone()
            
            if existing:
                return existing[0], False  # Return existing document ID and False (not new)
            
            # Insert new document
            cursor.execute("""
                INSERT INTO documents (filename, file_size, file_hash, content_preview)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?)
            """, (filename, file_size, file_hash, content_preview))
            
            document_id = cursor.fetchone()[0]
            conn.commit()
            
            return document_id, True  # Return new document ID and True (is new)
    
    def add_chunks(self, document_id: int, chunks: List[str], preserve_existing: bool = True) -> List[int]:
        """Add chunks for a document and return chunk IDs"""
        chunk_ids = []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if preserve_existing:
                # Check if chunks already exist for this document
                cursor.execute("SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,))
                existing_chunks = cursor.fetchall()
                
                if existing_chunks:
                    return [row[0] for row in existing_chunks]
            
            # Add new chunks
            for i, chunk_content in enumerate(chunks):
                chunk_size = len(chunk_content)
                chunk_hash = hashlib.sha256(chunk_content.encode('utf-8')).hexdigest()
                
                cursor.execute("""
                    INSERT INTO chunks (document_id, chunk_index, chunk_content, chunk_size, chunk_hash)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?)
                """, (document_id, i, chunk_content, chunk_size, chunk_hash))
                
                chunk_id = cursor.fetchone()[0]
                chunk_ids.append(chunk_id)
            
            conn.commit()
        
        return chunk_ids
    
    def start_processing_session(self, document_id: int, total_chunks: int) -> int:
        """Start a new processing session and return session ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processing_sessions (document_id, total_chunks)
                OUTPUT INSERTED.id
                VALUES (?, ?)
            """, (document_id, total_chunks))
            
            session_id = cursor.fetchone()[0]
            conn.commit()
            
            return session_id
    
    def end_processing_session(self, session_id: int, successful_chunks: int, failed_chunks: int):
        """End a processing session with results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Calculate processing time
            cursor.execute("""
                UPDATE processing_sessions 
                SET session_end = GETUTCDATE(),
                    successful_chunks = ?,
                    failed_chunks = ?,
                    processing_time_seconds = DATEDIFF(SECOND, session_start, GETUTCDATE())
                WHERE id = ?
            """, (successful_chunks, failed_chunks, session_id))
            
            conn.commit()
    
    def add_azure_function_chunks(self, session_id: int, document_id: int, azure_chunks: List[Dict]) -> List[int]:
        """Add Azure Function chunks to tracking table"""
        chunk_ids = []
        
        with self.get_connection() as conn:
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
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, document_id, chunk_index, chunk_content, chunk_size, chunk_hash))
                
                chunk_id = cursor.fetchone()[0]
                chunk_ids.append(chunk_id)
            
            conn.commit()
        
        return chunk_ids
    
    def update_azure_chunk_status(self, azure_chunk_id: int, status: str, 
                                 error_message: str = None, processing_time_ms: float = None,
                                 key_phrases: str = None):
        """Update Azure Function chunk processing status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE azure_function_chunks 
                SET upload_status = ?, error_message = ?, processing_time_ms = ?, key_phrases = ?
                WHERE id = ?
            """, (status, error_message, processing_time_ms, key_phrases, azure_chunk_id))
            conn.commit()
    
    def get_azure_function_chunks(self, session_id: int = None, document_id: int = None) -> List[Dict]:
        """Get Azure Function chunks with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT af.id, af.session_id, af.document_id, d.filename, 
                       af.azure_chunk_index, af.azure_chunk_content, af.azure_chunk_size,
                       af.azure_chunk_hash, af.upload_status, af.error_message, af.created_at
                FROM azure_function_chunks af
                JOIN documents d ON af.document_id = d.id
            """
            params = []
            
            where_conditions = []
            if session_id:
                where_conditions.append("af.session_id = ?")
                params.append(session_id)
            if document_id:
                where_conditions.append("af.document_id = ?")
                params.append(document_id)
            
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            
            query += " ORDER BY af.session_id, af.azure_chunk_index"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return [
                {
                    'chunk_id': row[0],
                    'session_id': row[1],
                    'document_id': row[2],
                    'filename': row[3],
                    'azure_chunk_index': row[4],
                    'azure_chunk_content': row[5],
                    'azure_chunk_size': row[6],
                    'chunk_hash': row[7][:12] + '...' if row[7] else '',
                    'created_at': row[10],
                    'upload_status': row[8],
                    'error_message': row[9]
                }
                for row in results
            ]
    
    def get_failed_azure_chunks(self, session_id: int = None) -> List[Dict]:
        """Get failed Azure Function chunks for analysis"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT af.id, af.session_id, af.document_id, d.filename, 
                       af.azure_chunk_index, af.azure_chunk_content, af.error_message, af.created_at
                FROM azure_function_chunks af
                JOIN documents d ON af.document_id = d.id
                WHERE af.upload_status = 'failed'
            """
            params = []
            
            if session_id:
                query += " AND af.session_id = ?"
                params.append(session_id)
            
            query += " ORDER BY af.session_id, af.azure_chunk_index"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            return [
                {
                    'chunk_id': row[0],
                    'session_id': row[1],
                    'document_id': row[2],
                    'filename': row[3],
                    'azure_chunk_index': row[4],
                    'azure_chunk_content': row[5],
                    'error_message': row[6],
                    'created_at': row[7]
                }
                for row in results
            ]
    
    def get_processing_sessions(self, document_id: int = None) -> List[Dict]:
        """Get processing sessions"""
        with self.get_connection() as conn:
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
    
    def get_preprocessing_stats(self, document_id: int) -> Dict:
        """Get preprocessing statistics for a document"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_chunks,
                    AVG(CAST(chunk_size AS FLOAT)) as avg_chunk_size,
                    MIN(chunk_size) as min_chunk_size,
                    MAX(chunk_size) as max_chunk_size
                FROM chunks 
                WHERE document_id = ?
            """, (document_id,))
            
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                return {
                    'total_chunks': result[0],
                    'avg_chunk_size': round(result[1], 1) if result[1] else 0,
                    'min_chunk_size': result[2],
                    'max_chunk_size': result[3]
                }
            
            return {
                'total_chunks': 0,
                'avg_chunk_size': 0,
                'min_chunk_size': 0,
                'max_chunk_size': 0
            }
    
    def get_database_stats(self) -> Dict:
        """Get overall database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get document count
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            
            # Get preprocessing chunk count
            cursor.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cursor.fetchone()[0]
            
            # Get processing session count
            cursor.execute("SELECT COUNT(*) FROM processing_sessions")
            session_count = cursor.fetchone()[0]
            
            # Get Azure Function chunk count
            cursor.execute("SELECT COUNT(*) FROM azure_function_chunks")
            azure_chunk_count = cursor.fetchone()[0]
            
            return {
                'documents': doc_count,
                'preprocessing_chunks': chunk_count,
                'processing_sessions': session_count,
                'azure_function_chunks': azure_chunk_count
            }
    
    def reset_database(self):
        """Reset all tables (clear all data)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Delete all data (in correct order due to foreign keys)
            cursor.execute("DELETE FROM azure_function_chunks")
            cursor.execute("DELETE FROM processing_sessions")
            cursor.execute("DELETE FROM chunks")
            cursor.execute("DELETE FROM documents")
            
            # Reset identity seeds
            cursor.execute("DBCC CHECKIDENT ('documents', RESEED, 0)")
            cursor.execute("DBCC CHECKIDENT ('chunks', RESEED, 0)")
            cursor.execute("DBCC CHECKIDENT ('processing_sessions', RESEED, 0)")
            cursor.execute("DBCC CHECKIDENT ('azure_function_chunks', RESEED, 0)")
            
            conn.commit()

# Example configuration class
class AzureSQLConfig:
    """Configuration for Azure SQL connection"""
    
    @classmethod
    def from_env(cls) -> Dict[str, str]:
        """Load configuration from environment variables"""
        import os
        
        return {
            'server': os.getenv('AZURE_SQL_SERVER'),
            'database': os.getenv('AZURE_SQL_DATABASE'),
            'username': os.getenv('AZURE_SQL_USERNAME'),
            'password': os.getenv('AZURE_SQL_PASSWORD')
        }
    
    @classmethod
    def from_connection_string(cls, connection_string: str) -> Dict[str, str]:
        """Parse configuration from connection string"""
        # Simple parser for connection string format
        parts = {}
        for part in connection_string.split(';'):
            if '=' in part:
                key, value = part.split('=', 1)
                parts[key.lower().strip()] = value.strip()
        
        return {
            'server': parts.get('server', ''),
            'database': parts.get('database', ''),
            'username': parts.get('uid', ''),
            'password': parts.get('pwd', '')
        }

# Example usage
if __name__ == "__main__":
    # Example: Initialize with environment variables
    config = AzureSQLConfig.from_env()
    
    if all(config.values()):
        db_manager = AzureSQLChunkManager(**config)
        print("✅ Azure SQL database initialized successfully!")
        
        # Get database statistics
        stats = db_manager.get_database_stats()
        print(f"📊 Database stats: {stats}")
        
    else:
        print("❌ Azure SQL configuration not found in environment variables")
        print("Set AZURE_SQL_SERVER, AZURE_SQL_DATABASE, AZURE_SQL_USERNAME, AZURE_SQL_PASSWORD")