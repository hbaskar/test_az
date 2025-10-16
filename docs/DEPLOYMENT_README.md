# Deployment Scripts and Configuration

This directory contains all deployment-related scripts and configuration files for the Azure Functions project.

## Files Overview

### Deployment Scripts
- **`deploy.ps1`** - PowerShell deployment script for Windows
- **`deploy.sh`** - Bash deployment script for Linux/macOS
- **`deploy.bat`** - Batch deployment script for Windows Command Prompt

### Setup Scripts
- **`setup-windows.ps1`** - Windows development environment setup script

### Configuration Files
- **`azure_environment_variables.json`** - Environment variables formatted for Azure Portal bulk import

## Quick Start

### Windows Users

#### Option 1: PowerShell (Recommended)
```powershell
cd deployment
.\deploy.ps1 -FunctionAppName "your-app-name" -ResourceGroup "your-resource-group"
```

#### Option 2: Command Prompt
```cmd
cd deployment
deploy.bat your-app-name your-resource-group
```

### Linux/macOS Users
```bash
cd deployment
chmod +x deploy.sh
./deploy.sh your-app-name your-resource-group
```

## Development Environment Setup

### Windows Setup
```powershell
cd deployment
.\setup-windows.ps1
```

This script will:
- Check Python version
- Create and activate virtual environment
- Install required dependencies
- Install Azure Functions Core Tools
- Configure development environment

## Deployment Script Features

All deployment scripts provide:

### 🚀 **Automated Deployment**
- Creates Azure Resource Group (if it doesn't exist)
- Creates Azure Storage Account
- Creates Azure Function App
- Deploys function code
- Configures environment variables

### 🔧 **Configuration Management**
- Sets up all required Azure services
- Configures function app settings
- Applies environment variables from `azure_environment_variables.json`

### 🛡️ **Error Handling**
- Validates Azure CLI installation and login
- Checks for required tools and dependencies
- Provides detailed error messages and troubleshooting tips

## Default Configuration

### Default Parameters
- **Function App Name**: `doc-processor-func-app`
- **Resource Group**: `rg-document-processing`
- **Location**: `eastus`
- **Storage Account**: Auto-generated based on function app name

### Services Created
1. **Resource Group** - Container for all resources
2. **Storage Account** - Required for Azure Functions
3. **Function App** - Hosts your Python functions
4. **Application Insights** - Monitoring and logging (optional)

## Environment Variables

The `azure_environment_variables.json` file contains all necessary environment variables:

- **Azure Functions Configuration**
  - `AzureWebJobsStorage`
  - `FUNCTIONS_WORKER_RUNTIME`

- **Azure OpenAI Integration**
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_KEY`
  - `AZURE_OPENAI_MODEL_DEPLOYMENT`
  - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`

- **Azure AI Search Integration**
  - `AZURE_SEARCH_ENDPOINT`
  - `AZURE_SEARCH_KEY`
  - `AZURE_SEARCH_INDEX`

## Prerequisites

### Required Tools
- **Azure CLI** - For Azure resource management
- **Azure Functions Core Tools** - For local development and deployment
- **Python 3.8+** - Runtime for the functions
- **Git** - For source code management

### Azure Services Required
- **Azure OpenAI Service** - For AI key phrase extraction
- **Azure AI Search Service** - For document indexing and search
- **Azure Storage Account** - For function app storage (auto-created)

## Usage Examples

### Deploy with Custom Parameters
```powershell
# PowerShell
.\deploy.ps1 -FunctionAppName "my-doc-processor" -ResourceGroup "my-rg" -Location "westus2"
```

```bash
# Bash
./deploy.sh my-doc-processor my-rg westus2
```

### Deploy to Existing Resource Group
The scripts will detect existing resource groups and use them, only creating resources that don't exist.

## Troubleshooting

### Common Issues

1. **Azure CLI Not Logged In**
   ```bash
   az login
   ```

2. **Missing Azure Functions Core Tools**
   - Windows: Install via npm or download from Microsoft
   - Linux/macOS: Install via package manager or npm

3. **Python Virtual Environment Issues**
   - Run `setup-windows.ps1` to fix environment setup
   - Ensure Python 3.8+ is installed

4. **Resource Naming Conflicts**
   - Storage account names must be globally unique
   - Function app names must be globally unique
   - Use custom names if defaults are taken

### Debugging Tips

1. **Check Azure CLI Version**
   ```bash
   az --version
   ```

2. **Verify Function App Deployment**
   ```bash
   az functionapp list --query "[].{Name:name, State:state, Location:location}"
   ```

3. **Monitor Deployment Logs**
   - Check Azure Portal → Function App → Deployment Center
   - Review Application Insights logs

## Security Considerations

### Environment Variables
- Never commit API keys or secrets to version control
- Use Azure Key Vault for production secrets
- Rotate keys regularly

### Access Control
- Use service principals for automated deployments
- Apply least-privilege access principles
- Enable Azure AD authentication for function apps

## Advanced Configuration

### Custom Deployment
For advanced scenarios, modify the deployment scripts:

1. **Add Additional Azure Services**
   - Cosmos DB for document storage
   - Event Grid for event-driven processing
   - Logic Apps for workflow automation

2. **Configure Networking**
   - Virtual Network integration
   - Private endpoints
   - Application Gateway integration

3. **Set Up CI/CD**
   - GitHub Actions integration
   - Azure DevOps pipelines
   - Automated testing and deployment

## Support

For issues with deployment scripts:
1. Check script output for detailed error messages
2. Verify all prerequisites are installed
3. Ensure Azure subscription has sufficient permissions
4. Review Azure portal for resource creation status

## File Permissions

### Linux/macOS
Make sure deployment scripts are executable:
```bash
chmod +x deploy.sh
```

### Windows
Run PowerShell as Administrator if encountering permission issues:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```