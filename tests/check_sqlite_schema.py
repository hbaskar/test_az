#!/usr/bin/env python3
"""
Check SQLite Database Schema
"""

import sqlite3

def check_sqlite_tables():
    """Check what tables exist in SQLite database"""
    print("🔍 Checking SQLite Database Schema")
    print("=" * 40)
    
    db_path = "chunks_preprocessing.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            print(f"📊 Found {len(tables)} tables:")
            for table in tables:
                table_name = table[0]
                print(f"  📋 {table_name}")
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"     Columns: {len(columns)}")
                for col in columns:
                    print(f"       - {col[1]} ({col[2]})")
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"     Rows: {count}")
                print()
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_sqlite_tables()