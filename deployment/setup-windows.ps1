# Setup script for Windows Azure Function Development
# This script handles common installation issues on Windows

Write-Host "🚀 Setting up Azure Function Development Environment" -ForegroundColor Green
Write-Host "=" * 60

# Check Python version
Write-Host "🐍 Checking Python version..." -ForegroundColor Blue
$pythonVersion = python --version 2>&1
Write-Host "Python version: $pythonVersion" -ForegroundColor Yellow

# Check if we're in a virtual environment
if ($env:VIRTUAL_ENV) {
    Write-Host "✅ Virtual environment detected: $env:VIRTUAL_ENV" -ForegroundColor Green
} else {
    Write-Host "⚠️ Not in virtual environment. Creating one..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "📁 Created virtual environment: .venv" -ForegroundColor Green
    Write-Host "Please activate it with: .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "Then run this script again." -ForegroundColor Cyan
    exit 1
}

# Upgrade pip first
Write-Host "📦 Upgrading pip..." -ForegroundColor Blue
python -m pip install --upgrade pip

# Try to install with minimal requirements first
Write-Host "🔧 Installing minimal requirements..." -ForegroundColor Blue
try {
    pip install -r requirements-minimal.txt
    Write-Host "✅ Minimal requirements installed successfully!" -ForegroundColor Green
    $useMinimal = $true
} catch {
    Write-Host "❌ Minimal requirements failed. Trying full requirements..." -ForegroundColor Red
    $useMinimal = $false
}

# If minimal failed, try full requirements
if (-not $useMinimal) {
    Write-Host "🔧 Installing full requirements..." -ForegroundColor Blue
    try {
        pip install -r requirements.txt
        Write-Host "✅ Full requirements installed successfully!" -ForegroundColor Green
    } catch {
        Write-Host "❌ Full requirements failed. Trying alternative approaches..." -ForegroundColor Red
        
        # Try installing packages individually
        Write-Host "🔧 Installing packages individually..." -ForegroundColor Blue
        
        $packages = @(
            "azure-functions",
            "azure-functions-worker", 
            "azure-search-documents==11.4.0b8",
            "azure-core==1.29.4",
            "openai==1.3.5",
            "python-docx==0.8.11",
            "PyPDF2==3.0.1", 
            "python-dotenv==1.0.0",
            "requests==2.31.0",
            "typing-extensions==4.8.0"
        )
        
        foreach ($package in $packages) {
            try {
                Write-Host "  Installing $package..." -ForegroundColor Cyan
                pip install $package
                Write-Host "  ✅ $package installed" -ForegroundColor Green
            } catch {
                Write-Host "  ❌ Failed to install $package" -ForegroundColor Red
            }
        }
    }
}

# Check Azure Functions Core Tools
Write-Host "🔧 Checking Azure Functions Core Tools..." -ForegroundColor Blue
try {
    $funcVersion = func --version 2>&1
    Write-Host "✅ Azure Functions Core Tools: $funcVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure Functions Core Tools not found!" -ForegroundColor Red
    Write-Host "Please install it with one of these methods:" -ForegroundColor Yellow
    Write-Host "  npm install -g azure-functions-core-tools@4 --unsafe-perm true" -ForegroundColor Cyan
    Write-Host "  or" -ForegroundColor Yellow
    Write-Host "  choco install azure-functions-core-tools" -ForegroundColor Cyan
}

# Check configuration
Write-Host "📋 Checking configuration files..." -ForegroundColor Blue

if (Test-Path ".env") {
    Write-Host "✅ .env file found" -ForegroundColor Green
} elseif (Test-Path ".env.example") {
    Write-Host "⚠️ .env.example found but no .env file" -ForegroundColor Yellow
    Write-Host "Copy .env.example to .env and configure your Azure credentials" -ForegroundColor Cyan
} else {
    Write-Host "❌ No environment configuration found" -ForegroundColor Red
}

if (Test-Path "local.settings.json") {
    Write-Host "✅ local.settings.json found" -ForegroundColor Green
} else {
    Write-Host "⚠️ No local.settings.json found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Setup completed!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Configure your .env file or local.settings.json with Azure credentials" -ForegroundColor Cyan
Write-Host "2. Run: func host start --port 7071" -ForegroundColor Cyan
Write-Host "3. Test: python test_function.py" -ForegroundColor Cyan