import sqlite3
from datetime import datetime

def cleanup_placeholder_chunks():
    """Remove old placeholder Azure Function chunks that contain 'content not available'"""
    
    conn = sqlite3.connect('chunks_preprocessing.db')
    cursor = conn.cursor()
    
    print("🧹 CLEANING UP PLACEHOLDER AZURE FUNCTION CHUNKS")
    print("=" * 60)
    
    # First, show what we're about to clean up
    cursor.execute('''
        SELECT COUNT(*) 
        FROM azure_function_chunks 
        WHERE azure_chunk_content LIKE '%content not available%'
    ''')
    placeholder_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM azure_function_chunks')
    total_count = cursor.fetchone()[0]
    
    print(f"📊 Current state:")
    print(f"   Total Azure Function chunks: {total_count}")
    print(f"   Placeholder chunks to remove: {placeholder_count}")
    print(f"   Real content chunks to keep: {total_count - placeholder_count}")
    
    if placeholder_count == 0:
        print("✅ No placeholder chunks found - database is already clean!")
        conn.close()
        return
    
    # Show examples of what will be removed
    print(f"\n🔍 Examples of placeholder chunks to be removed:")
    cursor.execute('''
        SELECT session_id, azure_chunk_index, azure_chunk_size, azure_chunk_content, created_at
        FROM azure_function_chunks 
        WHERE azure_chunk_content LIKE '%content not available%'
        ORDER BY created_at
        LIMIT 5
    ''')
    
    for row in cursor.fetchall():
        session, index, size, content, created = row
        print(f"   Session {session}, Chunk {index+1}: {size} chars - '{content}' ({created})")
    
    if placeholder_count > 5:
        print(f"   ... and {placeholder_count - 5} more placeholder chunks")
    
    # Confirm cleanup
    print(f"\n⚠️  This will permanently delete {placeholder_count} placeholder chunks.")
    confirm = input("Continue with cleanup? (type 'yes' to confirm): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cleanup cancelled.")
        conn.close()
        return
    
    # Perform cleanup
    print(f"\n🔄 Removing placeholder chunks...")
    cursor.execute('''
        DELETE FROM azure_function_chunks 
        WHERE azure_chunk_content LIKE '%content not available%'
    ''')
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    # Show final state
    cursor.execute('SELECT COUNT(*) FROM azure_function_chunks')
    remaining_count = cursor.fetchone()[0]
    
    print(f"✅ Cleanup completed!")
    print(f"   Deleted: {deleted_count} placeholder chunks")
    print(f"   Remaining: {remaining_count} real content chunks")
    
    # Show examples of remaining chunks
    print(f"\n📊 Remaining real content chunks:")
    cursor.execute('''
        SELECT session_id, azure_chunk_index, azure_chunk_size, 
               SUBSTR(azure_chunk_content, 1, 80) as preview, created_at
        FROM azure_function_chunks 
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    
    for row in cursor.fetchall():
        session, index, size, preview, created = row
        print(f"   Session {session}, Chunk {index+1}: {size} chars - {preview}... ({created})")
    
    conn.close()
    print(f"\n🎉 Database cleanup completed successfully!")

if __name__ == "__main__":
    cleanup_placeholder_chunks()