import os
import json
import logging
import tempfile
from typing import List, Dict, Any
from datetime import datetime
import base64
import uuid
import re

import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    # Try to load from .env file in the parent directory (for local development)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    print(f"🔍 Looking for .env file at: {env_path}")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logging.info(f"✅ Loaded environment variables from {env_path}")
    else:
        # Try to load from current directory
        load_dotenv()
        logging.info("✅ Loaded environment variables from current directory")
except ImportError:
    logging.warning("python-dotenv not available, using system environment variables only")
except Exception as e:
    logging.warning(f"Could not load .env file: {e}")

# Document processing imports
try:
    from docx import Document
    import PyPDF2
    from io import BytesIO
except ImportError as e:
    logging.error(f"Missing required packages: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
CONFIG = {
    "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "openai_key": os.getenv("AZURE_OPENAI_KEY"),
    "openai_api_version": "2024-08-01-preview",
    "openai_model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT", "gpt-4o-cms"),
    "openai_embedding_deployment": os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
    "search_endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
    "search_key": os.getenv("AZURE_SEARCH_KEY"),
    "search_document_index": os.getenv("AZURE_SEARCH_INDEX", "legal-documents-gc")
}

# Log configuration status (without sensitive values)
logger.info("🔧 Configuration Status:")
logger.info(f"  - OpenAI Endpoint: {'✅ Set' if CONFIG['openai_endpoint'] else '❌ Missing'}")
logger.info(f"  - OpenAI Key: {'✅ Set' if CONFIG['openai_key'] else '❌ Missing'}")
logger.info(f"  - OpenAI Model: {CONFIG['openai_model_deployment']}")
logger.info(f"  - OpenAI Embedding: {CONFIG['openai_embedding_deployment']}")
logger.info(f"  - Search Endpoint: {'✅ Set' if CONFIG['search_endpoint'] else '❌ Missing'}")
logger.info(f"  - Search Key: {'✅ Set' if CONFIG['search_key'] else '❌ Missing'}")
logger.info(f"  - Search Index: {CONFIG['search_document_index']}")

# Initialize clients (these will be initialized on first use)
openai_client = None
search_client = None

def get_openai_client():
    """Initialize OpenAI client lazily"""
    global openai_client
    if openai_client is None:
        if not CONFIG["openai_endpoint"]:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not CONFIG["openai_key"]:
            raise ValueError("AZURE_OPENAI_KEY environment variable is required")
        
        logger.info(f"🤖 Initializing OpenAI client with endpoint: {CONFIG['openai_endpoint']}")
        openai_client = AzureOpenAI(
            azure_endpoint=CONFIG["openai_endpoint"],
            api_key=CONFIG["openai_key"],
            api_version=CONFIG["openai_api_version"],
        )
        logger.info("✅ OpenAI client initialized successfully")
    return openai_client

def get_search_client():
    """Initialize Search client lazily"""
    global search_client
    if search_client is None:
        if not CONFIG["search_endpoint"]:
            raise ValueError("AZURE_SEARCH_ENDPOINT environment variable is required")
        if not CONFIG["search_key"]:
            raise ValueError("AZURE_SEARCH_KEY environment variable is required")
        
        logger.info(f"🔍 Initializing Search client with endpoint: {CONFIG['search_endpoint']}")
        search_client = SearchClient(
            endpoint=CONFIG["search_endpoint"],
            index_name=CONFIG["search_document_index"],
            credential=AzureKeyCredential(CONFIG["search_key"])
        )
        logger.info("✅ Search client initialized successfully")
    return search_client

def sanitize_document_key(filename: str) -> str:
    """Sanitize filename for use as document key"""
    base_name = os.path.splitext(filename)[0]
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name)
    return sanitized.lower()

def generate_text_embedding(text: str) -> List[float]:
    """Generate text embedding using Azure OpenAI"""
    try:
        client = get_openai_client()
        response = client.embeddings.create(
            input=text,
            model=CONFIG["openai_embedding_deployment"]
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return [0.0] * 1536  # Return dummy embedding

def extract_simple_keyphrases(text: str) -> List[str]:
    """Fallback method: Simple keyword extraction"""
    legal_terms = [
        "contract", "agreement", "terms", "conditions", "obligations", "rights",
        "payment", "delivery", "warranty", "liability", "indemnification",
        "confidentiality", "intellectual property", "termination", "breach",
        "damages", "jurisdiction", "governing law", "dispute resolution"
    ]
    
    found_terms = []
    text_lower = text.lower()
    
    for term in legal_terms:
        if term in text_lower:
            found_terms.append(term)
    
    # Add capitalized words
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    found_terms.extend(words[:3])
    
    return found_terms[:6] if found_terms else ["document", "content"]

def extract_keyphrases_with_openai(text: str, document_type: str = "legal") -> List[str]:
    """Use OpenAI to intelligently extract key phrases from text"""
    
    prompt = f'''
You are an expert at extracting key phrases from {document_type} documents. 

Analyze the provided text and extract 5-8 key phrases that are most important for search and categorization. Focus on:

For Legal Documents:
- Legal terms and concepts
- Important names, entities, companies
- Dates, deadlines, time periods
- Contract clauses and obligations
- Monetary amounts or percentages
- Jurisdictions or legal references

For General Documents:
- Main topics and themes
- Important entities or names
- Key concepts and terminology
- Action items or requirements
- Technical terms specific to the domain

Return ONLY a simple JSON array of key phrases as strings. No explanations.

Example output format:
["phrase1", "phrase2", "phrase3", "phrase4", "phrase5"]

Text to analyze:
{text[:2000]}
'''

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=CONFIG["openai_model_deployment"],
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=200
        )
        
        result = json.loads(response.choices[0].message.content)
        
        if isinstance(result, list):
            keyphrases = result
        elif isinstance(result, dict):
            keyphrases = result.get('keyphrases', result.get('phrases', result.get('key_phrases', [])))
            if not keyphrases and len(result) == 1:
                keyphrases = list(result.values())[0]
        else:
            keyphrases = []
        
        if not isinstance(keyphrases, list):
            keyphrases = []
            
        cleaned_phrases = []
        for phrase in keyphrases[:8]:
            if isinstance(phrase, str) and phrase.strip():
                cleaned_phrases.append(phrase.strip())
        
        return cleaned_phrases if cleaned_phrases else ["document", "content"]
        
    except Exception as e:
        logger.error(f"Error extracting keyphrases with OpenAI: {str(e)}")
        return extract_simple_keyphrases(text)

def extract_true_paragraphs_method2(file_path: str) -> str:
    """Method 2: Use paragraph styles and formatting to identify true paragraphs"""
    try:
        doc = Document(file_path)
        
        paragraphs = []
        current_paragraph = []
        
        for para in doc.paragraphs:
            text = para.text.strip()
            
            if not text:
                continue
                
            is_new_paragraph = (
                para.style.name.startswith(('Heading', 'Title')) or
                len(current_paragraph) == 0
            )
            
            if is_new_paragraph and current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = [text]
            else:
                current_paragraph.append(text)
        
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        return '\n\n'.join(paragraphs)
        
    except Exception as e:
        logger.error(f"Error in paragraph extraction: {str(e)}")
        return None

def process_document_content(file_path: str, file_extension: str) -> str:
    """Extract document content with properly reconstructed paragraphs"""
    if file_extension == 'txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    elif file_extension == 'docx':
        return extract_true_paragraphs_method2(file_path)
    
    elif file_extension == 'pdf':
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            # Basic paragraph reconstruction for PDFs
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            paragraphs = []
            current_paragraph = []
            
            for line in lines:
                current_paragraph.append(line)
                if line.endswith(('.', '!', '?')):
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
            
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
            
            return '\n\n'.join(paragraphs)
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return None
    
    else:
        logger.error(f"Unsupported file type: {file_extension}")
        return None

def delete_document_from_index(filename: str) -> Dict:
    """Delete all chunks of a document from the index"""
    try:
        client = get_search_client()
        results = client.search(
            search_text="*",
            filter=f"filename eq '{filename}'",
            select="id"
        )
        
        document_ids = [doc["id"] for doc in results]
        
        if not document_ids:
            return {
                "status": "not_found",
                "message": f"No documents found with filename: {filename}"
            }
        
        delete_docs = [{"id": doc_id} for doc_id in document_ids]
        result = client.delete_documents(delete_docs)
        
        successful_deletes = sum(1 for r in result if r.succeeded)
        
        return {
            "status": "success",
            "message": f"Deleted {successful_deletes} chunks for document {filename}",
            "deleted_chunks": successful_deletes
        }
        
    except Exception as e:
        logger.error(f"Error deleting document {filename}: {str(e)}")
        return {"status": "error", "message": str(e)}

def process_document_with_ai_keyphrases(file_path: str, filename: str, force_reindex: bool = False) -> Dict:
    """Enhanced version that uses OpenAI to extract intelligent key phrases"""
    try:
        logger.info(f"🔄 Processing document: {filename}")
        
        # Step 1: Extract content with proper paragraphs
        logger.info("📄 Extracting content with proper paragraph reconstruction...")
        file_extension = filename.lower().split('.')[-1]
        document_text = process_document_content(file_path, file_extension)
        
        if not document_text:
            return {"status": "error", "message": "Failed to extract document content"}
        
        paragraphs = document_text.split('\n\n')
        logger.info(f"✅ Extracted {len(paragraphs)} properly formatted paragraphs")
        
        # Step 2: Create enhanced chunks with AI key phrase extraction
        logger.info("🧠 Creating chunks with AI-powered key phrase extraction...")
        documents = []
        base_key = sanitize_document_key(filename)
        
        for i, para in enumerate(paragraphs, 1):
            if len(para.strip()) > 50:  # Only meaningful paragraphs
                logger.info(f"📝 Processing chunk {i}/{len(paragraphs)}...")
                
                # Generate AI-powered key phrases
                keyphrases = extract_keyphrases_with_openai(para, "legal")
                
                # Generate embedding
                embedding = generate_text_embedding(para)
                
                # Create enhanced summary
                sentences = para.split('. ')
                summary = sentences[0] + "." if len(sentences) > 1 else para[:100] + "..."
                
                # Create descriptive title
                title_prompt = f"Create a short descriptive title (3-6 words) for this legal text: {para[:200]}..."
                try:
                    client = get_openai_client()
                    title_response = client.chat.completions.create(
                        model=CONFIG["openai_model_deployment"],
                        messages=[{"role": "user", "content": title_prompt}],
                        max_tokens=20,
                        temperature=0.1
                    )
                    ai_title = title_response.choices[0].message.content.strip().strip('"')
                    title = ai_title if ai_title else f"Section {i}"
                except Exception as e:
                    logger.warning(f"Failed to generate AI title: {e}")
                    title = f"Section {i}"
                
                # Create document for indexing
                document = {
                    "id": f"{base_key}_{i}",
                    "title": title,
                    "paragraph": para.strip(),
                    "summary": summary,
                    "keyphrases": keyphrases,
                    "filename": filename,
                    "ParagraphId": str(i),
                    "date": datetime.now().isoformat(),
                    "group": ["legal"],
                    "department": "legal",
                    "language": "en",
                    "isCompliant": True,
                    "IrrelevantCollection": [],
                    "NonCompliantCollection": [],
                    "CompliantCollection": [str(i)],
                    "embedding": embedding
                }
                documents.append(document)
        
        logger.info(f"✅ Created {len(documents)} enhanced chunks with AI key phrases")
        
        # Step 3: Handle reindexing
        if force_reindex:
            logger.info("🗑️ Removing existing documents...")
            delete_result = delete_document_from_index(filename)
            if delete_result['status'] == 'success':
                logger.info(f"✅ Removed {delete_result['deleted_chunks']} existing chunks")
        
        # Step 4: Upload to Azure Search
        logger.info(f"☁️ Uploading {len(documents)} enhanced documents to Azure Search...")
        client = get_search_client()
        result = client.upload_documents(documents=documents)
        
        successful_uploads = sum(1 for r in result if r.succeeded)
        failed_uploads = len(result) - successful_uploads
        
        # Prepare chunk details for response (without embeddings to reduce size)
        chunk_details = []
        for i, doc in enumerate(documents):
            upload_result = result[i] if i < len(result) else None
            chunk_details.append({
                "chunk_id": doc["id"],
                "title": doc["title"],
                "content": doc["paragraph"][:500] + "..." if len(doc["paragraph"]) > 500 else doc["paragraph"],
                "content_size": len(doc["paragraph"]),
                "keyphrases": doc["keyphrases"],
                "status": "success" if (upload_result and upload_result.succeeded) else "failed",
                "error": None if (upload_result and upload_result.succeeded) else str(getattr(upload_result, 'error_message', 'Upload failed'))
            })
        
        return {
            "status": "success",
            "message": f"Successfully processed {filename} with AI key phrases",
            "filename": filename,
            "chunks_created": len(documents),
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "enhancement": "AI_keyphrases_and_titles",
            "chunk_details": chunk_details
        }
        
    except Exception as e:
        logger.error(f"Error in AI keyphrase processing: {str(e)}")
        return {"status": "error", "message": str(e)}

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function main entry point"""
    logger.info('🚀 Document processing function triggered')
    
    try:
        # Parse request
        method = req.method.upper()
        
        if method == 'GET':
            # Health check or status endpoint
            return func.HttpResponse(
                json.dumps({
                    "status": "healthy",
                    "message": "Document Processing Function is running",
                    "version": "1.0.0"
                }),
                mimetype="application/json",
                status_code=200
            )
        
        elif method == 'POST':
            # Process document request
            try:
                req_body = req.get_json()
            except ValueError:
                return func.HttpResponse(
                    json.dumps({"error": "Invalid JSON in request body"}),
                    mimetype="application/json",
                    status_code=400
                )
            
            if not req_body:
                return func.HttpResponse(
                    json.dumps({"error": "Request body is required"}),
                    mimetype="application/json",
                    status_code=400
                )
            
            # Extract parameters
            file_content = req_body.get('file_content')  # Base64 encoded file
            filename = req_body.get('filename')
            force_reindex = req_body.get('force_reindex', False)
            
            if not file_content or not filename:
                return func.HttpResponse(
                    json.dumps({
                        "error": "Both 'file_content' (base64 encoded) and 'filename' are required"
                    }),
                    mimetype="application/json",
                    status_code=400
                )
            
            # Validate file extension
            file_extension = filename.lower().split('.')[-1]
            if file_extension not in ['txt', 'docx', 'pdf']:
                return func.HttpResponse(
                    json.dumps({
                        "error": f"Unsupported file type: {file_extension}. Supported types: txt, docx, pdf"
                    }),
                    mimetype="application/json",
                    status_code=400
                )
            
            # Decode file content and save to temporary file
            try:
                file_data = base64.b64decode(file_content)
            except Exception as e:
                return func.HttpResponse(
                    json.dumps({"error": f"Invalid base64 file content: {str(e)}"}),
                    mimetype="application/json",
                    status_code=400
                )
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                # Process the document
                result = process_document_with_ai_keyphrases(
                    file_path=temp_file_path,
                    filename=filename,
                    force_reindex=force_reindex
                )
                
                return func.HttpResponse(
                    json.dumps(result),
                    mimetype="application/json",
                    status_code=200 if result["status"] == "success" else 500
                )
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
        
        else:
            return func.HttpResponse(
                json.dumps({"error": f"Method {method} not allowed"}),
                mimetype="application/json",
                status_code=405
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in function: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": f"Internal server error: {str(e)}"
            }),
            mimetype="application/json",
            status_code=500
        )