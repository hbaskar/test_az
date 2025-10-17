#!/usr/bin/env python3
"""
Debug Azure SQL Connection
=========================

Test to debug Azure SQL connection issues.
"""

import os
from dotenv import load_dotenv

def debug_env_loading():
    """Debug environment variable loading"""
    print("🔍 Debug Environment Variable Loading")
    print("=" * 50)
    
    # Try to load .env from current directory
    env_path = '.env'
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Found .env file: {os.path.abspath(env_path)}")
    else:
        print(f"❌ No .env file found: {os.path.abspath(env_path)}")
    
    # Show Azure SQL variables
    print("\n📊 Azure SQL Environment Variables:")
    azure_vars = [
        'DB_TYPE',
        'AZURE_SQL_SERVER', 
        'AZURE_SQL_DATABASE',
        'AZURE_SQL_USERNAME',
        'AZURE_SQL_PASSWORD'
    ]
    
    for var in azure_vars:
        value = os.getenv(var, 'NOT SET')
        if 'PASSWORD' in var and value != 'NOT SET':
            value = '*' * len(value)  # Hide password
        print(f"  {var}: {value}")
    
    # Test connection string building
    print("\n🔗 Connection String Test:")
    server = os.getenv('AZURE_SQL_SERVER', 'NOT_SET')
    database = os.getenv('AZURE_SQL_DATABASE', 'NOT_SET')
    username = os.getenv('AZURE_SQL_USERNAME', 'NOT_SET')
    password = os.getenv('AZURE_SQL_PASSWORD', 'NOT_SET')
    
    if all([server != 'NOT_SET', database != 'NOT_SET', username != 'NOT_SET', password != 'NOT_SET']):
        connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD=***;"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        print(f"  Connection String: {connection_string}")
    else:
        print("  ❌ Cannot build connection string - missing variables")

if __name__ == "__main__":
    debug_env_loading()