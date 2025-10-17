#!/usr/bin/env python3
"""
Quick test for heading-based chunking with validation metrics
"""
import sys
import os
import requests
import json
import base64
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

def test_heading_chunking():
    """Test heading-based chunking"""
    
    function_url = os.getenv('AZURE_FUNCTION_URL', 'http://localhost:7071/api/process-document')
    pdf_path = Path(__file__).parent / 'employee.pdf'
    
    print("🧪 Testing Heading-Based Chunking with Content Validation")
    print("=" * 60)
    
    try:
        with open(pdf_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        payload = {
            "filename": pdf_path.name,
            "file_content": file_content,
            "force_reindex": False,
            "chunking_method": "heading"  # Correct parameter for heading-based
        }
        
        print(f"🚀 Sending request...")
        
        response = requests.post(function_url, json=payload, timeout=500)
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ Success!")
            print(f"   Chunks: {result.get('chunks_created', 0)}")
            print(f"   Enhancement: {result.get('enhancement', 'none')}")
            
            # Show content validation
            validation = result.get('content_validation', {})
            if validation:
                print(f"\n📊 Content Preservation Validation:")
                print(f"   Original: {validation.get('original_chars', 0):,} chars, {validation.get('original_words', 0):,} words")
                print(f"   Chunked:  {validation.get('chunked_chars', 0):,} chars, {validation.get('chunked_words', 0):,} words")
                print(f"   Preservation: {validation.get('char_preservation_ratio', 0):.1%} chars, {validation.get('word_preservation_ratio', 0):.1%} words")
                print(f"   Validation: {'✅ PASSED' if validation.get('validation_passed', False) else '⚠️ ISSUES'}")
            
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_heading_chunking()