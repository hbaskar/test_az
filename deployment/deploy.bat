@echo off
REM Azure Function Deployment Script for Windows
REM Usage: deploy.bat [function-app-name] [resource-group]

set FUNCTION_APP_NAME=%1
set RESOURCE_GROUP=%2
set LOCATION=eastus

if "%FUNCTION_APP_NAME%"=="" set FUNCTION_APP_NAME=doc-processor-func-app
if "%RESOURCE_GROUP%"=="" set RESOURCE_GROUP=rg-document-processing

set STORAGE_ACCOUNT=%FUNCTION_APP_NAME:-=%
set STORAGE_ACCOUNT=%STORAGE_ACCOUNT:_=%
set STORAGE_ACCOUNT=%STORAGE_ACCOUNT%storage

echo 🚀 Deploying Azure Function: %FUNCTION_APP_NAME%
echo 📍 Resource Group: %RESOURCE_GROUP%
echo 🌍 Location: %LOCATION%

REM Login check
echo 🔐 Checking Azure login...
az account show >nul 2>&1
if errorlevel 1 (
    echo Please login to Azure first:
    az login
)

REM Create resource group
echo 📦 Creating resource group...
az group create --name %RESOURCE_GROUP% --location %LOCATION% --output table

REM Create storage account
echo 💾 Creating storage account...
az storage account create ^
  --name %STORAGE_ACCOUNT% ^
  --location %LOCATION% ^
  --resource-group %RESOURCE_GROUP% ^
  --sku Standard_LRS ^
  --output table

REM Create Function App
echo ⚡ Creating Function App...
az functionapp create ^
  --resource-group %RESOURCE_GROUP% ^
  --consumption-plan-location %LOCATION% ^
  --runtime python ^
  --runtime-version 3.9 ^
  --functions-version 4 ^
  --name %FUNCTION_APP_NAME% ^
  --storage-account %STORAGE_ACCOUNT% ^
  --output table

REM Configuration info
echo ⚙️ Configuring application settings...
echo Please set the following environment variables in the Azure portal or via Azure CLI:
echo.
echo az functionapp config appsettings set --name %FUNCTION_APP_NAME% --resource-group %RESOURCE_GROUP% --settings \
echo   AZURE_OPENAI_ENDPOINT="https://your-openai.openai.azure.com/" \
echo   AZURE_OPENAI_KEY="your-openai-key" \
echo   AZURE_OPENAI_MODEL_DEPLOYMENT="gpt-4o-cms" \
echo   AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-ada-002" \
echo   AZURE_SEARCH_ENDPOINT="https://your-search.search.windows.net" \
echo   AZURE_SEARCH_KEY="your-search-key" \
echo   AZURE_SEARCH_INDEX="legal-documents-gc"
echo.

REM Deploy function
echo 🚢 Deploying function code...
func azure functionapp publish %FUNCTION_APP_NAME%

echo.
echo ✅ Deployment complete!
echo 🌐 Function URL: https://%FUNCTION_APP_NAME%.azurewebsites.net/api/process-document
echo 🔑 Don't forget to configure the environment variables mentioned above!
echo.
echo Test your function:
echo curl https://%FUNCTION_APP_NAME%.azurewebsites.net/api/process-document