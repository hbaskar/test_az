# Azure Function Testing Suite

This directory contains comprehensive testing tools for Azure Functions document processing.

## Files Overview

### Test Scripts
- **`test_function.py`** - Original test script with PDF processing and OpenAI integration
- **`enhanced_test_runner.py`** - Enhanced test runner with better error handling and interactive mode
- **`base64_encoder.py`** - Utility script to convert files to base64 format for testing

### Test Data
- **`employee.pdf`** - Sample PDF document for testing document processing (44,245 bytes)

## Quick Start

### Interactive Testing (Recommended)

Run the enhanced test runner in interactive mode:

```bash
cd tests
python enhanced_test_runner.py
```

This provides a menu-driven interface to select and run specific tests:
1. Health Check
2. Document Processing (sample file)
3. Employee PDF (basic)
4. Employee PDF (with retry)
5. Run All Tests

### Command Line Testing

Run specific tests from the command line:

```bash
# Health check
python enhanced_test_runner.py health

# Document processing test
python enhanced_test_runner.py document

# Employee PDF test
python enhanced_test_runner.py employee

# Employee PDF with retry logic
python enhanced_test_runner.py retry

# Run all tests
python enhanced_test_runner.py all
```

### Original Test Script

Use the original test script with enhanced error handling:

```bash
python test_function.py
```

## Test Features

### 1. Health Check (`health`)
- Verifies Azure Function is running and responsive
- Tests the `/api/health` endpoint
- Provides connection diagnostics

### 2. Document Processing (`document`)
- Creates a sample text document
- Tests basic document upload and processing
- Validates chunk processing and AI key phrase extraction

### 3. Employee PDF Processing (`employee`)
- Tests PDF document processing with `employee.pdf`
- Validates PDF content extraction
- Tests OpenAI integration for key phrase extraction
- Includes detailed error reporting for JSON parsing issues

### 4. Retry Logic (`retry`)
- Implements exponential backoff for flaky tests
- Automatically retries failed tests up to 3 times
- Useful for handling temporary OpenAI API issues

### Preparing Test Files

Use the `base64_encoder.py` script to prepare files for testing:

```bash
# Run the encoder utility
python tests/base64_encoder.py
```

**Features:**
- Converts files to base64 format required by the API
- Creates sample legal documents automatically
- Generates ready-to-use JSON request bodies
- Supports .txt, .docx, and .pdf files

## Test Workflow

1. **Start the Function Locally**:
   ```bash
   func start
   ```

2. **Prepare Test Data**:
   ```bash
   python tests/base64_encoder.py
   ```

3. **Run Tests**:
   ```bash
   python tests/test_function.py
   ```

## Integration with Other Testing Tools

### Postman Testing
- The `base64_encoder.py` utility generates content that can be used in Postman requests
- See the `postman/` directory for complete Postman collection
- Documentation is in `docs/POSTMAN_DOCUMENT_PROCESSING_TESTING.md`

### Manual Testing
- Use the encoded files from `base64_encoder.py` for manual API testing
- Copy the generated JSON request bodies to any HTTP client
- Test endpoints: `GET /api/process-document` and `POST /api/process-document`

## Environment Setup

Both test scripts can use environment variables for configuration:

```bash
# Option 1: Create .env file in project root
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your-key
# ... other variables

# Option 2: Set system environment variables
```

## Test Data

The `base64_encoder.py` script creates sample documents:
- **Sample Contract**: Legal service agreement with payment terms
- **Sample Employment**: Employment agreement with confidentiality clauses

These provide realistic test data for document processing and AI key phrase extraction.

## Running Tests in CI/CD

For automated testing:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python tests/test_function.py --automated

# Generate test files
python tests/base64_encoder.py --batch
```

## Adding New Tests

When adding new test files:
1. Place them in this `tests/` directory
2. Follow the naming convention: `test_*.py`
3. Update this README with new test descriptions
4. Ensure tests can run both locally and in CI/CD

## Test Coverage

Current test coverage includes:
- ✅ Health check endpoint
- ✅ Document processing (txt, docx, pdf)
- ✅ Error handling and validation
- ✅ Base64 encoding utilities
- ✅ Sample document generation

Future test additions might include:
- [ ] Performance testing
- [ ] Load testing integration
- [ ] Mock Azure service responses
- [ ] Unit tests for individual functions