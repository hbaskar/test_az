#!/usr/bin/env python3
"""
Database Configuration for Enhanced Test Runner
============================================

This module provides configuration and factory methods to choose between
SQLite and Azure SQL for chunk processing database operations.

Usage:
    # Use SQLite (default)
    db_manager = create_database_manager('sqlite', db_path='chunks.db')
    
    # Use Azure SQL
    db_manager = create_database_manager('azure_sql', 
        server='your-server.database.windows.net',
        database='your-database',
        username='your-username', 
        password='your-password'
    )
"""

import os
from typing import Union, Dict, Any

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    # Try to load from .env file in the current directory
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        # Try to load from parent directory (project root)
        parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(parent_env_path):
            load_dotenv(parent_env_path)
        else:
            # Try to load from current working directory
            load_dotenv()
except ImportError:
    pass  # python-dotenv not available, use system environment variables only
except Exception:
    pass  # Could not load .env file, continue with system environment variables

# Import database managers
from enhanced_test_runner import ChunkDatabaseManager  # SQLite implementation

try:
    from azure_sql_chunk_manager import AzureSQLChunkManager
    AZURE_SQL_AVAILABLE = True
except ImportError:
    AZURE_SQL_AVAILABLE = False
    print("⚠️ Azure SQL not available. Install pyodbc: pip install pyodbc")

class DatabaseConfig:
    """Configuration manager for database selection"""
    
    def __init__(self):
        self.db_type = os.getenv('DB_TYPE', 'sqlite').lower()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration based on database type"""
        if self.db_type == 'sqlite':
            return {
                'db_path': os.getenv('SQLITE_DB_PATH', 'chunks_preprocessing.db')
            }
        elif self.db_type == 'azure_sql':
            return {
                'server': os.getenv('AZURE_SQL_SERVER'),
                'database': os.getenv('AZURE_SQL_DATABASE'),
                'username': os.getenv('AZURE_SQL_USERNAME'),
                'password': os.getenv('AZURE_SQL_PASSWORD')
            }
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def get_database_manager(self) -> Union[ChunkDatabaseManager, 'AzureSQLChunkManager']:
        """Get the appropriate database manager"""
        if self.db_type == 'sqlite':
            return ChunkDatabaseManager(self.config['db_path'])
        elif self.db_type == 'azure_sql':
            if not AZURE_SQL_AVAILABLE:
                raise ImportError("Azure SQL requires pyodbc. Install with: pip install pyodbc")
            
            # Validate Azure SQL configuration
            missing_config = [k for k, v in self.config.items() if not v]
            if missing_config:
                raise ValueError(f"Missing Azure SQL configuration: {missing_config}")
            
            return AzureSQLChunkManager(**self.config)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

def create_database_manager(db_type: str = None, **kwargs) -> Union[ChunkDatabaseManager, 'AzureSQLChunkManager']:
    """Factory function to create database manager"""
    
    if db_type is None:
        # Use environment configuration
        config = DatabaseConfig()
        return config.get_database_manager()
    
    db_type = db_type.lower()
    
    if db_type == 'sqlite':
        db_path = kwargs.get('db_path', 'chunks_preprocessing.db')
        return ChunkDatabaseManager(db_path)
    
    elif db_type == 'azure_sql':
        if not AZURE_SQL_AVAILABLE:
            raise ImportError("Azure SQL requires pyodbc. Install with: pip install pyodbc")
        
        # Use provided parameters or fall back to environment variables
        server = kwargs.get('server') or os.getenv('AZURE_SQL_SERVER')
        database = kwargs.get('database') or os.getenv('AZURE_SQL_DATABASE')
        username = kwargs.get('username') or os.getenv('AZURE_SQL_USERNAME')
        password = kwargs.get('password') or os.getenv('AZURE_SQL_PASSWORD')
        driver = kwargs.get('driver', "ODBC Driver 18 for SQL Server")
        
        # Validate required parameters
        params = {'server': server, 'database': database, 'username': username, 'password': password}
        missing_params = [k for k, v in params.items() if not v]
        
        if missing_params:
            raise ValueError(f"Missing required Azure SQL parameters: {missing_params}")
        
        return AzureSQLChunkManager(
            server=server,
            database=database,
            username=username,
            password=password,
            driver=driver
        )
    
    else:
        raise ValueError(f"Unsupported database type: {db_type}. Supported: 'sqlite', 'azure_sql'")

# Example .env configuration
ENV_EXAMPLE = """
# Database Configuration
# Choose database type: sqlite or azure_sql
DB_TYPE=sqlite

# SQLite Configuration (when DB_TYPE=sqlite)
SQLITE_DB_PATH=chunks_preprocessing.db

# Azure SQL Configuration (when DB_TYPE=azure_sql)
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=your-database
AZURE_SQL_USERNAME=your-username
AZURE_SQL_PASSWORD=your-password

# Azure Function Configuration (for both database types)
AZURE_FUNCTION_URL=http://localhost:7071/api/ProcessDocumentFunction
"""

if __name__ == "__main__":
    # Example usage
    print("🔧 Database Configuration Examples")
    print("=" * 50)
    
    # Test SQLite
    try:
        sqlite_db = create_database_manager('sqlite', db_path='test_chunks.db')
        stats = sqlite_db.get_database_stats()
        print(f"✅ SQLite: {stats}")
    except Exception as e:
        print(f"❌ SQLite error: {e}")
    
    # Test Azure SQL (if available)
    if AZURE_SQL_AVAILABLE:
        print("\n✅ Azure SQL support available")
        print("Configure with environment variables or direct parameters")
    else:
        print("\n⚠️ Azure SQL support not available")
        print("Install with: pip install pyodbc")
    
    print("\n📋 Environment Configuration:")
    print(ENV_EXAMPLE)