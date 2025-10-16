# Azure Document Processing Function# Azure Function: Document Processing with AI Key Phrases



A serverless Azure Function that processes documents with AI-powered key phrase extraction and Azure Search integration.This Azure Function converts the `process_document_with_ai_keyphrases` notebook function into a serverless HTTP-triggered Azure Function.



## 📚 Documentation## 🚀 Features



All project documentation has been organized in the [`docs/`](docs/) directory:- **HTTP Trigger**: Accepts POST requests with document content

- **Multi-format Support**: Handles .txt, .docx, and .pdf files

- **[📖 Complete Documentation](docs/INDEX.md)** - Start here for full documentation index- **AI-Powered Key Phrases**: Uses Azure OpenAI to extract intelligent key phrases

- **[🚀 Quick Start](docs/README.md)** - Main project guide and setup- **Azure Search Integration**: Automatically indexes processed documents

- **[💻 Local Development](docs/LOCAL_DEVELOPMENT.md)** - Development environment setup- **Proper Paragraph Extraction**: Uses document styles for better chunking

- **[🚀 Deployment](docs/DEPLOYMENT_QUICK_REFERENCE.md)** - Quick deployment commands- **Error Handling**: Comprehensive error handling and logging



## 🏗️ Project Structure## 📁 Project Structure



``````

├── docs/                           # 📚 All documentationazure_function/

├── deployment/                     # 🚀 Deployment scripts├── requirements.txt              # Python dependencies

├── postman/                        # 🧪 Testing artifacts├── host.json                    # Function app configuration

├── ProcessDocumentFunction/        # ⚙️ Function code├── .env.example                 # Environment variables template

└── ...                            # Other project files├── ProcessDocumentFunction/     # Main function

```│   ├── function.json           # Function binding configuration

│   └── __init__.py            # Function implementation

## ⚡ Quick Commands└── README.md                   # This file

```

### Local Development

```bash## 🔧 Setup Instructions

# Setup environment (Windows)

cd deployment && .\setup-windows.ps1### 1. **Prerequisites**

- Azure Functions Core Tools v4

# Start function locally- Python 3.8+ 

func start- Azure OpenAI resource

```- Azure AI Search resource



### Deployment### 2. **Environment Configuration**

```bash

# Deploy to Azure (Windows PowerShell)You can configure the function using either method:

cd deployment && .\deploy.ps1

#### **Method 1: Using .env file (Recommended)**

# Deploy to Azure (Linux/macOS)```bash

cd deployment && chmod +x deploy.sh && ./deploy.sh# Copy the template

```cp .env.example .env



### Testing# Edit .env with your values

```bashAZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/

# Prepare test filesAZURE_OPENAI_KEY=your-openai-api-key

python base64_encoder.pyAZURE_OPENAI_MODEL_DEPLOYMENT=gpt-4o-cms

AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Import Postman collection from postman/ directoryAZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net

```AZURE_SEARCH_KEY=your-search-admin-key

AZURE_SEARCH_INDEX=legal-documents-gc

## 🔗 Key Features```



- **HTTP Trigger** for document processing#### **Method 2: Using local.settings.json (Azure Functions Standard)**

- **Multi-format Support** (.txt, .docx, .pdf)```bash

- **AI Key Phrase Extraction** via Azure OpenAI# Edit local.settings.json with your values

- **Search Integration** with Azure AI Search# This file is automatically loaded by Azure Functions Core Tools

- **Comprehensive Testing** with Postman collection```



For detailed information, see the [complete documentation](docs/INDEX.md).The function will automatically detect and load configuration from either source.

### 3. **Local Development**

```bash
# Navigate to function directory
cd azure_function

# Install dependencies
pip install -r requirements.txt

# Start local function host
func host start --port 7071
```

### 4. **Deploy to Azure**

```bash
# Login to Azure
az login

# Create resource group (if needed)
az group create --name rg-document-processing --location eastus

# Create Function App
az functionapp create \
  --resource-group rg-document-processing \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name your-function-app-name \
  --storage-account yourstorageaccount

# Deploy function
func azure functionapp publish your-function-app-name
```

## 🔗 API Usage

### **Health Check (GET)**
```bash
curl https://your-function-app.azurewebsites.net/api/process-document
```

**Response:**
```json
{
  "status": "healthy",
  "message": "Document Processing Function is running",
  "version": "1.0.0"
}
```

### **Process Document (POST)**

```bash
curl -X POST https://your-function-app.azurewebsites.net/api/process-document \
  -H "Content-Type: application/json" \
  -d '{
    "file_content": "base64-encoded-file-content",
    "filename": "contract.docx",
    "force_reindex": false
  }'
```

**Request Body:**
```json
{
  "file_content": "base64-encoded-file-content",  // Required: Base64 encoded file
  "filename": "document.docx",                    // Required: Original filename  
  "force_reindex": false                          // Optional: Overwrite existing
}
```

**Success Response:**
```json
{
  "status": "success",
  "message": "Successfully processed document.docx with AI key phrases",
  "filename": "document.docx",
  "chunks_created": 25,
  "successful_uploads": 25,
  "failed_uploads": 0,
  "enhancement": "AI_keyphrases_and_titles"
}
```

**Error Response:**
```json
{
  "status": "error", 
  "message": "Failed to extract document content"
}
```

## 📤 Example Usage (Python)

```python
import base64
import requests
import json

# Read and encode file
with open('document.docx', 'rb') as f:
    file_content = base64.b64encode(f.read()).decode('utf-8')

# Prepare request
payload = {
    "file_content": file_content,
    "filename": "document.docx", 
    "force_reindex": False
}

# Make request
response = requests.post(
    'https://your-function-app.azurewebsites.net/api/process-document',
    json=payload,
    headers={'Content-Type': 'application/json'}
)

result = response.json()
print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Processed {result['chunks_created']} chunks")
```

## 🔒 Security Considerations

### **Authentication**
- Function uses `authLevel: "function"` requiring a function key
- Add `?code=your-function-key` to requests in production
- Consider using `authLevel: "admin"` for higher security

### **Input Validation**
- File size limits handled by Azure Functions (100MB default)
- File type validation (only .txt, .docx, .pdf allowed)
- Base64 content validation

### **Environment Variables**
- All sensitive keys stored as Application Settings
- Never commit actual keys to source control

## 📊 Monitoring & Logging

- Application Insights integration for monitoring
- Structured logging throughout the function
- Error tracking and performance metrics
- Custom telemetry for document processing stats

## ⚡ Performance Considerations

- **Timeout**: Configured for 10 minutes (adjustable in host.json)
- **Memory**: Azure Functions automatically scales based on usage
- **Concurrency**: Supports multiple concurrent requests
- **Caching**: Consider adding Redis cache for frequently processed documents

## 🛠️ Customization Options

### **Document Types**
Add support for additional file types in `process_document_content()`:
```python
elif file_extension == 'rtf':
    # Add RTF processing logic
    return process_rtf_content(file_path)
```

### **AI Models**
Configure different models for different document types:
```python
model_deployment = "gpt-4" if document_type == "legal" else "gpt-3.5-turbo"
```

### **Search Index**
Customize document structure in the indexing section:
```python
document = {
    # Add custom fields
    "custom_field": extract_custom_data(para),
    "confidence_score": calculate_confidence(para)
}
```

## 🐛 Troubleshooting

### **Common Issues**

1. **Import Errors**: Ensure all dependencies in requirements.txt are installed
2. **Authentication Failures**: Verify environment variables are set correctly  
3. **Timeout Issues**: Increase function timeout in host.json for large documents
4. **Memory Issues**: Consider chunking very large documents

### **Debug Locally**
```bash
# Enable debug logging
export AZURE_FUNCTIONS_ENVIRONMENT=Development

# Run with verbose output
func host start --verbose
```

## 📈 Future Enhancements

- **Batch Processing**: Support multiple documents in single request
- **Webhook Support**: Notify external systems when processing completes
- **Custom Models**: Support for domain-specific AI models
- **Real-time Status**: WebSocket support for processing progress
- **Document Validation**: Pre-processing validation and sanitization