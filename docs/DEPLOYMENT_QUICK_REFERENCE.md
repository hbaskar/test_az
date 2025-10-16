# Quick Deployment Reference

## One-Line Deployments

### Windows PowerShell
```powershell
cd deployment && .\deploy.ps1
```

### Windows Command Prompt  
```cmd
cd deployment && deploy.bat
```

### Linux/macOS
```bash
cd deployment && chmod +x deploy.sh && ./deploy.sh
```

## Custom Parameters

### PowerShell
```powershell
.\deploy.ps1 -FunctionAppName "my-app" -ResourceGroup "my-rg" -Location "westus2"
```

### Bash/Batch
```bash
./deploy.sh my-app my-rg westus2
```

## Setup Development Environment (Windows)
```powershell
cd deployment && .\setup-windows.ps1
```

## Environment Variables Import
1. Copy contents of `azure_environment_variables.json`
2. Go to Azure Portal → Function App → Settings → Environment variables
3. Click "Bulk edit" and paste the JSON content

## Default Values
- **App Name**: doc-processor-func-app
- **Resource Group**: rg-document-processing  
- **Location**: eastus