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

def intelligent_chunk_with_openai(document_text: str, document_type: str = "legal", max_chunk_size: int = 1000) -> List[str]:
    """Use OpenAI to intelligently determine optimal chunk boundaries based on semantic meaning"""
    
    # First, let OpenAI analyze the document structure and suggest chunking strategy
    analysis_prompt = f'''
You are an expert document analyst. Analyze this {document_type} document and determine the optimal way to break it into semantic chunks.

Consider:
- Natural topic boundaries
- Logical flow and coherence  
- Related concepts that should stay together
- Legal sections, clauses, or provisions
- Introductory vs detailed content
- Maximum chunk size of approximately {max_chunk_size} characters

Document to analyze:
{document_text[:3000]}{'...' if len(document_text) > 3000 else ''}

Return a JSON object with:
1. "strategy": brief description of chunking approach
2. "boundaries": array of character positions where chunks should split (approximate)
3. "chunk_themes": array of brief themes/topics for each suggested chunk

Example output:
{{
    "strategy": "Split by legal sections and related clauses",
    "boundaries": [0, 500, 1200, 2000],
    "chunk_themes": ["Introduction and parties", "Payment terms", "Obligations", "Termination clauses"]
}}
'''

    try:
        client = get_openai_client()
        
        # Get AI analysis of optimal chunking strategy
        analysis_response = client.chat.completions.create(
            model=CONFIG["openai_model_deployment"],
            messages=[{"role": "user", "content": analysis_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=800,
            timeout=45  # Longer timeout for analysis
        )
        
        analysis = json.loads(analysis_response.choices[0].message.content)
        logger.info(f"🧠 AI Chunking Strategy: {analysis.get('strategy', 'Standard approach')}")
        
        # Use AI-suggested boundaries to create initial chunks
        boundaries = analysis.get('boundaries', [])
        themes = analysis.get('chunk_themes', [])
        
        if not boundaries or len(boundaries) < 2:
            # Fallback to size-based chunking if AI analysis failed
            boundaries = list(range(0, len(document_text), max_chunk_size))
            boundaries.append(len(document_text))
        
        # Create chunks based on AI-suggested boundaries
        chunks = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = min(boundaries[i + 1], len(document_text))
            
            if end > start:
                raw_chunk = document_text[start:end].strip()
                
                # Now use OpenAI to refine and clean up each chunk
                refinement_prompt = f'''
You are a document processing expert. Clean up and optimize this text chunk for better readability and completeness.

Tasks:
1. Ensure the chunk starts and ends at natural sentence boundaries
2. If the chunk is cut off mid-sentence, either include the complete sentence or exclude the incomplete part
3. Remove any orphaned fragments
4. Ensure the chunk is coherent and self-contained
5. Preserve important formatting and structure

Theme for this chunk: {themes[i] if i < len(themes) else 'General content'}

Original chunk:
{raw_chunk}

Return ONLY the cleaned, optimized chunk text with no additional formatting or explanations.
'''

                try:
                    refinement_response = client.chat.completions.create(
                        model=CONFIG["openai_model_deployment"],
                        messages=[{"role": "user", "content": refinement_prompt}],
                        temperature=0.1,
                        max_tokens=min(1500, len(raw_chunk) + 200),
                        timeout=30  # Add timeout to prevent hanging
                    )
                    
                    refined_chunk = refinement_response.choices[0].message.content.strip()
                    
                    # Validation: ensure the refined chunk is reasonable
                    if (len(refined_chunk) > 50 and 
                        len(refined_chunk) <= max_chunk_size * 1.2 and
                        not refined_chunk.startswith("I ") and  # Avoid AI meta-responses
                        not refined_chunk.startswith("The chunk")):
                        chunks.append(refined_chunk)
                    else:
                        # Use original chunk if refinement failed
                        chunks.append(raw_chunk)
                        
                except Exception as e:
                    logger.warning(f"Chunk refinement failed: {e}, using original")
                    chunks.append(raw_chunk)
        
        # Final validation and cleanup
        final_chunks = []
        for chunk in chunks:
            if len(chunk.strip()) > 50:  # Minimum meaningful chunk size
                final_chunks.append(chunk.strip())
        
        logger.info(f"✅ AI Intelligent Chunking: {len(final_chunks)} semantic chunks created")
        return final_chunks
        
    except Exception as e:
        logger.error(f"Error in intelligent chunking: {str(e)}")
        # Fallback to sentence-based chunking
        return fallback_sentence_chunking(document_text, max_chunk_size)

def fallback_sentence_chunking(document_text: str, max_chunk_size: int = 1000) -> List[str]:
    """Fallback method: Split by sentences when AI chunking fails"""
    import re
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', document_text)
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        if current_size + len(sentence) > max_chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_size = len(sentence)
        else:
            current_chunk.append(sentence)
            current_size += len(sentence) + 1  # +1 for space
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # Validate content preservation (returns metrics but we don't need them here)
    validate_content_preservation(document_text, chunks, "sentence-based chunking")
    
    return chunks

def validate_content_preservation(original_text: str, chunks: List[str], method_name: str) -> Dict[str, Any]:
    """Validate that chunking preserves all content without loss or duplication"""
    
    # Calculate original content metrics
    original_length = len(original_text)
    original_words = len(original_text.split())
    
    # Calculate chunked content metrics  
    combined_chunks = ' '.join(chunks)
    combined_length = len(combined_chunks)
    combined_words = len(combined_chunks.split())
    
    # Calculate content preservation ratio
    length_ratio = combined_length / original_length if original_length > 0 else 0
    word_ratio = combined_words / original_words if original_words > 0 else 0
    
    # Additional validation: Check for significant content overlap or gaps
    total_chunk_chars = sum(len(chunk) for chunk in chunks)
    
    # Log validation results
    logger.info(f"📊 Content Validation for {method_name}:")
    logger.info(f"   Original: {original_length:,} chars, {original_words:,} words")
    logger.info(f"   Chunked:  {combined_length:,} chars, {combined_words:,} words")
    logger.info(f"   Individual chunks total: {total_chunk_chars:,} chars")
    logger.info(f"   Preservation: {length_ratio:.1%} chars, {word_ratio:.1%} words")
    
    # Check for content integrity issues
    issues = []
    
    # Check for significant content loss (allow 5% variance for whitespace/formatting)
    if length_ratio < 0.95:
        issues.append(f"Content loss: {original_length - combined_length} chars missing")
    
    # Check for unexpected content expansion (potential duplication)
    if length_ratio > 1.10:
        issues.append(f"Content expansion: {combined_length - original_length} extra chars")
    
    # Check for empty chunks
    empty_chunks = [i for i, chunk in enumerate(chunks) if not chunk.strip()]
    if empty_chunks:
        issues.append(f"Empty chunks found at positions: {empty_chunks}")
    
    # Determine validation result
    validation_passed = len(issues) == 0
    acceptable = length_ratio >= 0.90 and length_ratio <= 1.15
    
    # Log results
    if validation_passed:
        logger.info(f"✅ Content preservation validated for {method_name}")
    else:
        logger.warning(f"⚠️ Content integrity issues detected in {method_name}:")
        for issue in issues:
            logger.warning(f"   - {issue}")
        
        if acceptable:
            logger.info(f"📋 Issues within acceptable range for {method_name}")
    
    # Return detailed validation metrics
    return {
        "method": method_name,
        "original_chars": original_length,
        "original_words": original_words,
        "chunked_chars": combined_length,
        "chunked_words": combined_words,
        "total_chunk_chars": total_chunk_chars,
        "char_preservation_ratio": round(length_ratio, 3),
        "word_preservation_ratio": round(word_ratio, 3),
        "validation_passed": validation_passed,
        "acceptable": acceptable,
        "issues": issues,
        "chunks_count": len(chunks)
    }

def heading_based_chunking(document_text: str) -> List[str]:
    """Chunk document based on headings and sections"""
    import re
    
    # Split document into lines for analysis
    lines = document_text.split('\n')
    chunks = []
    current_chunk_lines = []
    
    # Patterns to detect headings and sections
    heading_patterns = [
        # Numbered sections: "1.", "1.1", "2.3.4", etc.
        re.compile(r'^\s*(\d+\.)+\s*[A-Z]'),
        # ALL CAPS headings (minimum 3 words, not too long)
        re.compile(r'^\s*[A-Z][A-Z\s]{10,80}[A-Z]\s*$'),
        # Roman numerals: "I.", "II.", "III.", etc.
        re.compile(r'^\s*[IVX]+\.\s*[A-Z]'),
        # Letters: "A.", "B.", "(a)", "(b)", etc.
        re.compile(r'^\s*\(?[A-Za-z]\)?\.\s*[A-Z]'),
        # Section keywords
        re.compile(r'^\s*(SECTION|ARTICLE|CHAPTER|PART|EXHIBIT)\s+\d+', re.IGNORECASE),
        # Legal document patterns
        re.compile(r'^\s*(WHEREAS|NOW THEREFORE|IN WITNESS WHEREOF)', re.IGNORECASE),
    ]
    
    def is_heading(line: str) -> bool:
        """Check if a line is likely a heading"""
        line = line.strip()
        
        # Skip empty lines
        if not line:
            return False
            
        # Skip very long lines (likely paragraph text)
        if len(line) > 100:
            return False
            
        # Check against heading patterns
        for pattern in heading_patterns:
            if pattern.match(line):
                return True
                
        # Additional heuristics for headings
        # Short lines that are mostly uppercase
        if len(line) < 50 and len([c for c in line if c.isupper()]) > len(line) * 0.7:
            return True
            
        return False
    
    def should_start_new_chunk(line: str, current_chunk_lines: List[str]) -> bool:
        """Determine if we should start a new chunk"""
        # Always start new chunk on headings
        if is_heading(line):
            return True
            
        # Don't split if current chunk is too small (less than 200 chars)
        current_size = sum(len(l) for l in current_chunk_lines)
        if current_size < 200:
            return False
            
        # Don't split if current chunk would be too large (more than 2000 chars)
        if current_size > 2000:
            return True
            
        return False
    
    logger.info(f"📋 Processing {len(lines)} lines for heading-based chunking")
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip completely empty lines at chunk boundaries
        if not line and not current_chunk_lines:
            continue
            
        # Check if we should start a new chunk
        if current_chunk_lines and should_start_new_chunk(line, current_chunk_lines):
            # Finalize current chunk
            chunk_text = '\n'.join(current_chunk_lines).strip()
            if chunk_text:
                chunks.append(chunk_text)
            current_chunk_lines = []
        
        # Add line to current chunk
        if line:  # Only add non-empty lines
            current_chunk_lines.append(line)
    
    # Add final chunk
    if current_chunk_lines:
        chunk_text = '\n'.join(current_chunk_lines).strip()
        if chunk_text:
            chunks.append(chunk_text)
    
    logger.info(f"✅ Created {len(chunks)} heading-based chunks")
    
    # Validate content preservation (returns metrics but we don't need them here)
    validate_content_preservation(document_text, chunks, "heading-based chunking")
    
    # Log chunk details for debugging
    for i, chunk in enumerate(chunks[:5]):  # Show first 5 chunks
        logger.info(f"   Chunk {i+1}: {len(chunk)} chars - {chunk[:60]}...")
    
    return chunks

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
            max_tokens=200,
            timeout=30  # Add timeout
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

def process_document_with_ai_keyphrases(file_path: str, filename: str, force_reindex: bool = False, chunking_method: str = "intelligent") -> Dict:
    """Enhanced version that uses OpenAI to extract intelligent key phrases"""
    try:
        logger.info(f"🔄 Processing document: {filename}")
        
        # Step 1: Extract content with proper paragraphs
        logger.info("📄 Extracting content with proper paragraph reconstruction...")
        file_extension = filename.lower().split('.')[-1]
        document_text = process_document_content(file_path, file_extension)
        
        if not document_text:
            return {"status": "error", "message": "Failed to extract document content"}
        
        # Step 2: Choose chunking method based on parameter
        validation_metrics = None
        if chunking_method == "intelligent":
            logger.info("🧠 Using OpenAI for intelligent semantic chunking...")
            chunks = intelligent_chunk_with_openai(document_text, "legal", max_chunk_size=1200)
            logger.info(f"✅ Created {len(chunks)} intelligent semantic chunks")
            chunk_method_used = "AI_semantic_analysis"
            enhancement_type = "OpenAI_intelligent_chunking_with_semantic_boundaries"
            validation_metrics = validate_content_preservation(document_text, chunks, "intelligent chunking")
        elif chunking_method == "heading":
            logger.info("📋 Using heading-based structural chunking...")
            chunks = heading_based_chunking(document_text)
            logger.info(f"✅ Created {len(chunks)} heading-based chunks")
            chunk_method_used = "heading_based_chunking"
            enhancement_type = "structural_heading_chunking"
            validation_metrics = validate_content_preservation(document_text, chunks, "heading-based chunking")
        else:  # basic or sentence-based
            logger.info("📝 Using basic sentence-based chunking...")
            chunks = fallback_sentence_chunking(document_text, max_chunk_size=500)  # Smaller chunks for more chunks
            logger.info(f"✅ Created {len(chunks)} sentence-based chunks")
            chunk_method_used = "sentence_based_chunking"
            enhancement_type = "basic_sentence_chunking"
            validation_metrics = validate_content_preservation(document_text, chunks, "sentence-based chunking")
        
        # Step 3: Create enhanced chunks with AI key phrase extraction
        logger.info("🧠 Creating chunks with AI-powered key phrase extraction...")
        documents = []
        base_key = sanitize_document_key(filename)
        
        for i, chunk_text in enumerate(chunks, 1):
            if len(chunk_text.strip()) > 50:  # Only meaningful chunks
                logger.info(f"📝 Processing chunk {i}/{len(chunks)}...")
                
                # Generate AI-powered key phrases
                keyphrases = extract_keyphrases_with_openai(chunk_text, "legal")
                
                # Generate embedding
                embedding = generate_text_embedding(chunk_text)
                
                # Create enhanced summary using OpenAI
                summary_prompt = f"Create a concise 1-2 sentence summary of this legal text: {chunk_text[:500]}..."
                try:
                    client = get_openai_client()
                    summary_response = client.chat.completions.create(
                        model=CONFIG["openai_model_deployment"],
                        messages=[{"role": "user", "content": summary_prompt}],
                        max_tokens=100,
                        temperature=0.1,
                        timeout=20
                    )
                    ai_summary = summary_response.choices[0].message.content.strip()
                    summary = ai_summary if ai_summary else chunk_text[:100] + "..."
                except Exception as e:
                    logger.warning(f"Failed to generate AI summary: {e}")
                    # Fallback summary
                    sentences = chunk_text.split('. ')
                    summary = sentences[0] + "." if len(sentences) > 1 else chunk_text[:100] + "..."
                
                # Create descriptive title using OpenAI
                title_prompt = f"Create a short descriptive title (3-6 words) for this legal text: {chunk_text[:200]}..."
                try:
                    client = get_openai_client()
                    title_response = client.chat.completions.create(
                        model=CONFIG["openai_model_deployment"],
                        messages=[{"role": "user", "content": title_prompt}],
                        max_tokens=20,
                        temperature=0.1,
                        timeout=20
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
                    "paragraph": chunk_text.strip(),
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
        
        logger.info(f"✅ Created {len(documents)} AI-enhanced chunks with intelligent boundaries")
        
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
        
        # Prepare chunk details for response (full content included)
        chunk_details = []
        for i, doc in enumerate(documents):
            upload_result = result[i] if i < len(result) else None
            chunk_details.append({
                "chunk_id": doc["id"],
                "title": doc["title"],
                "content": doc["paragraph"].strip(),  # Full content without truncation
                "content_size": len(doc["paragraph"]),
                "keyphrases": doc["keyphrases"],
                "status": "success" if (upload_result and upload_result.succeeded) else "failed",
                "error": None if (upload_result and upload_result.succeeded) else str(getattr(upload_result, 'error_message', 'Upload failed'))
            })
        
        return {
            "status": "success",
            "message": f"Successfully processed {filename} with {chunking_method} chunking",
            "filename": filename,
            "chunks_created": len(documents),
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "enhancement": enhancement_type,
            "chunking_method": chunk_method_used,
            "chunk_details": chunk_details,
            "content_validation": validation_metrics
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
            chunking_method = req_body.get('chunking_method', 'intelligent')  # 'intelligent', 'heading', or 'basic'
            
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
                    force_reindex=force_reindex,
                    chunking_method=chunking_method
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