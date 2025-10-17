#!/usr/bin/env python3
"""
Simple Azure Function Test
=========================

Send a minimal request to the Azure Function to debug the 500 error.
"""

import requests
import json
import base64

def test_simple_request():
    """Test Azure Function with a simple request"""
    print("🧪 Testing Azure Function with Simple Request")
    print("=" * 50)
    
    url = "http://localhost:7071/api/process-document"
    
    # Simple test document
    test_content = "This is a test document."
    test_content_b64 = base64.b64encode(test_content.encode()).decode()
    
    payload = {
        "document": {
            "filename": "simple_test.txt",
            "content": test_content_b64
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-functions-key": "default"
    }
    
    try:
        print(f"🌐 Sending request to: {url}")
        print(f"📦 Payload size: {len(json.dumps(payload))} bytes")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Success!")
            try:
                result = response.json()
                print(f"📄 Response: {json.dumps(result, indent=2)}")
            except:
                print(f"📄 Response Text: {response.text}")
        else:
            print(f"❌ Error {response.status_code}")
            print(f"📄 Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_simple_request()