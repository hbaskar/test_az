#!/usr/bin/env python3
"""
Direct SQLite query script to show full chunk content without truncation
"""
import sqlite3
import sys
from pathlib import Path

def query_chunks():
    """Query and display full chunk content from SQLite database"""
    
    # Database path
    db_path = Path(__file__).parent / 'chunks_preprocessing.db'
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("   Run a test with database enabled first")
        return
    
    print("🔍 SQLite Database Content Analysis")
    print("=" * 60)
    print(f"📁 Database: {db_path}")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check what tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"📊 Available tables: {[t[0] for t in tables]}")
        print()
        
        # Query Azure Function chunks, focusing on larger ones first
        cursor.execute("""
            SELECT id, azure_chunk_index, azure_chunk_content, azure_chunk_size, 
                   upload_status, created_at 
            FROM azure_function_chunks 
            ORDER BY azure_chunk_size DESC 
            LIMIT 10
        """)
        
        chunks = cursor.fetchall()
        
        if not chunks:
            print("📋 No chunks found in database")
            print("   Run a test with database enabled to populate data")
            return
        
        print(f"📝 Found {len(chunks)} chunks (showing largest 10 by size):")
        print("-" * 60)
        
        for chunk in chunks:
            chunk_id, index, content, size, status, created = chunk
            
            print(f"🔹 Chunk {index} (ID: {chunk_id})")
            print(f"   Declared size: {size} characters")
            print(f"   Actual stored length: {len(content)} characters")
            print(f"   Status: {status}")
            print(f"   Created: {created}")
            
            # Check if content appears truncated
            is_truncated = content.endswith('...') or len(content) < size
            truncation_indicator = " ⚠️ TRUNCATED" if is_truncated else " ✅ COMPLETE"
            
            print(f"   Content (first 200 chars): {content[:200]}...")
            print(f"   Storage status: {truncation_indicator}")
            
            if is_truncated:
                print(f"   � Content loss: {size - len(content)} characters missing")
            
            print()
        
        # Get total stats
        cursor.execute("SELECT COUNT(*), AVG(azure_chunk_size), SUM(azure_chunk_size) FROM azure_function_chunks")
        total_chunks, avg_size, total_size = cursor.fetchone()
        
        print("📊 Database Statistics:")
        print(f"   Total chunks: {total_chunks}")
        print(f"   Average size: {avg_size:.1f} characters")
        print(f"   Total content: {total_size:,} characters")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    query_chunks()