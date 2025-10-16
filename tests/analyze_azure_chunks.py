import sqlite3

# Examine Azure Function chunks in detail
conn = sqlite3.connect('chunks_preprocessing.db')
cursor = conn.cursor()

print("🔍 AZURE FUNCTION CHUNKS ANALYSIS")
print("=" * 50)

# Get detailed chunk information
cursor.execute('''
    SELECT af.session_id, af.document_id, d.filename, af.azure_chunk_index, 
           af.azure_chunk_size, af.upload_status, af.error_message, af.processing_time_ms,
           SUBSTR(af.azure_chunk_content, 1, 100) as content_preview,
           af.created_at
    FROM azure_function_chunks af
    JOIN documents d ON af.document_id = d.id
    ORDER BY af.session_id, af.azure_chunk_index
''')

chunks = cursor.fetchall()
print(f"📊 Found {len(chunks)} Azure Function chunks\n")

for chunk in chunks:
    session_id, doc_id, filename, chunk_idx, size, status, error, time_ms, preview, created = chunk
    
    print(f"🔹 Chunk {chunk_idx + 1}")
    print(f"   📄 File: {filename}")
    print(f"   📊 Size: {size} characters")
    print(f"   ✅ Status: {status}")
    print(f"   ⏱️  Processing: {time_ms}ms" if time_ms else "   ⏱️  Processing: Not recorded")
    print(f"   📝 Preview: {preview}..." if preview else "   📝 Preview: (No content)")
    if error:
        print(f"   ❌ Error: {error}")
    print(f"   🕐 Created: {created}")
    print()

# Get summary statistics
cursor.execute('''
    SELECT 
        COUNT(*) as total_chunks,
        COUNT(CASE WHEN upload_status = 'success' THEN 1 END) as successful,
        COUNT(CASE WHEN upload_status = 'failed' THEN 1 END) as failed,
        AVG(azure_chunk_size) as avg_size,
        MIN(azure_chunk_size) as min_size,
        MAX(azure_chunk_size) as max_size,
        AVG(processing_time_ms) as avg_processing_time
    FROM azure_function_chunks
''')

stats = cursor.fetchone()
total, successful, failed, avg_size, min_size, max_size, avg_time = stats

print("📈 SUMMARY STATISTICS")
print("=" * 50)
print(f"📊 Total Azure Function Chunks: {total}")
print(f"✅ Successful: {successful}")
print(f"❌ Failed: {failed}")
print(f"📏 Size Range: {min_size} - {max_size} characters")
print(f"📊 Average Size: {avg_size:.1f} characters" if avg_size else "📊 Average Size: Not available")
print(f"⏱️  Average Processing Time: {avg_time:.1f}ms" if avg_time else "⏱️  Average Processing Time: Not recorded")

conn.close()