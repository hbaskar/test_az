# Postman Testing Suite

This directory contains all Postman-related files for testing the Azure Functions project.

## Files Structure

### Collections
- **`postman_document_processing_collection.json`** - Main test collection for the Document Processing Function

### Environments
- **`postman_document_processing_environment_local.json`** - Local development environment variables
- **`postman_document_processing_environment_production.json`** - Production environment variables

### Documentation
- **`POSTMAN_DOCUMENT_PROCESSING_TESTING.md`** - Comprehensive testing guide and documentation

## Quick Start

1. **Import Collection & Environments**:
   - Open Postman
   - Import all JSON files from this directory

2. **Select Environment**:
   - Choose "Document Processing - Local Development" for local testing
   - Choose "Document Processing - Production" for deployed function testing

3. **Start Testing**:
   - For local: Ensure `func host start` is running
   - Run individual tests or the entire collection

## Test Coverage

The collection includes comprehensive tests for:
- Health checks and status endpoints
- Document processing with various file types
- Error handling and validation
- AI key phrase extraction
- Azure Search integration

For detailed instructions, see `POSTMAN_DOCUMENT_PROCESSING_TESTING.md`.