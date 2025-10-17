#!/usr/bin/env python3
"""
Debug Azure SQL Configuration
"""

import os
from dotenv import load_dotenv

# Load .env file
env_path = '.env'
if os.path.exists(env_path):
    load_dotenv(env_path)

# Check Azure SQL configuration
config = {
    'server': os.getenv('AZURE_SQL_SERVER'),
    'database': os.getenv('AZURE_SQL_DATABASE'),
    'username': os.getenv('AZURE_SQL_USERNAME'),
    'password': os.getenv('AZURE_SQL_PASSWORD')
}

print("🔍 Azure SQL Configuration Debug")
print("=" * 40)

for key, value in config.items():
    if key == 'password' and value:
        print(f"{key}: {'*' * len(value)}")
    else:
        print(f"{key}: {value}")

# Check for missing values
missing = [k for k, v in config.items() if not v]
if missing:
    print(f"\n❌ Missing config: {missing}")
else:
    print(f"\n✅ All configuration present")