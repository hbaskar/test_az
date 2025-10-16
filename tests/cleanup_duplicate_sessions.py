import sqlite3
from datetime import datetime

def cleanup_duplicate_sessions():
    """Remove duplicate Azure Function processing sessions, keeping only the latest unique data"""
    
    conn = sqlite3.connect('chunks_preprocessing.db')
    cursor = conn.cursor()
    
    print("🧹 CLEANING UP DUPLICATE AZURE FUNCTION SESSIONS")
    print("=" * 60)
    
    # Show current state
    cursor.execute('SELECT COUNT(*) FROM azure_function_chunks')
    total_chunks = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT session_id) FROM azure_function_chunks')
    unique_sessions = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(DISTINCT document_id) 
        FROM azure_function_chunks af
        JOIN documents d ON af.document_id = d.id
    ''')
    unique_documents = cursor.fetchone()[0]
    
    print(f"📊 Current state:")
    print(f"   Total Azure Function chunks: {total_chunks}")
    print(f"   Unique processing sessions: {unique_sessions}")
    print(f"   Unique documents processed: {unique_documents}")
    
    # Show session details
    print(f"\n📋 Session details:")
    cursor.execute('''
        SELECT af.session_id, af.document_id, d.filename, 
               COUNT(af.id) as chunk_count,
               MIN(af.created_at) as first_chunk,
               MAX(af.created_at) as last_chunk
        FROM azure_function_chunks af
        JOIN documents d ON af.document_id = d.id
        GROUP BY af.session_id, af.document_id, d.filename
        ORDER BY af.session_id
    ''')
    
    sessions = cursor.fetchall()
    for session in sessions:
        session_id, doc_id, filename, count, first, last = session
        print(f"   Session {session_id}: {filename} ({count} chunks) - {first} to {last}")
    
    # Check for duplicate document processing
    cursor.execute('''
        SELECT d.filename, COUNT(DISTINCT af.session_id) as session_count,
               GROUP_CONCAT(DISTINCT af.session_id) as sessions
        FROM azure_function_chunks af
        JOIN documents d ON af.document_id = d.id
        GROUP BY d.filename
        HAVING session_count > 1
        ORDER BY d.filename
    ''')
    
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\n⚠️  Documents processed multiple times:")
        for filename, session_count, session_ids in duplicates:
            print(f"   '{filename}': {session_count} sessions ({session_ids})")
        
        print(f"\n🔧 Cleanup strategy:")
        print(f"   - Keep the LATEST session for each document")
        print(f"   - Remove older duplicate sessions")
        
        confirm = input("\nContinue with cleanup? (type 'yes' to confirm): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Cleanup cancelled.")
            conn.close()
            return
        
        # For each document, keep only the latest session
        deleted_total = 0
        for filename, session_count, session_ids in duplicates:
            session_list = [int(s.strip()) for s in session_ids.split(',')]
            sessions_to_keep = max(session_list)  # Keep the highest session ID (latest)
            sessions_to_delete = [s for s in session_list if s != sessions_to_keep]
            
            print(f"\n📄 Processing '{filename}':")
            print(f"   Keeping session {sessions_to_keep}")
            print(f"   Deleting sessions: {sessions_to_delete}")
            
            # Delete chunks from old sessions
            for old_session in sessions_to_delete:
                cursor.execute('''
                    DELETE FROM azure_function_chunks 
                    WHERE session_id = ?
                ''', (old_session,))
                deleted_count = cursor.rowcount
                deleted_total += deleted_count
                print(f"   Deleted {deleted_count} chunks from session {old_session}")
        
        conn.commit()
        
        print(f"\n✅ Cleanup completed!")
        print(f"   Total chunks deleted: {deleted_total}")
        
    else:
        print(f"\n✅ No duplicate document processing found - database is clean!")
    
    # Show final state
    cursor.execute('SELECT COUNT(*) FROM azure_function_chunks')
    final_chunks = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT session_id) FROM azure_function_chunks')
    final_sessions = cursor.fetchone()[0]
    
    print(f"\n📊 Final state:")
    print(f"   Total Azure Function chunks: {final_chunks}")
    print(f"   Unique processing sessions: {final_sessions}")
    
    if final_chunks < total_chunks:
        print(f"   Cleanup saved: {total_chunks - final_chunks} chunks removed")
    
    conn.close()
    print(f"\n🎉 Database cleanup completed!")

if __name__ == "__main__":
    cleanup_duplicate_sessions()