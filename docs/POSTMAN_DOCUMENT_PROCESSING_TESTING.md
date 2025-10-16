# Postman Testing for Azure Document Processing Function

This directory contains comprehensive Postman testing scripts for the Azure Document Processing Function that uses AI for key phrase extraction and Azure Search indexing.

## Files Overview

### Postman Collection & Environments
- **`postman_document_processing_collection.json`** - Main test collection
- **`postman_document_processing_environment_local.json`** - Local development environment
- **`postman_document_processing_environment_production.json`** - Production environment

### Helper Scripts
- **`base64_encoder.py`** - Python script to convert files to base64 for testing
- **`azure_environment_variables.json`** - Environment variables for Azure portal

## Function Overview

The Document Processing Function (`/api/process-document`) provides:

### GET Endpoint - Health Check
- **URL**: `GET /api/process-document`
- **Purpose**: Health check and status verification
- **Response**: JSON with status, message, and version

### POST Endpoint - Document Processing
- **URL**: `POST /api/process-document`
- **Purpose**: Process documents with AI key phrase extraction
- **Supported file types**: `.txt`, `.docx`, `.pdf`
- **Required fields**:
  - `filename` - Name of the file with extension
  - `file_content` - Base64-encoded file content
- **Optional fields**:
  - `force_reindex` - Boolean to force reprocessing (default: false)

## Test Categories

### 1. Health Check & Status Tests
- **GET - Health Check**: Verifies function is running and responds correctly

### 2. Document Processing Tests
- **POST - Process Text Document**: Tests successful document processing with sample legal content
- **POST - Process with Force Reindex**: Tests reprocessing existing documents

### 3. Error Handling Tests
- **POST - Missing Required Fields**: Tests validation for missing filename or file_content
- **POST - Unsupported File Type**: Tests rejection of unsupported file extensions
- **POST - Invalid Base64 Content**: Tests handling of malformed base64 data
- **POST - Invalid JSON Body**: Tests malformed JSON request handling
- **PUT - Method Not Allowed**: Tests HTTP method validation

### 4. Sample Document Tests
- **POST - Process PDF Sample**: Demonstrates PDF file processing structure

## Getting Started

### 1. Import Collection and Environments

1. Open Postman
2. Click **Import** → **Upload Files**
3. Import all JSON files:
   - `postman_document_processing_collection.json`
   - `postman_document_processing_environment_local.json`
   - `postman_document_processing_environment_production.json`

### 2. Set Up Environment

#### For Local Testing:
1. Select **"Document Processing - Local Development"** environment
2. Ensure your Azure Functions are running locally: `func host start`
3. Verify environment variables are loaded in your function

#### For Production Testing:
1. Select **"Document Processing - Production"** environment
2. Update `baseUrl` with your Function App URL
3. Set `functionKey` if authentication is required

## Preparing Test Files

### Using the Base64 Encoder Script

1. **Run the encoder script**:
   ```powershell
   python base64_encoder.py
   ```

2. **The script will**:
   - Create sample contract and employment documents
   - List available files for encoding
   - Generate base64 content for Postman testing
   - Provide ready-to-use JSON request bodies

3. **Sample output**:
   ```json
   {
     "filename": "sample_contract.txt",
     "file_content": "VGhpcyBpcyBhIHNhbXBsZS4uLg==",
     "force_reindex": false
   }
   ```

### Manual File Conversion

For custom files, convert to base64:

```python
import base64

with open('your_file.txt', 'rb') as f:
    content = base64.b64encode(f.read()).decode('utf-8')
    print(content)
```

## Test Scenarios Explained

### Sample Test Data

The collection includes base64-encoded sample documents:

1. **Legal Contract**: Contains contract terms, payment schedules, jurisdiction clauses
2. **Service Agreement**: Includes parties, services, compensation, timeline, confidentiality

### Expected AI Processing

The function uses Azure OpenAI to extract key phrases such as:
- Legal terms and concepts
- Important names and entities
- Dates and deadlines
- Contract clauses
- Monetary amounts
- Jurisdictions

### Search Indexing

Processed documents are indexed in Azure AI Search with:
- Document content
- AI-extracted key phrases
- Metadata (filename, processing date)
- Embeddings for semantic search

## Running Tests

### Individual Tests
1. Select any request from the collection
2. Click **Send**
3. Review response and test results

### Collection Runner
1. Right-click collection name → **Run collection**
2. Select environment
3. Configure iterations and delay if needed
4. Click **Run Azure Document Processing Function Tests**

## Test Assertions

Each test includes automated validations:

### Successful Processing Tests
- HTTP 200 status code
- JSON response format
- Required response fields (status, message)
- Reasonable response times (AI processing can take 10-30 seconds)

### Error Handling Tests
- Appropriate HTTP error codes (400, 405, 500)
- Descriptive error messages
- Proper error JSON structure

### Performance Tests
- Response time monitoring
- Timeout handling for AI processing
- Resource usage validation

## Environment Variables Required

Ensure these environment variables are configured:

```json
[
  {
    "name": "AZURE_OPENAI_ENDPOINT",
    "value": "https://your-openai.openai.azure.com/",
    "slotSetting": false
  },
  {
    "name": "AZURE_OPENAI_KEY",
    "value": "your-openai-key",
    "slotSetting": false
  },
  {
    "name": "AZURE_OPENAI_MODEL_DEPLOYMENT",
    "value": "gpt-4o-cms",
    "slotSetting": false
  },
  {
    "name": "AZURE_SEARCH_ENDPOINT",
    "value": "https://your-search.search.windows.net",
    "slotSetting": false
  },
  {
    "name": "AZURE_SEARCH_KEY",
    "value": "your-search-key",
    "slotSetting": false
  },
  {
    "name": "AZURE_SEARCH_INDEX",
    "value": "legal-documents-gc",
    "slotSetting": false
  }
]
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure Azure Functions are running: `func host start`
   - Check port 7071 is available

2. **401 Unauthorized**
   - Verify function key for production
   - Check authentication level in function.json

3. **500 Internal Server Error**
   - Review function logs for detailed errors
   - Verify all environment variables are set
   - Check Azure OpenAI and Search service connectivity

4. **Timeout Errors**
   - AI processing can take 10-30 seconds
   - Increase Postman timeout settings
   - Monitor Azure service quotas and limits

### Debug Tips

1. **Check Function Logs**:
   ```powershell
   func logs
   ```

2. **Test Environment Variables**:
   - Use the health check endpoint
   - Review function startup logs

3. **Validate Base64 Content**:
   - Use online base64 decoders to verify content
   - Check for proper encoding format

## Advanced Testing

### Load Testing

For performance testing with multiple documents:

1. **Create multiple variations** of the base test requests
2. **Use Collection Runner** with multiple iterations
3. **Monitor Azure service metrics** during load tests
4. **Set appropriate delays** between requests to avoid rate limiting

### Integration Testing

Test the complete workflow:

1. **Process Document** → Verify successful processing
2. **Search for Document** → Use Azure Search APIs to verify indexing
3. **Reprocess Same Document** → Test duplicate detection
4. **Force Reindex** → Verify overwrite functionality

### Security Testing

1. **Test without authentication** (should fail in production)
2. **Test with invalid keys** (should return 401/403)
3. **Test with malicious content** (should handle gracefully)
4. **Test oversized files** (should respect limits)

## Monitoring and Analytics

Use Postman's built-in monitoring:

1. **Set up Monitors** for critical endpoints
2. **Configure alerts** for failures or performance issues
3. **Track success rates** and response times
4. **Monitor Azure Function metrics** in parallel

## Newman CLI Integration

Run tests from command line:

```bash
# Install Newman
npm install -g newman

# Run collection
newman run postman_document_processing_collection.json \\
  -e postman_document_processing_environment_local.json \\
  --reporters html,cli \\
  --reporter-html-export results.html

# Run with custom timeout
newman run postman_document_processing_collection.json \\
  -e postman_document_processing_environment_local.json \\
  --timeout-request 60000
```

This comprehensive testing suite ensures your Azure Document Processing Function works correctly across all scenarios and handles errors gracefully.