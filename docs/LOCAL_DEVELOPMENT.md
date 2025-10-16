# Local Development Setup Guide

## 🚀 Quick Start for Local Development

### 1. **Environment Setup**

1. **Copy the environment template:**
   ```bash
   cd azure_function
   cp .env.example .env
   ```

2. **Edit `.env` file with your Azure credentials:**
   ```bash
   # Azure OpenAI Configuration
   AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
   AZURE_OPENAI_KEY=your-openai-api-key
   AZURE_OPENAI_MODEL_DEPLOYMENT=gpt-4o-cms
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

   # Azure Search Configuration  
   AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
   AZURE_SEARCH_KEY=your-search-admin-key
   AZURE_SEARCH_INDEX=legal-documents-gc

   # Function App Settings (for local development)
   FUNCTIONS_WORKER_RUNTIME=python
   AzureWebJobsStorage=UseDevelopmentStorage=true
   ```

### 2. **Install Dependencies**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Azure Functions Core Tools (if not already installed)
# Windows (via npm)
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Or Windows (via chocolatey)
choco install azure-functions-core-tools

# Or macOS (via Homebrew)
brew tap azure/functions
brew install azure-functions-core-tools@4
```

### 3. **Run Locally**
```bash
# Start the function host
func host start --port 7071

# You should see output like:
# Azure Functions Core Tools
# Core Tools Version:       4.x.x
# Function Runtime Version: 4.x.x
# 
# Functions:
#   ProcessDocumentFunction: [GET,POST] http://localhost:7071/api/process-document
```

### 4. **Test the Function**

**Health Check:**
```bash
curl http://localhost:7071/api/process-document
```

**Process Document:**
```bash
python test_function.py
```

## 🔧 Environment Variable Loading

The Azure Function loads environment variables in the following order:

1. **Local Development**: `.env` file in the function directory
2. **System Environment**: OS environment variables
3. **Azure Function App Settings**: When deployed to Azure

### Environment File Locations

The function looks for `.env` files in:
1. Parent directory of the function (`../azure_function/.env`)
2. Current working directory (`./.env`)

### Configuration Validation

When the function starts, it will log the configuration status:
```
🔧 Configuration Status:
  - OpenAI Endpoint: ✅ Set
  - OpenAI Key: ✅ Set
  - OpenAI Model: gpt-4o-cms
  - OpenAI Embedding: text-embedding-ada-002
  - Search Endpoint: ✅ Set
  - Search Key: ✅ Set
  - Search Index: legal-documents-gc
```

## 🐛 Troubleshooting

### Common Issues

1. **"Missing required packages" error**
   ```bash
   pip install -r requirements.txt
   ```

2. **"Environment variable is required" error**
   - Check that your `.env` file exists and has the correct values
   - Verify the file path is correct
   - Ensure no extra spaces around the `=` in the `.env` file

3. **"Could not load .env file" warning**
   - This is usually OK if you have environment variables set another way
   - The function will still work with system environment variables

4. **Function not starting**
   ```bash
   # Check if Azure Functions Core Tools is installed
   func --version
   
   # Install if missing (Windows)
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```

### Debug Mode

Enable verbose logging by setting:
```bash
# In your .env file
AZURE_FUNCTIONS_ENVIRONMENT=Development
```

Or run with verbose output:
```bash
func host start --verbose
```

## 🚀 Next Steps

1. **Test with real documents**: Use `test_function.py` with your own files
2. **Deploy to Azure**: Use the deployment scripts (`deploy.ps1`, `deploy.bat`, or `deploy.sh`)
3. **Monitor performance**: Check logs and Application Insights after deployment

## 📁 Project Structure
```
azure_function/
├── .env                          # Your local environment variables (create this)
├── .env.example                  # Template for environment variables
├── requirements.txt              # Python dependencies
├── host.json                    # Function app configuration
├── local.settings.json          # Local development settings (optional)
├── ProcessDocumentFunction/     # Function implementation
│   ├── function.json
│   └── __init__.py
├── test_function.py            # Test script
├── deploy.ps1                 # PowerShell deployment
├── deploy.bat                 # Batch deployment
└── deploy.sh                  # Bash deployment
```

{
  "search": "*frank",
  "filter": "filename eq 'employee.pdf'",
  "select": "filename, ParagraphId,paragraph,title,summary,keyphrases",
  "top": 50,
  "orderby":"ParagraphId"
}