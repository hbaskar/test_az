"""
Base64 File Encoder for Postman Testing
This script helps convert files to base64 format for testing the Azure Document Processing Function
"""

import base64
import os

def encode_file_to_base64(file_path):
    """Convert a file to base64 string"""
    try:
        with open(file_path, 'rb') as file:
            file_content = file.read()
            base64_encoded = base64.b64encode(file_content).decode('utf-8')
            return base64_encoded
    except Exception as e:
        print(f"Error encoding file: {e}")
        return None

def create_sample_files():
    """Create sample files for testing"""
    
    # Sample text document
    sample_text = """
    SERVICE AGREEMENT
    
    This Service Agreement ("Agreement") is entered into on December 1, 2024, 
    between ABC Corporation, a Delaware corporation ("Company") and XYZ Consulting LLC, 
    a New York limited liability company ("Consultant").
    
    1. SERVICES
    Consultant agrees to provide web development services including:
    - Frontend development using React.js
    - Backend API development
    - Database design and implementation
    - Testing and deployment
    
    2. COMPENSATION
    Company agrees to pay Consultant a total fee of $50,000 for the services, 
    payable as follows:
    - 25% ($12,500) upon execution of this Agreement
    - 50% ($25,000) upon completion of development phase
    - 25% ($12,500) upon final delivery and acceptance
    
    3. TIMELINE
    Project shall commence on December 15, 2024, and be completed by March 15, 2025.
    
    4. CONFIDENTIALITY
    Both parties agree to maintain confidentiality of proprietary information.
    
    5. TERMINATION
    Either party may terminate this Agreement with 30 days written notice.
    
    6. GOVERNING LAW
    This Agreement shall be governed by the laws of the State of New York.
    
    IN WITNESS WHEREOF, the parties have executed this Agreement.
    
    ABC Corporation                    XYZ Consulting LLC
    By: John Smith, CEO               By: Jane Doe, Managing Member
    Date: December 1, 2024            Date: December 1, 2024
    """
    
    # Create sample text file
    with open('sample_contract.txt', 'w') as f:
        f.write(sample_text.strip())
    
    # Sample legal document
    legal_text = """
    EMPLOYMENT AGREEMENT
    
    This Employment Agreement is made between TechCorp Inc. ("Employer") 
    and Sarah Johnson ("Employee") effective January 1, 2025.
    
    POSITION: Senior Software Engineer
    SALARY: $120,000 annually
    BENEFITS: Health insurance, 401(k) matching, 4 weeks PTO
    
    CONFIDENTIALITY: Employee agrees to protect confidential information.
    NON-COMPETE: 12-month restriction in same industry within 50-mile radius.
    TERMINATION: Either party may terminate with 2 weeks notice.
    
    This agreement is governed by California state law.
    
    Signatures:
    Employer: Michael Chen, CTO
    Employee: Sarah Johnson
    Date: December 15, 2024
    """
    
    with open('sample_employment.txt', 'w') as f:
        f.write(legal_text.strip())
    
    print("Sample files created:")
    print("- sample_contract.txt")
    print("- sample_employment.txt")

def main():
    """Main function to demonstrate usage"""
    
    print("=== Base64 File Encoder for Azure Function Testing ===\n")
    
    # Create sample files if they don't exist
    if not os.path.exists('sample_contract.txt'):
        create_sample_files()
        print()
    
    # List available files
    files = [f for f in os.listdir('.') if f.endswith(('.txt', '.pdf', '.docx'))]
    
    if not files:
        print("No suitable files found. Creating sample files...")
        create_sample_files()
        files = [f for f in os.listdir('.') if f.endswith(('.txt', '.pdf', '.docx'))]
    
    print("Available files for encoding:")
    for i, file in enumerate(files, 1):
        print(f"{i}. {file}")
    
    print("\nChoose a file to encode (enter number), or press Enter for all:")
    choice = input().strip()
    
    if choice:
        try:
            file_index = int(choice) - 1
            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                base64_content = encode_file_to_base64(selected_file)
                if base64_content:
                    print(f"\n=== Base64 for {selected_file} ===")
                    print(base64_content)
                    print(f"\n=== Postman JSON body for {selected_file} ===")
                    print(f'''{{
  "filename": "{selected_file}",
  "file_content": "{base64_content}",
  "force_reindex": false
}}''')
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    else:
        # Encode all files
        for file in files:
            base64_content = encode_file_to_base64(file)
            if base64_content:
                print(f"\n=== {file} ===")
                print(f"Base64: {base64_content[:100]}..." if len(base64_content) > 100 else base64_content)
                print(f"Length: {len(base64_content)} characters")

if __name__ == "__main__":
    main()