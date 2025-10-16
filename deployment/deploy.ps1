# Azure Function Deployment Script (PowerShell)
# Usage: .\deploy.ps1 [-FunctionAppName "your-app-name"] [-ResourceGroup "your-rg"]

param(
    [string]$FunctionAppName = "doc-processor-func-app",
    [string]$ResourceGroup = "rg-document-processing",
    [string]$Location = "eastus"
)

$StorageAccount = ($FunctionAppName -replace '[-_]', '') + "storage"

Write-Host "🚀 Deploying Azure Function: $FunctionAppName" -ForegroundColor Green
Write-Host "📍 Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "🌍 Location: $Location" -ForegroundColor Yellow

# Check Azure CLI login
Write-Host "🔐 Checking Azure login..." -ForegroundColor Blue
try {
    az account show --output none
    Write-Host "✅ Already logged in to Azure" -ForegroundColor Green
} catch {
    Write-Host "Please login to Azure first:" -ForegroundColor Red
    az login
}

# Create resource group
Write-Host "📦 Creating resource group..." -ForegroundColor Blue
az group create --name $ResourceGroup --location $Location --output table

# Create storage account
Write-Host "💾 Creating storage account..." -ForegroundColor Blue
az storage account create `
  --name $StorageAccount `
  --location $Location `
  --resource-group $ResourceGroup `
  --sku Standard_LRS `
  --output table

# Create Function App
Write-Host "⚡ Creating Function App..." -ForegroundColor Blue
az functionapp create `
  --resource-group $ResourceGroup `
  --consumption-plan-location $Location `
  --runtime python `
  --runtime-version 3.9 `
  --functions-version 4 `
  --name $FunctionAppName `
  --storage-account $StorageAccount `
  --output table

# Configuration information
Write-Host "⚙️ Application Settings Configuration" -ForegroundColor Magenta
Write-Host "Please set the following environment variables:" -ForegroundColor Yellow
Write-Host ""
Write-Host "az functionapp config appsettings set --name $FunctionAppName --resource-group $ResourceGroup --settings \\" -ForegroundColor Cyan
Write-Host "  AZURE_OPENAI_ENDPOINT='https://your-openai.openai.azure.com/' \\" -ForegroundColor Cyan
Write-Host "  AZURE_OPENAI_KEY='your-openai-key' \\" -ForegroundColor Cyan
Write-Host "  AZURE_OPENAI_MODEL_DEPLOYMENT='gpt-4o-cms' \\" -ForegroundColor Cyan
Write-Host "  AZURE_OPENAI_EMBEDDING_DEPLOYMENT='text-embedding-ada-002' \\" -ForegroundColor Cyan
Write-Host "  AZURE_SEARCH_ENDPOINT='https://your-search.search.windows.net' \\" -ForegroundColor Cyan
Write-Host "  AZURE_SEARCH_KEY='your-search-key' \\" -ForegroundColor Cyan
Write-Host "  AZURE_SEARCH_INDEX='legal-documents-gc'" -ForegroundColor Cyan
Write-Host ""

# Deploy function
Write-Host "🚢 Deploying function code..." -ForegroundColor Blue
func azure functionapp publish $FunctionAppName

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host "🌐 Function URL: https://$FunctionAppName.azurewebsites.net/api/process-document" -ForegroundColor Green
Write-Host "🔑 Don't forget to configure the environment variables mentioned above!" -ForegroundColor Yellow
Write-Host ""
Write-Host "Test your function:" -ForegroundColor Cyan
Write-Host "curl https://$FunctionAppName.azurewebsites.net/api/process-document" -ForegroundColor Cyan