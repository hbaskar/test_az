#!/usr/bin/env python3
"""
Test Azure Function Connection
=============================

Simple test to check if Azure Function is running.
"""

import requests
import os

def test_azure_function():
    """Test if Azure Function is accessible"""
    print("🔍 Testing Azure Function Connection")
    print("=" * 40)
    
    # Get function URL from environment or use default
    function_url = os.getenv('AZURE_FUNCTION_URL', 'http://localhost:7071/api/process-document')
    
    print(f"🌐 Testing URL: {function_url}")
    
    try:
        # Try a simple GET request to check if function is running
        response = requests.get(function_url, timeout=5)
        
        print(f"✅ Function is responding!")
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 405:
            print("ℹ️ Method Not Allowed (405) is expected for GET requests to this function")
            print("✅ Function is running correctly!")
            return True
        elif response.status_code == 200:
            print("✅ Function is running!")
            return True
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Function is not running or not accessible")
        print("\n📋 To start the Azure Function:")
        print("1. Open a new terminal")
        print("2. cd c:\\Users\\harib\\projects\\test_az")
        print("3. func start")
        print("\n📋 Or use VS Code task:")
        print("1. Ctrl+Shift+P")
        print("2. Type 'Tasks: Run Task'")
        print("3. Select 'func: host start'")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_azure_function()