#!/usr/bin/env python3
"""
Enhanced Azure Function Test Runner with Multi-Database Support
============================================================

Supports both SQLite and Azure SQL for chunk processing and tracking.

Environment Configuration:
    # Use SQLite (default)
    DB_TYPE=sqlite
    SQLITE_DB_PATH=chunks_preprocessing.db
    
    # Use Azure SQL
    DB_TYPE=azure_sql
    AZURE_SQL_SERVER=your-server.database.windows.net
    AZURE_SQL_DATABASE=your-database
    AZURE_SQL_USERNAME=your-username
    AZURE_SQL_PASSWORD=your-password

Usage:
    # Default (uses environment DB_TYPE)
    python enhanced_test_runner_multi_db.py document --verbose
    
    # Force SQLite
    python enhanced_test_runner_multi_db.py document --verbose --db-type sqlite
    
    # Force Azure SQL (requires environment variables)
    python enhanced_test_runner_multi_db.py document --verbose --db-type azure_sql
"""

import sys
import argparse
import os
from typing import Optional

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    # Try to load from .env file in the current directory
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from {env_path}")
    else:
        # Try to load from parent directory (project root)
        parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(parent_env_path):
            load_dotenv(parent_env_path)
            print(f"✅ Loaded environment variables from {parent_env_path}")
        else:
            # Try to load from current working directory
            load_dotenv()
            print("ℹ️ Loaded environment variables from current directory")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment variables only")
except Exception as e:
    print(f"⚠️ Could not load .env file: {e}")

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database_config import create_database_manager, DatabaseConfig
    from enhanced_test_runner import AzureFunctionTester
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all required files are in the same directory:")
    print("- enhanced_test_runner.py")
    print("- azure_sql_chunk_manager.py")
    print("- database_config.py")
    sys.exit(1)

class MultiDatabaseAzureFunctionTester(AzureFunctionTester):
    """Enhanced Azure Function tester with multi-database support"""
    
    def __init__(self, azure_function_url: str, verbose: bool = False, 
                 enable_db: bool = True, db_type: str = None, **db_config):
        """Initialize with flexible database backend"""
        
        # Store database configuration
        self.db_type = db_type or os.getenv('DB_TYPE', 'sqlite')
        self.db_config = db_config
        
        # Store azure function URL for compatibility  
        self.azure_function_url = azure_function_url
        
        # Initialize parent class but override database manager
        super().__init__(base_url=azure_function_url, verbose=verbose, enable_db=False)  # Disable default DB
        
        # Set up database manager
        if enable_db:
            try:
                if db_type:
                    self.db = create_database_manager(db_type, **db_config)
                else:
                    # Use environment configuration
                    config = DatabaseConfig()
                    self.db = config.get_database_manager()
                
                self.enable_db = True
                self.log_success(f"📊 {self.db_type.upper()} database initialized successfully")
                
                # Show database stats
                if self.verbose:
                    stats = self.db.get_database_stats()
                    self.log_info(f"📈 Database stats: {stats}")
                    
            except Exception as e:
                self.log_error(f"Failed to initialize {self.db_type} database: {str(e)}")
                self.log_warning("Continuing without database support")
                self.enable_db = False
                self.db = None
        else:
            self.enable_db = False
            self.db = None

    def show_database_statistics(self):
        """Display database statistics and failed chunks"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        print(f"\n📊 {self.db_type.upper()} DATABASE STATISTICS")
        print("=" * 50)
        
        # Overall stats
        try:
            stats = self.db.get_database_stats()
            self.log_info(f"Total documents: {stats.get('documents', 0)}")
            self.log_info(f"Total preprocessing chunks: {stats.get('preprocessing_chunks', 0)}")
            self.log_info(f"Total processing sessions: {stats.get('processing_sessions', 0)}")
            self.log_info(f"Total Azure Function chunks: {stats.get('azure_function_chunks', 0)}")
        except Exception as e:
            self.log_error(f"Could not get database stats: {str(e)}")
        
        # Additional detailed stats if available
        try:
            if hasattr(self.db, 'get_preprocessing_stats'):
                detailed_stats = self.db.get_preprocessing_stats()
                if detailed_stats.get('total_chunks', 0) > 0:
                    self.log_info(f"Average chunk size: {detailed_stats.get('avg_chunk_size', 0)} characters")
                    self.log_info(f"Total file size processed: {detailed_stats.get('total_file_size', 0):,} bytes")
        except Exception as e:
            self.log_debug(f"Could not get detailed stats: {str(e)}")
        
        # Failed chunks
        try:
            if hasattr(self.db, 'get_failed_chunks'):
                failed_chunks = self.db.get_failed_chunks()
                if failed_chunks:
                    print(f"\n❌ FAILED PREPROCESSING CHUNKS ({len(failed_chunks)} total):")
                    print("-" * 30)
                    for chunk in failed_chunks[:5]:  # Show first 5
                        print(f"📄 Chunk {chunk.get('chunk_index', 'N/A')} - Error: {chunk.get('error_message', 'Unknown')}")
                    if len(failed_chunks) > 5:
                        print(f"... and {len(failed_chunks) - 5} more failed chunks")
                else:
                    self.log_success("No failed preprocessing chunks! 🎉")
        except Exception as e:
            self.log_debug(f"Could not get failed chunks: {str(e)}")

    def interactive_database_viewer(self):
        """Interactive database contents viewer"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        while True:
            print(f"\n📋 {self.db_type.upper()} DATABASE VIEWER")
            print("=" * 40)
            print("1. Show Database Statistics")
            print("2. List All Documents (if supported)")
            print("3. View Processing Sessions (if supported)")
            print("4. View Azure Function Chunks (if supported)")
            print("5. Reset Database (Clear All Data)")
            print("0. Back to Main Menu")
            
            try:
                choice = input("\nSelect option (0-5): ").strip()
                
                if choice == "0":
                    break
                
                elif choice == "1":
                    self.show_database_statistics()
                
                elif choice == "2":
                    try:
                        if hasattr(self.db, 'get_all_documents'):
                            documents = self.db.get_all_documents()
                            if documents:
                                print(f"\n📄 ALL DOCUMENTS ({len(documents)} total):")
                                print("-" * 60)
                                for doc in documents:
                                    print(f"ID: {doc['id']} | File: {doc['filename']}")
                                    print(f"   Size: {doc['file_size']:,} bytes")
                                    print(f"   Status: {doc.get('processing_status', 'N/A')}")
                                    print(f"   Created: {doc.get('created_at', 'N/A')}")
                                    print()
                            else:
                                self.log_info("No documents found in database")
                        else:
                            self.log_warning("Document listing not supported for this database type")
                    except Exception as e:
                        self.log_error(f"Error listing documents: {str(e)}")
                
                elif choice == "3":
                    try:
                        if hasattr(self.db, 'get_processing_sessions'):
                            sessions = self.db.get_processing_sessions()
                            if sessions:
                                print(f"\n🔄 PROCESSING SESSIONS ({len(sessions)} total):")
                                print("-" * 60)
                                for session in sessions:
                                    print(f"Session ID: {session['id']} | Document ID: {session['document_id']}")
                                    print(f"   Start: {session.get('session_start', 'N/A')}")
                                    print(f"   End: {session.get('session_end', 'N/A')}")
                                    print(f"   Total chunks: {session.get('total_chunks', 0)}")
                                    print(f"   Success: {session.get('successful_chunks', 0)} | Failed: {session.get('failed_chunks', 0)}")
                                    print()
                            else:
                                self.log_info("No processing sessions found")
                        else:
                            self.log_warning("Session listing not supported for this database type")
                    except Exception as e:
                        self.log_error(f"Error listing sessions: {str(e)}")
                
                elif choice == "4":
                    try:
                        if hasattr(self.db, 'get_azure_function_chunks'):
                            chunks = self.db.get_azure_function_chunks()
                            if chunks:
                                print(f"\n🔄 AZURE FUNCTION CHUNKS ({len(chunks)} total):")
                                print("-" * 60)
                                for chunk in chunks[:10]:  # Show first 10
                                    status_icon = "✅" if chunk.get('upload_status') == 'success' else "❌" if chunk.get('upload_status') == 'failed' else "⏳"
                                    print(f"{status_icon} Chunk {chunk.get('azure_chunk_index', 'N/A')} (Session {chunk.get('session_id', 'N/A')})")
                                    print(f"   Size: {chunk.get('azure_chunk_size', 0)} chars")
                                    print(f"   Status: {chunk.get('upload_status', 'unknown')}")
                                    if chunk.get('error_message'):
                                        print(f"   Error: {chunk['error_message']}")
                                    print()
                                if len(chunks) > 10:
                                    print(f"... and {len(chunks) - 10} more chunks")
                            else:
                                self.log_info("No Azure Function chunks found")
                        else:
                            self.log_warning("Azure Function chunk listing not supported for this database type")
                    except Exception as e:
                        self.log_error(f"Error listing Azure Function chunks: {str(e)}")
                
                elif choice == "5":
                    self.reset_database_interactive()
                
                else:
                    print("❌ Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n👋 Returning to main menu...")
                break
            except Exception as e:
                self.log_error(f"Error in database viewer: {str(e)}")

    def reset_database_interactive(self):
        """Interactive database reset"""
        if not self.enable_db:
            self.log_warning("Database not enabled")
            return
        
        print(f"\n⚠️ RESET {self.db_type.upper()} DATABASE")
        print("=" * 40)
        print("This will permanently delete ALL data from the database:")
        print("• All documents")
        print("• All preprocessing chunks")
        print("• All processing sessions")
        print("• All Azure Function chunks")
        
        confirm = input("\nType 'YES' to confirm database reset: ").strip()
        
        if confirm == "YES":
            try:
                if hasattr(self.db, 'reset_database'):
                    # Handle different reset_database signatures
                    if self.db_type == 'sqlite':
                        # SQLite version takes confirm parameter and returns bool
                        success = self.db.reset_database(confirm=True)
                        if success:
                            self.log_success("Database reset successfully! 🗑️")
                        else:
                            self.log_error("Database reset failed")
                    elif self.db_type == 'azure_sql':
                        # Azure SQL version doesn't take parameters and doesn't return value
                        self.db.reset_database()
                        self.log_success("Database reset successfully! 🗑️")
                    else:
                        # Generic approach - try without parameters first
                        try:
                            self.db.reset_database()
                            self.log_success("Database reset successfully! 🗑️")
                        except TypeError:
                            # If that fails, try with confirm parameter
                            success = self.db.reset_database(confirm=True)
                            if success:
                                self.log_success("Database reset successfully! 🗑️")
                            else:
                                self.log_error("Database reset failed")
                else:
                    self.log_warning("Database reset not supported for this database type")
            except Exception as e:
                self.log_error(f"Error resetting database: {str(e)}")
        else:
            self.log_info("Database reset cancelled")

    def test_openai_intelligent_chunking(self):
        """Test OpenAI intelligent chunking with different document types"""
        print("\n🧠 OpenAI Intelligent Chunking Test")
        print("=" * 50)
        
        # Get available test documents
        test_files = []
        test_dir = os.path.dirname(__file__)
        
        # Look for test documents
        for filename in os.listdir(test_dir):
            if filename.endswith(('.txt', '.pdf')) and not filename.startswith('.'):
                test_files.append(filename)
        
        if not test_files:
            self.log_error("No test documents found in current directory")
            return False
        
        print("Available documents for testing:")
        for i, filename in enumerate(test_files, 1):
            print(f"  {i}. {filename}")
        print(f"  {len(test_files) + 1}. Test all documents")
        
        try:
            choice = input(f"\nSelect document (1-{len(test_files) + 1}): ").strip()
            
            if choice == str(len(test_files) + 1):
                # Test all documents
                selected_files = test_files
            else:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(test_files):
                    selected_files = [test_files[choice_idx]]
                else:
                    self.log_error("Invalid selection")
                    return False
            
            # Process selected files
            all_passed = True
            for filename in selected_files:
                self.log_info(f"\n🔄 Testing: {filename}")
                
                file_path = os.path.join(test_dir, filename)
                
                # Read file content appropriately
                if filename.endswith('.pdf'):
                    # For PDF, send as binary
                    with open(file_path, 'rb') as f:
                        import base64
                        file_content = base64.b64encode(f.read()).decode('utf-8')
                    is_binary = True
                else:
                    # For text files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    is_binary = False
                
                # Test the Azure Function with intelligent chunking
                payload = {
                    "file_content": file_content,
                    "filename": filename
                }
                
                try:
                    # Call Azure Function using the correct endpoint and method
                    # Increase timeout for intelligent chunking which takes longer
                    response = self.session.post(
                        f"{self.base_url}/api/process-document",
                        json=payload,
                        timeout=180  # Increased timeout for OpenAI processing
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                    else:
                        result = {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
                    
                    if result and result.get('status') == 'success':
                        chunks_created = result.get('chunks_created', 0)
                        enhancement_type = result.get('enhancement', 'unknown')
                        chunking_method = result.get('chunking_method', 'basic')
                        
                        self.log_success(f"✅ {filename}: {chunks_created} chunks created")
                        self.log_info(f"   📊 Enhancement: {enhancement_type}")
                        self.log_info(f"   🧠 Chunking Method: {chunking_method}")
                        
                        # Show chunk details if verbose
                        if self.verbose and 'chunk_details' in result:
                            chunk_details = result['chunk_details'][:3]  # Show first 3 chunks
                            for i, chunk in enumerate(chunk_details, 1):
                                self.log_info(f"   🔹 Chunk {i}: {chunk.get('title', 'Untitled')}")
                                self.log_info(f"      Size: {chunk.get('content_size', 0)} chars")
                                if 'keyphrases' in chunk and chunk['keyphrases']:
                                    phrases = ', '.join(chunk['keyphrases'][:3])
                                    self.log_info(f"      Key phrases: {phrases}")
                        
                        # Store in database if enabled
                        if self.enable_db and hasattr(self.db, 'store_azure_function_result'):
                            try:
                                self.db.store_azure_function_result(filename, result)
                                self.log_debug(f"Stored {filename} results in {self.db_type} database")
                            except Exception as e:
                                self.log_warning(f"Could not store results: {str(e)}")
                    else:
                        self.log_error(f"❌ {filename}: Failed - {result.get('message', 'Unknown error')}")
                        all_passed = False
                        
                except Exception as e:
                    self.log_error(f"❌ {filename}: Exception - {str(e)}")
                    all_passed = False
            
            return all_passed
            
        except (ValueError, KeyboardInterrupt):
            self.log_info("Test cancelled")
            return False
        except Exception as e:
            self.log_error(f"Test failed: {str(e)}")
            return False

    def interactive_mode(self):
        """Interactive test runner mode"""
        print(f"🔧 Multi-Database Azure Function Testing Suite - Interactive Mode")
        print(f"📊 Using: {self.db_type.upper()} Database")
        print("=" * 60)
        
        while True:
            print("\nAvailable Tests:")
            print("1. Health Check")
            print("2. Document Processing (sample file)")
            print("3. Employee PDF (heading-based chunking)")
            print("4. Employee PDF (with retry)")
            print("5. OpenAI Intelligent Chunking Test")
            print("6. Employee PDF (basic sentence chunking)")
            print("7. Run All Tests")
            print("8. Toggle Verbose Mode (currently: {})".format("ON" if self.verbose else "OFF"))
            print("9. Show Database Statistics")
            if self.enable_db:
                print("10. Toggle Database Mode (currently: ON)")
                print("A. View Database Contents")
                print("R. Reset Database (Clear All Data)")
            else:
                print("10. Toggle Database Mode (currently: OFF)")
            print(f"D. Switch Database Type (currently: {self.db_type.upper()})")
            print("0. Exit")
            
            try:
                choice = input("\nSelect option (0-10, A, R, D): ").strip().upper()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                    
                elif choice == "1":
                    result = self.test_health_check()
                    
                elif choice == "2":
                    result = self.test_document_processing()
                    
                elif choice == "3":
                    result = self.test_employee_pdf()
                    
                elif choice == "4":
                    result = self.test_employee_pdf_with_retry()
                    
                elif choice == "5":
                    result = self.test_openai_intelligent_chunking()
                    
                elif choice == "6":
                    result = self.test_employee_pdf_basic()
                    
                elif choice == "7":
                    print("🔄 Running all tests...")
                    results = self.run_all_tests()
                    print(f"\n📊 Test Results:")
                    for test, passed in results.items():
                        status = "✅ PASS" if passed else "❌ FAIL"
                        print(f"  {test}: {status}")
                    
                elif choice == "8":
                    self.verbose = not self.verbose
                    print(f"🔧 Verbose mode: {'ON' if self.verbose else 'OFF'}")
                    
                elif choice == "9":
                    self.show_database_statistics()
                    
                elif choice == "10":
                    self.enable_db = not self.enable_db
                    if self.enable_db and not self.db:
                        try:
                            config = DatabaseConfig()
                            self.db = config.get_database_manager()
                            self.log_success("Database reconnected")
                        except Exception as e:
                            self.log_error(f"Failed to reconnect database: {str(e)}")
                            self.enable_db = False
                    elif not self.enable_db:
                        self.db = None
                    print(f"🗄️ Database mode: {'ON' if self.enable_db else 'OFF'}")
                    
                elif choice == "A":
                    self.interactive_database_viewer()
                    
                elif choice == "R":
                    self.reset_database_interactive()
                
                elif choice == "D":
                    print(f"\nCurrent database: {self.db_type.upper()}")
                    print("Available databases:")
                    print("1. SQLite (local development)")
                    print("2. Azure SQL (enterprise)")
                    new_choice = input("Select database (1-2): ").strip()
                    
                    if new_choice == "1":
                        new_db_type = "sqlite"
                    elif new_choice == "2":
                        new_db_type = "azure_sql"
                    else:
                        print("❌ Invalid choice")
                        continue
                    
                    if new_db_type != self.db_type:
                        try:
                            self.db_type = new_db_type
                            if self.enable_db:
                                self.db = create_database_manager(new_db_type)
                                self.log_success(f"Switched to {new_db_type.upper()} database")
                            else:
                                self.log_info(f"Database type set to {new_db_type.upper()} (will be used when database is enabled)")
                        except Exception as e:
                            self.log_error(f"Failed to switch database: {str(e)}")
                
                else:
                    print("❌ Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                self.log_error(f"Error in interactive mode: {str(e)}")

def create_test_runner(args) -> MultiDatabaseAzureFunctionTester:
    """Create test runner with specified configuration"""
    
    # Azure Function URL - extract base URL from full URL
    full_function_url = os.getenv('AZURE_FUNCTION_URL', 'http://localhost:7071/api/process-document')
    
    # Extract base URL (remove /api/process-document part if present)
    if '/api/' in full_function_url:
        base_url = full_function_url.split('/api/')[0]
    else:
        base_url = full_function_url
    
    # Database configuration
    db_config = {}
    if args.db_type == 'sqlite':
        if args.sqlite_db_path:
            db_config['db_path'] = args.sqlite_db_path
    elif args.db_type == 'azure_sql':
        # Use environment variables for Azure SQL
        pass
    
    return MultiDatabaseAzureFunctionTester(
        azure_function_url=base_url,
        verbose=args.verbose,
        enable_db=not args.no_db,
        db_type=args.db_type,
        **db_config
    )

def main():
    """Main entry point with enhanced argument parsing"""
    
    parser = argparse.ArgumentParser(
        description='Enhanced Azure Function Test Runner with Multi-Database Support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enhanced_test_runner_multi_db.py document --verbose
  python enhanced_test_runner_multi_db.py document --db-type sqlite --sqlite-db-path custom.db
  python enhanced_test_runner_multi_db.py employee --db-type azure_sql --verbose
  python enhanced_test_runner_multi_db.py all --no-db
        """
    )
    
    # Test selection
    parser.add_argument('test', nargs='?', default='interactive',
                       choices=['health', 'document', 'employee', 'retry', 'all', 'stats', 'view', 'reset', 'interactive'],
                       help='Test to run (default: interactive)')
    
    # Options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable detailed logging and debugging output')
    parser.add_argument('--no-db', action='store_true',
                       help='Disable database preprocessing (enabled by default)')
    
    # Database configuration
    parser.add_argument('--db-type', choices=['sqlite', 'azure_sql'],
                       help='Database type (default: from DB_TYPE env var or sqlite)')
    parser.add_argument('--sqlite-db-path', 
                       help='SQLite database path (default: chunks_preprocessing.db)')
    
    args = parser.parse_args()
    
    # Show configuration
    print("🔧 Multi-Database Azure Function Test Runner")
    print("=" * 50)
    
    db_type = args.db_type or os.getenv('DB_TYPE', 'sqlite')
    print(f"📊 Database type: {db_type.upper()}")
    
    if not args.no_db:
        if db_type == 'sqlite':
            db_path = args.sqlite_db_path or os.getenv('SQLITE_DB_PATH', 'chunks_preprocessing.db')
            print(f"📁 SQLite database: {db_path}")
        elif db_type == 'azure_sql':
            server = os.getenv('AZURE_SQL_SERVER', 'Not configured')
            database = os.getenv('AZURE_SQL_DATABASE', 'Not configured')
            print(f"🌐 Azure SQL server: {server}")
            print(f"🗄️ Azure SQL database: {database}")
    else:
        print("❌ Database disabled")
    
    print()
    
    # Create test runner
    try:
        tester = create_test_runner(args)
    except Exception as e:
        print(f"❌ Failed to initialize test runner: {e}")
        return 1
    
    # Run tests based on selection
    if args.test == 'interactive':
        return tester.interactive_mode()
    elif args.test == 'health':
        return 0 if tester.test_health_check() else 1
    elif args.test == 'document':
        return 0 if tester.test_document_processing() else 1
    elif args.test == 'employee':
        return 0 if tester.test_employee_pdf() else 1
    elif args.test == 'retry':
        return 0 if tester.test_employee_pdf_with_retry() else 1
    elif args.test == 'all':
        results = tester.run_all_tests()
        return 0 if all(results.values()) else 1
    elif args.test == 'stats':
        tester.show_database_statistics()
        return 0
    elif args.test == 'view':
        tester.interactive_database_viewer()
        return 0
    elif args.test == 'reset':
        tester.reset_database_interactive()
        return 0
    else:
        print(f"❌ Unknown test: {args.test}")
        return 1

if __name__ == "__main__":
    sys.exit(main())