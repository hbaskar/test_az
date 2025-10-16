#!/bin/bash

# Azure Function Deployment Script
# Usage: ./deploy.sh [function-app-name] [resource-group]

set -e

FUNCTION_APP_NAME=${1:-"doc-processor-func-app"}
RESOURCE_GROUP=${2:-"rg-document-processing"}
LOCATION="eastus"
STORAGE_ACCOUNT="${FUNCTION_APP_NAME//[-_]/}storage"

echo "🚀 Deploying Azure Function: $FUNCTION_APP_NAME"
echo "📍 Resource Group: $RESOURCE_GROUP"
echo "🌍 Location: $LOCATION"

# Login check
echo "🔐 Checking Azure login..."
if ! az account show &>/dev/null; then
    echo "Please login to Azure first:"
    az login
fi

# Create resource group if it doesn't exist
echo "📦 Creating resource group..."
az group create --name $RESOURCE_GROUP --location $LOCATION --output table

# Create storage account
echo "💾 Creating storage account..."
az storage account create \
  --name $STORAGE_ACCOUNT \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --sku Standard_LRS \
  --output table

# Create Function App
echo "⚡ Creating Function App..."
az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name $FUNCTION_APP_NAME \
  --storage-account $STORAGE_ACCOUNT \
  --output table

# Configure application settings (you'll need to set these manually or via script)
echo "⚙️  Configuring application settings..."
echo "Please set the following environment variables in the Azure portal or via Azure CLI:"
echo ""
echo "az functionapp config appsettings set --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --settings \\"
echo "  AZURE_OPENAI_ENDPOINT='https://your-openai.openai.azure.com/' \\"
echo "  AZURE_OPENAI_KEY='your-openai-key' \\"
echo "  AZURE_OPENAI_MODEL_DEPLOYMENT='gpt-4o-cms' \\"
echo "  AZURE_OPENAI_EMBEDDING_DEPLOYMENT='text-embedding-ada-002' \\"
echo "  AZURE_SEARCH_ENDPOINT='https://your-search.search.windows.net' \\"
echo "  AZURE_SEARCH_KEY='your-search-key' \\"
echo "  AZURE_SEARCH_INDEX='legal-documents-gc'"
echo ""

# Deploy the function
echo "🚢 Deploying function code..."
func azure functionapp publish $FUNCTION_APP_NAME

echo ""
echo "✅ Deployment complete!"
echo "🌐 Function URL: https://$FUNCTION_APP_NAME.azurewebsites.net/api/process-document"
echo "🔑 Don't forget to configure the environment variables mentioned above!"
echo ""
echo "Test your function:"
echo "curl https://$FUNCTION_APP_NAME.azurewebsites.net/api/process-document"