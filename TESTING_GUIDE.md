# Azure Function Testing - Quick Start Guide

## 🎯 What We've Built

You now have a comprehensive testing suite for your Azure Function document processing:

### ✅ Complete File Organization
- **`postman/`** - Postman collections and environment files
- **`deployment/`** - Azure deployment scripts and configurations  
- **`docs/`** - Complete documentation and guides
- **`tests/`** - Enhanced testing tools and test data

### ✅ Enhanced Testing Tools
1. **Enhanced Test Runner** (`tests/enhanced_test_runner.py`) - Interactive and command-line testing
2. **Original Test Script** (`tests/test_function.py`) - Comprehensive PDF processing tests  
3. **Base64 Encoder** (`tests/base64_encoder.py`) - File encoding utility
4. **Employee PDF Test Data** (`tests/employee.pdf`) - Real PDF for testing

## 🚀 Getting Started

### Step 1: Start Your Azure Function
```bash
# In the project root directory (c:\Users\harib\projects\test_az)
func host start
```

### Step 2: Run Tests (Choose Your Preferred Method)

#### Option A: Interactive Testing (Recommended for New Users)
```bash
cd tests
python enhanced_test_runner.py
```
This gives you a menu to select tests.

#### Option B: Command Line Testing (Quick Tests)
```bash
cd tests

# Quick health check
python enhanced_test_runner.py health

# Test employee PDF processing
python enhanced_test_runner.py employee  

# Run all tests
python enhanced_test_runner.py all
```

#### Option C: Original Script (Full Features)
```bash
cd tests
python test_function.py
```

### Step 3: Use Postman for API Testing
1. Import `postman/postman_document_processing_collection.json` 
2. Import environment files from `postman/` directory
3. Run the collection tests

## 🔧 Troubleshooting

### If Health Check Fails
1. **Start the Function**: Run `func host start` in the project root
2. **Check Port**: Ensure it's running on `http://localhost:7071`
3. **Check Logs**: Look for startup errors in the function output

### If PDF Processing Fails
1. **OpenAI JSON Errors**: Try the retry version: `python enhanced_test_runner.py retry`
2. **PDF Issues**: The `employee.pdf` is a real 44KB employment document
3. **Timeout Issues**: Large PDFs may take 30-60 seconds to process

### If Tests Can't Find Files
- Always run tests from the `tests/` directory: `cd tests`
- The test scripts look for `employee.pdf` in the current directory

## 📊 Test Features

### Comprehensive Error Handling
- **PDF Parsing Errors** - Detailed diagnostics for corrupted PDFs
- **OpenAI API Issues** - JSON parsing error detection and retry logic
- **Network Issues** - Connection timeout handling and diagnostics
- **Function Errors** - Azure Function error analysis and reporting

### Advanced Test Capabilities
- **Interactive Mode** - Menu-driven test selection
- **Retry Logic** - Exponential backoff for flaky tests
- **Test Statistics** - Detailed pass/fail reporting and timing
- **Multiple Test Files** - Support for various document types

### Real-World Testing
- **Employee Handbook PDF** - Tests complex document processing
- **OpenAI Integration** - Validates AI key phrase extraction  
- **Base64 Encoding** - Handles file upload simulation
- **Error Scenarios** - Tests invalid inputs and error handling

## 📁 File Structure Summary

```
test_az/
├── function_app.py              # Main Azure Function code
├── requirements.txt             # Python dependencies
├── host.json                    # Function configuration
├── local.settings.json          # Local environment settings
├── postman/                     # Postman testing files
│   ├── postman_document_processing_collection.json
│   ├── local_environment.postman_environment.json
│   └── production_environment.postman_environment.json
├── deployment/                  # Deployment configurations
│   └── azure_environment_variables.env
├── docs/                        # Documentation
│   ├── POSTMAN_DOCUMENT_PROCESSING_TESTING.md
│   └── DEPLOYMENT_GUIDE.md
└── tests/                       # Testing tools
    ├── enhanced_test_runner.py  # New enhanced test runner
    ├── test_function.py         # Original comprehensive test script
    ├── base64_encoder.py        # File encoding utility
    ├── employee.pdf             # Test PDF document (44KB)
    └── README.md                # Testing documentation
```

## 🎉 Next Steps

1. **Start Testing**: Run `func host start` then try the interactive tester
2. **Explore Features**: Test different document types and error scenarios
3. **Monitor Performance**: Check processing times and success rates
4. **Deploy to Azure**: Use the deployment guide in `docs/DEPLOYMENT_GUIDE.md`
5. **CI/CD Integration**: Use command-line testing for automated pipelines

## 💡 Pro Tips

- **Use Retry Logic** for unstable OpenAI API responses
- **Monitor Function Logs** for detailed error diagnostics  
- **Test Multiple File Types** - PDFs, text files, different sizes
- **Check API Quotas** if OpenAI integration fails consistently
- **Use Interactive Mode** for exploring test failures

Happy Testing! 🧪✨