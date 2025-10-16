# Windows Installation Troubleshooting Guide

## 🚨 Common Issue: grpcio Compilation Error

The error you're experiencing is common on Windows when packages try to compile C++ extensions. Here are several solutions:

### 🔧 **Solution 1: Use Minimal Requirements (Recommended)**

```powershell
# Use the minimal requirements file instead
pip install -r requirements-minimal.txt
```

This avoids packages that require compilation.

### 🔧 **Solution 2: Use Pre-compiled Wheels**

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install with pre-compiled wheels only
pip install --only-binary=all -r requirements.txt
```

### 🔧 **Solution 3: Install Visual Studio Build Tools**

If you need the full requirements:

1. **Download Visual Studio Build Tools 2022**:
   - Go to: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
   - Download "Build Tools for Visual Studio 2022"

2. **Install with C++ workload**:
   - Run the installer
   - Select "C++ build tools" workload
   - Install

3. **Retry installation**:
   ```powershell
   pip install -r requirements.txt
   ```

### 🔧 **Solution 4: Use Conda Instead of Pip**

```powershell
# Install miniconda if not already installed
# Download from: https://docs.conda.io/en/latest/miniconda.html

# Create conda environment
conda create -n azure-func python=3.9
conda activate azure-func

# Install packages via conda (avoids compilation)
conda install -c conda-forge azure-functions-core-tools
pip install azure-functions azure-functions-worker
pip install azure-search-documents azure-core
pip install openai python-docx PyPDF2 python-dotenv requests
```

### 🔧 **Solution 5: Skip Problematic Packages**

Temporarily remove problematic packages and install individually:

```powershell
# Install core packages first
pip install azure-functions azure-functions-worker
pip install azure-search-documents azure-core  
pip install openai python-docx PyPDF2
pip install python-dotenv requests typing-extensions

# Skip these if they cause issues:
# pip install pydantic  # Can cause compilation issues
# pip install grpcio grpcio-tools  # Compilation problems on Windows
```

## 🛠️ **Automated Setup Script**

Run the automated setup script:

```powershell
# Make sure you're in the azure_function directory
cd azure_function

# Run the setup script
.\setup-windows.ps1
```

This script will:
- Check your Python environment
- Try minimal requirements first
- Fall back to individual package installation
- Validate Azure Functions Core Tools
- Check configuration files

## 🐍 **Python Environment Best Practices**

### **Use Virtual Environment**
```powershell
# Create virtual environment
python -m venv .venv

# Activate (PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Command Prompt)
.\.venv\Scripts\activate.bat
```

### **Verify Environment**
```powershell
# Check you're in virtual environment
python -c "import sys; print(sys.prefix)"

# Should show path to .venv directory
```

## 🔍 **Alternative: Docker Development**

If Windows compilation continues to be problematic, use Docker:

```dockerfile
# Create Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements-minimal.txt .
RUN pip install -r requirements-minimal.txt

COPY . .
CMD ["func", "host", "start", "--host", "0.0.0.0"]
```

```powershell
# Build and run
docker build -t azure-func .
docker run -p 7071:7071 azure-func
```

## ✅ **Quick Test After Setup**

1. **Verify installation**:
   ```powershell
   python -c "import azure.functions; print('Azure Functions OK')"
   python -c "import openai; print('OpenAI OK')"
   python -c "from docx import Document; print('python-docx OK')"
   ```

2. **Test function locally**:
   ```powershell
   func host start --port 7071
   ```

3. **Run test script**:
   ```powershell
   python test_function.py
   ```

## 📞 **Still Having Issues?**

If you continue to have problems:

1. **Check Python version**: Azure Functions work best with Python 3.8-3.11
2. **Use Python from Microsoft Store**: Often has fewer compilation issues
3. **Try WSL**: Use Windows Subsystem for Linux for a Linux-like environment
4. **Use GitHub Codespaces**: Develop in the cloud without local setup issues

The minimal requirements approach should work for most scenarios and avoids the compilation issues entirely.