#!/usr/bin/env python3
"""
Direct test script for sentence-based chunking with content validation
"""
import sys
import os
import time
import requests
import json
import base64
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

def test_sentence_chunking():
    """Test sentence-based chunking directly"""
    
    # Azure Function URL
    function_url = os.getenv('AZURE_FUNCTION_URL', 'http://localhost:7071/api/process-document')
    
    # PDF file path
    pdf_path = Path(__file__).parent / 'employee.pdf'
    
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return False
    
    print("🧪 Testing Sentence-Based Chunking with Content Validation")
    print("=" * 60)
    print(f"📄 File: {pdf_path.name}")
    print(f"📏 Size: {pdf_path.stat().st_size:,} bytes")
    
    try:
        # Read and encode file to base64
        with open(pdf_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        # Prepare JSON payload
        payload = {
            "filename": pdf_path.name,
            "file_content": file_content,
            "force_reindex": False,
            "chunking_method": "sentence_based_chunking"
        }
        
        print(f"🚀 Sending request to: {function_url}")
        print(f"🔧 Method: sentence_based_chunking")
        print(f"📏 Payload size: {len(file_content):,} characters")
        
        # Send JSON request with extended timeout for sentence chunking
        response = requests.post(
            function_url,
            json=payload,
            timeout=1000  # 16+ minutes for sentence chunking which creates many chunks
        )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ Response received successfully!")
            print("📊 Results:")
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"   Chunks created: {result.get('chunks_created', 0)}")
            print(f"   Successful uploads: {result.get('successful_uploads', 0)}")
            print(f"   Failed uploads: {result.get('failed_uploads', 0)}")
            print(f"   Enhancement: {result.get('enhancement', 'none')}")
            print(f"   Method: {result.get('chunking_method', 'unknown')}")
            
            # Show chunk details if available
            chunk_details = result.get('chunk_details', [])
            if chunk_details:
                print(f"\n📝 Chunk Details ({len(chunk_details)} chunks):")
                for i, chunk_data in enumerate(chunk_details[:5], 1):  # Show first 5
                    if isinstance(chunk_data, dict):
                        content = chunk_data.get('content', '')
                        content_size = chunk_data.get('content_size', 0)
                        chunk_id = chunk_data.get('chunk_id', f'chunk_{i}')
                        title = chunk_data.get('title', 'Untitled')
                        
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"   Chunk {i} ({chunk_id}): {content_size} chars")
                        print(f"      Title: {title}")
                        print(f"      Content: {content_preview}")
                        print()
                    else:
                        # Fallback for string data
                        content_preview = str(chunk_data)[:200] + "..." if len(str(chunk_data)) > 200 else str(chunk_data)
                        print(f"   Chunk {i}: {content_preview}")
                
                if len(chunk_details) > 5:
                    print(f"   ... and {len(chunk_details) - 5} more chunks")
            
            # Show content validation metrics
            validation = result.get('content_validation', {})
            if validation:
                print(f"\n📊 Content Preservation Validation:")
                print(f"   Original: {validation.get('original_chars', 0):,} chars, {validation.get('original_words', 0):,} words")
                print(f"   Chunked:  {validation.get('chunked_chars', 0):,} chars, {validation.get('chunked_words', 0):,} words")
                print(f"   Preservation: {validation.get('char_preservation_ratio', 0):.1%} chars, {validation.get('word_preservation_ratio', 0):.1%} words")
                print(f"   Validation: {'✅ PASSED' if validation.get('validation_passed', False) else '⚠️ ISSUES DETECTED'}")
                
                issues = validation.get('issues', [])
                if issues:
                    print(f"   Issues: {', '.join(issues)}")
            
            return True
            
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out after 180 seconds")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    success = test_sentence_chunking()
    
    if success:
        print("\n🎉 Test completed successfully!")
        return 0
    else:
        print("\n💥 Test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())