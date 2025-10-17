# Azure SQL Database Setup for Chunk Processing
# ===========================================

This guide shows how to set up Azure SQL Database for chunk processing and tracking.

## 🔧 **Quick Setup**

### **1. Install Dependencies**
```bash
pip install -r requirements-azure-sql.txt
```

### **2. Create Azure SQL Database**
```bash
# Using Azure CLI
az sql server create --name myserver --resource-group mygroup --location eastus --admin-user myadmin --admin-password MyPassword123!
az sql db create --resource-group mygroup --server myserver --name chunks-database --service-objective Basic
```

### **3. Configure Environment Variables**

**📁 .env File Locations:**
The system searches for `.env` files in this order:
1. Current directory (where you run the command)
2. Parent directory
3. Working directory

**📝 .env File Content:**
```bash
# Database Configuration
DB_TYPE=azure_sql
AZURE_SQL_SERVER=myserver.database.windows.net
AZURE_SQL_DATABASE=chunks-database
AZURE_SQL_USERNAME=myadmin
AZURE_SQL_PASSWORD=MyPassword123!

# Azure Function URL
AZURE_FUNCTION_URL=http://localhost:7071/api/ProcessDocumentFunction
```

**✨ Pro Tip:** Copy `.env.example` to `.env` and modify:
```bash
copy .env.example .env
# Then edit .env with your actual values
```

### **4. Run Tests**
```bash
# Test with Azure SQL
python enhanced_test_runner_multi_db.py document --verbose

# Force Azure SQL (ignore env DB_TYPE)
python enhanced_test_runner_multi_db.py document --db-type azure_sql --verbose

# Fallback to SQLite
python enhanced_test_runner_multi_db.py document --db-type sqlite --verbose
```

## 📊 **Database Schema**

The Azure SQL implementation creates these tables:

### **documents**
- `id` (INT IDENTITY PRIMARY KEY)
- `filename` (NVARCHAR(255))
- `file_size` (INT)
- `file_hash` (NVARCHAR(64) UNIQUE)
- `content_preview` (NVARCHAR(MAX))
- `created_at` (DATETIME2 DEFAULT GETUTCDATE())
- `processed_at` (DATETIME2 NULL)
- `processing_status` (NVARCHAR(50) DEFAULT 'pending')

### **chunks** (Preprocessing chunks)
- `id` (INT IDENTITY PRIMARY KEY)
- `document_id` (INT FOREIGN KEY)
- `chunk_index` (INT)
- `chunk_content` (NVARCHAR(MAX))
- `chunk_size` (INT)
- `chunk_hash` (NVARCHAR(64))
- `created_at` (DATETIME2 DEFAULT GETUTCDATE())
- `upload_status` (NVARCHAR(50) DEFAULT 'pending')
- `error_message` (NVARCHAR(MAX) NULL)

### **processing_sessions**
- `id` (INT IDENTITY PRIMARY KEY)
- `document_id` (INT FOREIGN KEY)
- `session_start` (DATETIME2 DEFAULT GETUTCDATE())
- `session_end` (DATETIME2 NULL)
- `total_chunks` (INT)
- `successful_chunks` (INT DEFAULT 0)
- `failed_chunks` (INT DEFAULT 0)
- `processing_time_seconds` (REAL NULL)

### **azure_function_chunks** (Azure Function processing results)
- `id` (INT IDENTITY PRIMARY KEY)
- `session_id` (INT FOREIGN KEY)
- `document_id` (INT FOREIGN KEY)
- `azure_chunk_index` (INT)
- `azure_chunk_content` (NVARCHAR(MAX))
- `azure_chunk_size` (INT)
- `azure_chunk_hash` (NVARCHAR(64))
- `upload_status` (NVARCHAR(50) DEFAULT 'pending')
- `error_message` (NVARCHAR(MAX) NULL)
- `processing_time_ms` (REAL NULL)
- `key_phrases` (NVARCHAR(MAX) NULL)
- `created_at` (DATETIME2 DEFAULT GETUTCDATE())

## 🔑 **Authentication Options**

### **1. SQL Authentication (Basic)**
```env
AZURE_SQL_USERNAME=myadmin
AZURE_SQL_PASSWORD=MyPassword123!
```

### **2. Azure AD Authentication (Advanced)**
```python
# In azure_sql_chunk_manager.py, modify connection string:
connection_string = (
    f"DRIVER={driver};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"Authentication=ActiveDirectoryPassword;"
    f"UID={username};"
    f"PWD={password};"
    f"Encrypt=yes;"
)
```

### **3. Managed Identity (Production)**
```python
# For Azure services with managed identity
connection_string = (
    f"DRIVER={driver};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"Authentication=ActiveDirectoryMsi;"
    f"Encrypt=yes;"
)
```

## 🔧 **Configuration Examples**

### **Development (Local SQLite)**
```env
DB_TYPE=sqlite
SQLITE_DB_PATH=chunks_preprocessing.db
```

### **Testing (Azure SQL Basic)**
```env
DB_TYPE=azure_sql
AZURE_SQL_SERVER=test-server.database.windows.net
AZURE_SQL_DATABASE=chunks-test
AZURE_SQL_USERNAME=testuser
AZURE_SQL_PASSWORD=TestPass123!
```

### **Production (Azure SQL with Connection String)**
```env
DB_TYPE=azure_sql
AZURE_SQL_CONNECTION_STRING="Driver={ODBC Driver 18 for SQL Server};Server=prod-server.database.windows.net;Database=chunks-prod;Authentication=ActiveDirectoryMsi;Encrypt=yes;"
```

## 🚀 **Migration from SQLite**

### **1. Export SQLite Data**
```python
import sqlite3
import json

# Export data from SQLite
conn = sqlite3.connect('chunks_preprocessing.db')
cursor = conn.cursor()

# Export documents
cursor.execute("SELECT * FROM documents")
documents = cursor.fetchall()
with open('documents.json', 'w') as f:
    json.dump(documents, f)

# Export other tables...
conn.close()
```

### **2. Import to Azure SQL**
```python
from azure_sql_chunk_manager import AzureSQLChunkManager
import json

# Initialize Azure SQL
db = AzureSQLChunkManager(
    server='myserver.database.windows.net',
    database='chunks-database',
    username='myadmin',
    password='MyPassword123!'
)

# Import data
with open('documents.json', 'r') as f:
    documents = json.load(f)
    # Insert data using db methods...
```

## 📈 **Performance Considerations**

### **SQLite vs Azure SQL**

| Feature | SQLite | Azure SQL |
|---------|--------|-----------|
| **Setup** | Simple file | Requires Azure setup |
| **Scalability** | Single user | Multi-user, scalable |
| **Performance** | Fast local | Network dependent |
| **Backup** | File copy | Azure automated backup |
| **Security** | File permissions | Enterprise-grade |
| **Cost** | Free | Pay per usage |

### **Recommendations**

- **Development**: Use SQLite for simplicity
- **Testing**: Use Azure SQL Basic tier
- **Production**: Use Azure SQL Standard/Premium with proper authentication

## 🛠️ **Troubleshooting**

### **Common Issues**

1. **ODBC Driver Not Found**
   ```bash
   # Install ODBC Driver 18 for SQL Server
   # Windows: Download from Microsoft
   # Linux: sudo apt-get install msodbcsql18
   ```

2. **Connection Timeout**
   ```python
   # Increase timeout in connection string
   connection_string += "Connection Timeout=60;"
   ```

3. **Firewall Issues**
   ```bash
   # Add your IP to Azure SQL firewall
   az sql server firewall-rule create --resource-group mygroup --server myserver --name AllowMyIP --start-ip-address YOUR_IP --end-ip-address YOUR_IP
   ```

4. **Authentication Failed**
   - Check username/password
   - Verify server name format: `server.database.windows.net`
   - Ensure user has db_owner permissions

## 📋 **Testing Checklist**

- [ ] Install pyodbc dependency
- [ ] Configure Azure SQL server and database
- [ ] Set environment variables
- [ ] Test database connection
- [ ] Run document processing test
- [ ] Verify chunk data in Azure SQL
- [ ] Test failure scenarios
- [ ] Check performance vs SQLite

## 🔗 **Additional Resources**

- [Azure SQL Database Documentation](https://docs.microsoft.com/en-us/azure/azure-sql/database/)
- [pyodbc Documentation](https://pyodbc.readthedocs.io/)
- [Azure CLI SQL Commands](https://docs.microsoft.com/en-us/cli/azure/sql)
- [ODBC Driver Download](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)