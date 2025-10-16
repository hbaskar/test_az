#!/usr/bin/env python3
"""
Database Viewer - Standalone SQLite Database Browser
===================================================

A simple standalone viewer for the chunks preprocessing database.
This script allows you to browse and query the SQLite database 
independently from the main test runner.

Usage:
    python database_viewer.py                    # Interactive mode
    python database_viewer.py --query "SELECT * FROM documents"  # Direct query
    python database_viewer.py --export           # Export all data to JSON
    python database_viewer.py --reset            # Reset/clear all database tables
"""

import sqlite3
import json
import sys
import os
from typing import Dict, List, Any

class DatabaseViewer:
    """Standalone database viewer for chunks preprocessing database"""
    
    def __init__(self, db_path: str = "chunks_preprocessing.db"):
        """Initialize database viewer"""
        self.db_path = db_path
        
        if not os.path.exists(db_path):
            print(f"❌ Database file not found: {db_path}")
            print("Run the test runner first to create the database.")
            sys.exit(1)
    
    def get_table_info(self) -> Dict[str, List[str]]:
        """Get information about all tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            table_info = {}
            for table in tables:
                # Get column info for each table
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                table_info[table] = [col[1] for col in columns]  # col[1] is column name
            
            return table_info
    
    def get_table_counts(self) -> Dict[str, int]:
        """Get row counts for all tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            tables = self.get_table_info()
            counts = {}
            
            for table in tables.keys():
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            
            return counts
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a SQL query and return results"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(query)
                
                if query.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return {
                        'success': True,
                        'results': results,
                        'columns': columns,
                        'row_count': len(results)
                    }
                else:
                    conn.commit()
                    return {
                        'success': True,
                        'message': 'Query executed successfully',
                        'rows_affected': cursor.rowcount
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def show_database_overview(self):
        """Display overview of database"""
        print("📊 DATABASE OVERVIEW")
        print("=" * 50)
        print(f"Database file: {self.db_path}")
        print(f"File size: {os.path.getsize(self.db_path):,} bytes")
        print()
        
        # Table information
        table_info = self.get_table_info()
        table_counts = self.get_table_counts()
        
        for table, columns in table_info.items():
            print(f"📋 Table: {table} ({table_counts[table]} rows)")
            print(f"   Columns: {', '.join(columns)}")
            print()
    
    def show_sample_data(self, table: str, limit: int = 5):
        """Show sample data from a table"""
        result = self.execute_query(f"SELECT * FROM {table} LIMIT {limit}")
        
        if result['success'] and result.get('results'):
            print(f"📄 Sample data from {table}:")
            print("-" * 40)
            
            # Print headers
            print(" | ".join(result['columns']))
            print("-" * 40)
            
            # Print sample rows
            for row in result['results']:
                formatted_row = []
                for item in row:
                    if isinstance(item, str) and len(item) > 30:
                        formatted_row.append(item[:27] + "...")
                    else:
                        formatted_row.append(str(item) if item is not None else "NULL")
                print(" | ".join(formatted_row))
            
            if result['row_count'] == limit:
                total_result = self.execute_query(f"SELECT COUNT(*) FROM {table}")
                if total_result['success']:
                    total_rows = total_result['results'][0][0]
                    if total_rows > limit:
                        print(f"... and {total_rows - limit} more rows")
        else:
            print(f"❌ No data found in table {table}")
    
    def export_to_json(self, output_file: str = "database_export.json"):
        """Export all database data to JSON"""
        print(f"📤 Exporting database to {output_file}...")
        
        export_data = {}
        table_info = self.get_table_info()
        
        for table in table_info.keys():
            result = self.execute_query(f"SELECT * FROM {table}")
            if result['success']:
                # Convert rows to dictionaries
                rows_as_dicts = []
                for row in result['results']:
                    row_dict = {}
                    for i, column in enumerate(result['columns']):
                        row_dict[column] = row[i]
                    rows_as_dicts.append(row_dict)
                
                export_data[table] = {
                    'columns': result['columns'],
                    'row_count': result['row_count'],
                    'data': rows_as_dicts
                }
        
        # Add metadata
        export_data['_metadata'] = {
            'database_file': self.db_path,
            'export_timestamp': str(sqlite3.datetime.datetime.now()),
            'file_size_bytes': os.path.getsize(self.db_path)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"✅ Export complete: {output_file}")
        print(f"📊 Exported {sum(len(t['data']) for t in export_data.values() if isinstance(t, dict) and 'data' in t)} total rows")
    
    def interactive_mode(self):
        """Interactive database browser"""
        print("🔍 INTERACTIVE DATABASE VIEWER")
        print("=" * 40)
        
        while True:
            print("\nOptions:")
            print("1. Database Overview")
            print("2. Show Sample Data")
            print("3. Custom SQL Query")
            print("4. Export to JSON")
            print("5. Table Statistics")
            print("6. Reset Database (Clear All Data)")
            print("0. Exit")
            
            try:
                choice = input("\nSelect option (0-6): ").strip()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                
                elif choice == "1":
                    self.show_database_overview()
                
                elif choice == "2":
                    # Show sample data
                    table_info = self.get_table_info()
                    tables = list(table_info.keys())
                    
                    print(f"\nAvailable tables: {', '.join(tables)}")
                    table = input("Enter table name: ").strip()
                    
                    if table in tables:
                        limit = input("Number of rows to show (default 5): ").strip()
                        limit = int(limit) if limit.isdigit() else 5
                        self.show_sample_data(table, limit)
                    else:
                        print("❌ Invalid table name")
                
                elif choice == "3":
                    # Custom SQL query
                    print("\n💾 CUSTOM SQL QUERY")
                    print("Available tables:", ', '.join(self.get_table_info().keys()))
                    print("Example: SELECT * FROM documents WHERE filename LIKE '%.pdf%'")
                    
                    query = input("\nEnter SQL query: ").strip()
                    if query:
                        result = self.execute_query(query)
                        
                        if result['success']:
                            if 'results' in result:
                                # SELECT query
                                print(f"\n📊 Query results ({result['row_count']} rows):")
                                print("-" * 60)
                                
                                if result['row_count'] > 0:
                                    # Print headers
                                    print(" | ".join(result['columns']))
                                    print("-" * 60)
                                    
                                    # Print rows (limit to 50 for readability)
                                    display_rows = result['results'][:50]
                                    for row in display_rows:
                                        formatted_row = []
                                        for item in row:
                                            if isinstance(item, str) and len(item) > 40:
                                                formatted_row.append(item[:37] + "...")
                                            else:
                                                formatted_row.append(str(item) if item is not None else "NULL")
                                        print(" | ".join(formatted_row))
                                    
                                    if result['row_count'] > 50:
                                        print(f"... and {result['row_count'] - 50} more rows")
                                else:
                                    print("No results found")
                            else:
                                # Non-SELECT query
                                print(f"✅ {result['message']}")
                                if 'rows_affected' in result:
                                    print(f"Rows affected: {result['rows_affected']}")
                        else:
                            print(f"❌ Query error: {result['error']}")
                
                elif choice == "4":
                    # Export to JSON
                    filename = input("Export filename (default: database_export.json): ").strip()
                    if not filename:
                        filename = "database_export.json"
                    self.export_to_json(filename)
                
                elif choice == "5":
                    # Table statistics
                    print("\n📊 TABLE STATISTICS")
                    print("-" * 40)
                    
                    table_counts = self.get_table_counts()
                    table_info = self.get_table_info()
                    
                    for table, count in table_counts.items():
                        columns = table_info[table]
                        print(f"📋 {table}:")
                        print(f"   Rows: {count:,}")
                        print(f"   Columns: {len(columns)} ({', '.join(columns)})")
                        
                        # Get some basic stats if there's data
                        if count > 0:
                            # Try to get date range for tables with timestamps
                            if 'created_at' in columns:
                                result = self.execute_query(f"""
                                    SELECT MIN(created_at) as first, MAX(created_at) as last 
                                    FROM {table}
                                """)
                                if result['success'] and result['results']:
                                    first, last = result['results'][0]
                                    print(f"   Date range: {first} to {last}")
                        print()
                
                elif choice == "6":
                    # Reset database
                    print("\n🗑️ RESET DATABASE")
                    print("=" * 40)
                    
                    # Show current database info
                    file_size = os.path.getsize(self.db_path)
                    table_counts = self.get_table_counts()
                    
                    print("⚠️ This will permanently delete ALL database content!")
                    print(f"Database file: {self.db_path}")
                    print(f"Current size: {file_size:,} bytes")
                    
                    for table, count in table_counts.items():
                        print(f"{table.title()}: {count:,} records")
                    
                    print("\n⚠️ WARNING: This action cannot be undone!")
                    
                    # Double confirmation
                    confirm1 = input("\nType 'DELETE ALL DATA' to confirm: ").strip()
                    
                    if confirm1 == 'DELETE ALL DATA':
                        confirm2 = input("Are you absolutely sure? Type 'YES' to proceed: ").strip().upper()
                        
                        if confirm2 == 'YES':
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
                                    
                                print("✅ Database reset successfully!")
                                print(f"New file size: {os.path.getsize(self.db_path):,} bytes")
                                
                            except Exception as e:
                                print(f"❌ Error resetting database: {str(e)}")
                        else:
                            print("Reset cancelled - second confirmation didn't match")
                    else:
                        print("Reset cancelled - confirmation didn't match")
                
                else:
                    print("❌ Invalid choice. Please select 0-6.")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
            
            if choice != "0":
                input("\nPress Enter to continue...")

def main():
    """Main entry point"""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return
    
    # Check for database file parameter
    db_path = "chunks_preprocessing.db"
    if "--db" in sys.argv:
        try:
            db_index = sys.argv.index("--db")
            db_path = sys.argv[db_index + 1]
        except (IndexError, ValueError):
            print("❌ --db requires a database file path")
            return
    
    viewer = DatabaseViewer(db_path)
    
    # Check for direct query
    if "--query" in sys.argv:
        try:
            query_index = sys.argv.index("--query")
            query = sys.argv[query_index + 1]
            
            result = viewer.execute_query(query)
            if result['success']:
                if 'results' in result:
                    print(f"📊 Query results ({result['row_count']} rows):")
                    print(" | ".join(result['columns']))
                    print("-" * 60)
                    for row in result['results']:
                        print(" | ".join(str(item) for item in row))
                else:
                    print(f"✅ {result['message']}")
            else:
                print(f"❌ Query error: {result['error']}")
        except (IndexError, ValueError):
            print("❌ --query requires a SQL query string")
        return
    
    # Check for reset
    if "--reset" in sys.argv:
        print("🗑️ RESETTING DATABASE")
        print("=" * 40)
        
        file_size = os.path.getsize(viewer.db_path)
        table_counts = viewer.get_table_counts()
        
        print("⚠️ This will permanently delete ALL database content!")
        print(f"Database: {viewer.db_path}")
        print(f"Size: {file_size:,} bytes")
        
        for table, count in table_counts.items():
            print(f"{table.title()}: {count:,} records")
        
        confirm = input("\nType 'DELETE ALL DATA' to confirm: ").strip()
        if confirm == 'DELETE ALL DATA':
            try:
                with sqlite3.connect(viewer.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM azure_function_chunks")
                    cursor.execute("DELETE FROM processing_sessions")
                    cursor.execute("DELETE FROM chunks") 
                    cursor.execute("DELETE FROM documents")
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('documents', 'chunks', 'processing_sessions', 'azure_function_chunks')")
                    conn.commit()
                
                print("✅ Database reset successfully!")
                print(f"New size: {os.path.getsize(viewer.db_path):,} bytes")
                
            except Exception as e:
                print(f"❌ Reset failed: {str(e)}")
        else:
            print("Reset cancelled")
        return
    
    # Check for export
    if "--export" in sys.argv:
        output_file = "database_export.json"
        if "--output" in sys.argv:
            try:
                output_index = sys.argv.index("--output")
                output_file = sys.argv[output_index + 1]
            except (IndexError, ValueError):
                pass
        
        viewer.export_to_json(output_file)
        return
    
    # Interactive mode
    viewer.interactive_mode()

if __name__ == "__main__":
    main()