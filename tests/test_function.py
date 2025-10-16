"""
Test script for the Azure Function Document Processing API
"""
import base64
import requests
import json
import sys
import os

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env file")
except ImportError:
    print("ℹ️ python-dotenv not available, using system environment variables")
except:
    pass

# Configuration
FUNCTION_URL = os.getenv("FUNCTION_TEST_URL", "http://localhost:7071/api/process-document")
print(f"🎯 Testing function at: {FUNCTION_URL}")

def test_health_check():
    """Test the health check endpoint (GET)"""
    print("🔍 Testing health check...")
    
    try:
        response = requests.get(FUNCTION_URL)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Health check passed: {result['message']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def encode_file(file_path):
    """Encode a file to base64"""
    try:
        with open(file_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        return file_content
    except Exception as e:
        print(f"❌ Error encoding file: {str(e)}")
        return None

def test_document_processing(file_path, force_reindex=False):
    """Test document processing with a sample file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    filename = os.path.basename(file_path)
    print(f"📄 Testing document processing: {filename}")
    
    # Encode file
    file_content = encode_file(file_path)
    if not file_content:
        return False
    
    # Prepare request
    payload = {
        "file_content": file_content,
        "filename": filename,
        "force_reindex": force_reindex
    }
    
    try:
        print("🚀 Sending request to Azure Function...")
        response = requests.post(
            FUNCTION_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=300  # 5 minute timeout for processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Document processed successfully!")
            print(f"   📊 Status: {result['status']}")
            print(f"   📝 Message: {result['message']}")
            print(f"   🗂️  Filename: {result.get('filename', 'N/A')}")
            print(f"   📦 Chunks created: {result.get('chunks_created', 'N/A')}")
            print(f"   ☁️  Successful uploads: {result.get('successful_uploads', 'N/A')}")
            print(f"   ⚠️  Failed uploads: {result.get('failed_uploads', 'N/A')}")
            print(f"   🎯 Enhancement: {result.get('enhancement', 'N/A')}")
            
            # Check for any warnings or issues in the response
            if 'warnings' in result:
                print(f"   ⚠️  Warnings: {result['warnings']}")
            if 'errors' in result:
                print(f"   🚨 Errors: {result['errors']}")
            
            return True
        else:
            print(f"❌ Document processing failed: {response.status_code}")
            try:
                error_result = response.json()
                error_message = error_result.get('message', response.text)
                print(f"   Error: {error_message}")
                
                # Check for specific OpenAI JSON parsing errors
                if "Expecting value" in error_message and "char" in error_message:
                    print("   🔍 This appears to be an OpenAI JSON parsing error!")
                    print("   💡 Possible causes:")
                    print("      • OpenAI API returned malformed JSON")
                    print("      • Response exceeded token limits")
                    print("      • API rate limiting or timeout")
                    print("      • Complex document content causing parsing issues")
                    print("   🛠️  Suggested fixes:")
                    print("      • Check OpenAI API status and quotas")
                    print("      • Reduce document size or complexity")
                    print("      • Add retry logic with exponential backoff")
                    print("      • Update temperature/max_tokens settings")
                
            except:
                print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out. Document processing may take longer than expected.")
        return False
    except Exception as e:
        print(f"❌ Request error: {str(e)}")
        return False

def test_invalid_requests():
    """Test various invalid request scenarios"""
    print("🧪 Testing invalid request scenarios...")
    
    test_cases = [
        {
            "name": "Missing file_content",
            "payload": {"filename": "test.txt"},
            "expected_status": 400
        },
        {
            "name": "Missing filename", 
            "payload": {"file_content": "dGVzdA=="},
            "expected_status": 400
        },
        {
            "name": "Invalid file type",
            "payload": {"file_content": "dGVzdA==", "filename": "test.exe"},
            "expected_status": 400
        },
        {
            "name": "Invalid base64",
            "payload": {"file_content": "invalid-base64!", "filename": "test.txt"},
            "expected_status": 400
        }
    ]
    
    for test_case in test_cases:
        try:
            response = requests.post(
                FUNCTION_URL,
                json=test_case["payload"],
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == test_case["expected_status"]:
                print(f"   ✅ {test_case['name']}: Expected {test_case['expected_status']}, got {response.status_code}")
            else:
                print(f"   ❌ {test_case['name']}: Expected {test_case['expected_status']}, got {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ {test_case['name']}: Error - {str(e)}")

def create_test_file():
    """Create a simple test file for testing"""
    test_content = """Test Document

This is a test document for Azure Function processing.

Section 1: Introduction
This section introduces the document processing capabilities.

Section 2: Features
The Azure Function can process multiple file types including:
- Text files (.txt)
- Word documents (.docx) 
- PDF files (.pdf)

Section 3: Conclusion
This concludes our test document."""

    test_file_path = "test_document.txt"
    
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"📝 Created test file: {test_file_path}")
    return test_file_path

def create_employee_text_file():
    """Create an employee handbook text file as alternative to PDF"""
    employee_content = """EMPLOYEE HANDBOOK
====================

Employee Information:
- Name: John Smith
- Position: Senior Software Engineer  
- Department: Technology
- Employee ID: EMP001
- Start Date: January 15, 2024
- Annual Salary: $95,000

Job Responsibilities:
• Develop and maintain software applications using Python and JavaScript
• Collaborate with product managers and designers on feature requirements
• Participate in code reviews and maintain coding standards
• Mentor junior developers and interns
• Contribute to technical documentation and best practices

Benefits Package:
• Health Insurance: Medical, dental, vision fully covered
• Retirement: 401(k) with 4% company match
• Time Off: 20 vacation days, 10 sick days, 8 holidays
• Professional Development: $2,000 annual budget for training
• Remote Work: Hybrid schedule, 3 days in office

Compensation Details:
• Base Salary: $95,000 annually
• Performance Bonus: Up to 15% of base salary
• Stock Options: 1,000 shares vesting over 4 years
• Annual Review: Merit increases based on performance

Confidentiality Agreement:
Employee agrees to maintain strict confidentiality of all proprietary 
company information, trade secrets, and client data. This includes 
software code, business strategies, customer lists, and financial 
information.

Non-Compete Clause:
Employee agrees not to work for direct competitors for a period of 
12 months after termination of employment within a 50-mile radius 
of company headquarters.

Termination Policy:
Either party may terminate employment with 2 weeks written notice.
Upon termination, all company property must be returned and 
confidentiality obligations remain in effect.

Company Policies:
• Work Hours: Monday-Friday, 9:00 AM - 5:00 PM with flexible arrangements
• Dress Code: Business casual, remote work allows casual attire
• Communication: Use Slack for team communication, email for external
• Equipment: Company provides laptop, monitor, and necessary software licenses

Training and Development:
• Onboarding: 2-week comprehensive training program
• Continuous Learning: Access to online courses and conferences
• Career Path: Regular discussions about advancement opportunities
• Mentorship: Assigned senior mentor for first 6 months

This employee handbook serves as a guide for company policies 
and procedures. Management reserves the right to modify these 
policies as needed with appropriate notice to employees."""

    text_file_path = "employee_handbook.txt"
    
    with open(text_file_path, 'w', encoding='utf-8') as f:
        f.write(employee_content)
    
    print(f"📄 Created employee handbook text file: {text_file_path}")
    return text_file_path

def test_employee_pdf_with_retry():
    """Test processing of employee.pdf with retry logic for OpenAI errors"""
    print("📄 Testing employee.pdf processing with retry logic...")
    
    # Path to the employee.pdf file in tests directory
    pdf_path = "employee.pdf"
    
    # Check if the file exists
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        print("ℹ️ Make sure employee.pdf exists in the tests directory")
        return False
    
    try:
        # Get file size for information
        file_size = os.path.getsize(pdf_path)
        print(f"📁 File size: {file_size:,} bytes")
        
        # Test processing the PDF with retry logic
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            print(f"🚀 Processing employee.pdf (attempt {retry_count + 1}/{max_retries})...")
            success = test_document_processing(pdf_path, force_reindex=True)
            
            if success:
                print("✅ Employee PDF processing completed successfully!")
                print("🎯 The AI extracted key phrases related to:")
                print("   • Employee information and job details")
                print("   • Compensation and benefits")
                print("   • Company policies and procedures")
                print("   • Confidentiality and legal terms")
                return True
            
            retry_count += 1
            if retry_count < max_retries:
                import time
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        print("❌ Employee PDF processing failed after all retries!")
        print("ℹ️ This could indicate persistent issues with:")
        print("   • OpenAI API response format (JSON parsing errors)")
        print("   • Document complexity causing AI processing failures")
        print("   • API rate limits or service availability")
        print("   • PDF content extraction problems")
        
        return False
        
    except Exception as e:
        print(f"❌ Error during employee PDF processing: {str(e)}")
        return False

def test_employee_pdf():
    """Test processing of employee.pdf from tests directory"""
    print("📄 Testing employee.pdf processing...")
    
    # Path to the employee.pdf file in tests directory
    pdf_path = "employee.pdf"
    
    # Check if the file exists
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        print("ℹ️ Make sure employee.pdf exists in the tests directory")
        return False
    
    try:
        # Get file size for information
        file_size = os.path.getsize(pdf_path)
        print(f"📁 File size: {file_size:,} bytes")
        
        # Test processing the PDF
        print("🚀 Processing employee.pdf with Azure Function...")
        success = test_document_processing(pdf_path, force_reindex=True)
        
        if success:
            print("✅ Employee PDF processing completed successfully!")
            print("🎯 The AI should extract key phrases related to:")
            print("   • Employee information and job details")
            print("   • Compensation and benefits")
            print("   • Company policies and procedures")
            print("   • Confidentiality and legal terms")
        else:
            print("❌ Employee PDF processing failed!")
            print("ℹ️ Common PDF processing issues:")
            print("   • OpenAI JSON parsing errors ('Expecting value' errors)")
            print("   • 'EOF marker not found' - Corrupted or incomplete PDF file")
            print("   • PDF parsing errors in PyPDF2 library")
            print("   • Complex PDF format requiring additional handling")
            print("💡 Suggestions:")
            print("   • Try the retry version: test_employee_pdf_with_retry()")
            print("   • Check OpenAI API status and quotas")
            print("   • Consider using a simpler text file for testing")
            
        return success
        
    except Exception as e:
        print(f"❌ Error during employee PDF processing: {str(e)}")
        return False

def test_employee_handbook():
    """Test processing employee handbook - tries PDF first, falls back to text"""
    print("📚 Testing Employee Handbook Processing...")
    
    # First try the PDF
    pdf_success = test_employee_pdf()
    
    if pdf_success:
        return True
    
    # If PDF failed, try with text version
    print("\n🔄 PDF processing failed, trying with text version...")
    
    text_file = None
    try:
        # Create text version of employee handbook
        text_file = create_employee_text_file()
        
        # Test processing the text file
        print("🚀 Processing employee handbook text file...")
        text_success = test_document_processing(text_file, force_reindex=True)
        
        if text_success:
            print("✅ Employee handbook (text) processing completed successfully!")
            print("🎯 The AI should extract key phrases related to:")
            print("   • Employee information and job details")
            print("   • Compensation and salary details")
            print("   • Benefits and time off policies")
            print("   • Confidentiality and non-compete clauses")
            print("   • Company policies and procedures")
        else:
            print("❌ Employee handbook (text) processing also failed!")
        
        return text_success
        
    except Exception as e:
        print(f"❌ Error during employee handbook text processing: {str(e)}")
        return False
    
    finally:
        # Clean up the text file
        if text_file and os.path.exists(text_file):
            try:
                os.remove(text_file)
                print(f"🗑️ Cleaned up text file: {text_file}")
            except:
                pass

def main():
    # """Main test function"""
    # print("🧪 Azure Function Document Processing - Test Suite")
    # print("=" * 60)
    
    # # Test 1: Health Check
    # if not test_health_check():
    #     print("❌ Health check failed. Make sure the function is running.")
    #     return
    
    # print()
    
    # # Test 2: Create and test with sample file
    # test_file_path = None
    # try:
    #     # Check if user provided a file path
    #     if len(sys.argv) > 1:
    #         test_file_path = sys.argv[1]
    #     else:
    #         # Create a test file
    #         test_file_path = create_test_file()
        
    #     success = test_document_processing(test_file_path, force_reindex=True)
        
    #     if success:
    #         print("\n✅ Document processing test passed!")
    #     else:
    #         print("\n❌ Document processing test failed!")
    
    # except Exception as e:
    #     print(f"❌ Error during document processing test: {str(e)}")
    
    # finally:
    #     # Clean up test file if we created it
    #     if test_file_path and test_file_path == "test_document.txt":
    #         try:
    #             os.remove(test_file_path)
    #             print(f"🗑️ Cleaned up test file: {test_file_path}")
    #         except:
    #             pass
    
    # print()
    
    # Test 3: Employee Handbook Processing (PDF with text fallback)
    print("� Running Employee Handbook Test...")
    handbook_success = test_employee_pdf()
    
    if handbook_success:
        print("✅ Employee handbook processing test passed!")
    else:
        print("❌ Employee handbook processing test failed!")
    
    print()
    
    # # Test 4: Invalid requests
    # test_invalid_requests()
    
    # print()
    # print("🏁 Test suite completed!")
    
    # # Summary
    # print("\n📊 Test Summary:")
    # print("=" * 30)
    # print("✅ Health Check")
    # print("✅ Text Document Processing" if 'success' in locals() and success else "❌ Text Document Processing")
    # print("✅ Employee Handbook Processing" if 'handbook_success' in locals() and handbook_success else "❌ Employee Handbook Processing") 
    # print("✅ Invalid Request Handling")

if __name__ == "__main__":
    main()