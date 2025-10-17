#!/usr/bin/env python3
"""
Test Azure SQL Chunk Manager
===========================

Simple test script to verify Azure SQL functionality before using with main test runner.

Usage:
    # Set environment variables first
    export AZURE_SQL_SERVER=myserver.database.windows.net
    export AZURE_SQL_DATABASE=chunks-database
    export AZURE_SQL_USERNAME=myadmin
    export AZURE_SQL_PASSWORD=MyPassword123!
    
    python test_azure_sql.py
"""

import os
import sys
from datetime import datetime

def test_azure_sql():
    """Test Azure SQL chunk manager functionality"""
    
    print("🧪 Testing Azure SQL Chunk Manager")
    print("=" * 50)
    
    # Check dependencies
    try:
        import pyodbc
        print("✅ pyodbc available")
    except ImportError:
        print("❌ pyodbc not available. Install with: pip install pyodbc")
        return False
    
    # Check configuration
    config = {
        'server': os.getenv('AZURE_SQL_SERVER'),
        'database': os.getenv('AZURE_SQL_DATABASE'),
        'username': os.getenv('AZURE_SQL_USERNAME'),
        'password': os.getenv('AZURE_SQL_PASSWORD')
    }
    
    missing_config = [k for k, v in config.items() if not v]
    if missing_config:
        print(f"❌ Missing configuration: {missing_config}")
        print("Set environment variables:")
        for key in missing_config:
            print(f"  export AZURE_SQL_{key.upper()}=your-value")
        return False
    
    print(f"✅ Configuration complete")
    print(f"   Server: {config['server']}")
    print(f"   Database: {config['database']}")
    print(f"   Username: {config['username']}")
    
    # Test database manager
    try:
        from azure_sql_chunk_manager import AzureSQLChunkManager
        
        print("\n🔌 Testing database connection...")
        db = AzureSQLChunkManager(**config)
        print("✅ Database connection successful")
        
        # Test basic operations
        print("\n📊 Testing basic operations...")
        
        # Get initial stats
        stats = db.get_database_stats()
        print(f"📈 Initial stats: {stats}")
        
        # Test document addition
        test_content = b"This is a test document for Azure SQL testing."
        doc_id, is_new = db.add_document("test_document.txt", test_content)
        print(f"📄 Document added: ID={doc_id}, New={is_new}")
        
        # Test chunk addition
        test_chunks = [
            "This is the first test chunk.",
            "This is the second test chunk.",
            "This is the third test chunk."
        ]
        chunk_ids = db.add_chunks(doc_id, test_chunks)
        print(f"📋 Chunks added: {len(chunk_ids)} chunks")
        
        # Test processing session
        session_id = db.start_processing_session(doc_id, len(test_chunks))
        print(f"🔄 Processing session started: {session_id}")
        
        # Test Azure Function chunks
        azure_chunks = [
            {"content": "Azure chunk 1 content", "index": 0, "status": "success"},
            {"content": "Azure chunk 2 content", "index": 1, "status": "success"},
            {"content": "Azure chunk 3 content", "index": 2, "status": "failed", "error": "Test error"}
        ]
        azure_chunk_ids = db.add_azure_function_chunks(session_id, doc_id, azure_chunks)
        print(f"☁️ Azure Function chunks added: {len(azure_chunk_ids)} chunks")
        
        # Update chunk status
        for i, (chunk_data, chunk_id) in enumerate(zip(azure_chunks, azure_chunk_ids)):
            status = chunk_data.get('status', 'pending')
            error = chunk_data.get('error')
            db.update_azure_chunk_status(chunk_id, status, error_message=error)
        print("📝 Chunk statuses updated")
        
        # End processing session
        db.end_processing_session(session_id, 2, 1)  # 2 successful, 1 failed
        print("✅ Processing session completed")
        
        # Test queries
        print("\n🔍 Testing data retrieval...")
        
        # Get Azure Function chunks
        azure_chunks_retrieved = db.get_azure_function_chunks(session_id=session_id)
        print(f"📊 Retrieved {len(azure_chunks_retrieved)} Azure Function chunks")
        
        # Get failed chunks
        failed_chunks = db.get_failed_azure_chunks(session_id=session_id)
        print(f"❌ Found {len(failed_chunks)} failed chunks")
        
        # Get processing sessions
        sessions = db.get_processing_sessions(document_id=doc_id)
        print(f"📋 Found {len(sessions)} processing sessions")
        
        # Get final stats
        final_stats = db.get_database_stats()
        print(f"📈 Final stats: {final_stats}")
        
        # Test preprocessing stats
        prep_stats = db.get_preprocessing_stats(doc_id)
        print(f"📊 Preprocessing stats: {prep_stats}")
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_connection_only():
    """Test just the database connection"""
    
    print("🔌 Testing Azure SQL Connection Only")
    print("=" * 40)
    
    try:
        import pyodbc
        
        config = {
            'server': os.getenv('AZURE_SQL_SERVER'),
            'database': os.getenv('AZURE_SQL_DATABASE'),
            'username': os.getenv('AZURE_SQL_USERNAME'),
            'password': os.getenv('AZURE_SQL_PASSWORD')
        }
        
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        
        print(f"Connecting to: {config['server']}")
        print(f"Database: {config['database']}")
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # Test simple query
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"✅ Connection successful!")
        print(f"SQL Server version: {version[:50]}...")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "connection":
        success = test_connection_only()
    else:
        success = test_azure_sql()
    
    sys.exit(0 if success else 1)