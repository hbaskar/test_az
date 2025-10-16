import sqlite3

# Check database tables and Azure Function chunks
conn = sqlite3.connect('chunks_preprocessing.db')
cursor = conn.cursor()

# Check tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print('Tables:', [table[0] for table in tables])

# Check Azure Function chunks count
cursor.execute('SELECT COUNT(*) FROM azure_function_chunks')
count = cursor.fetchone()[0]
print(f'Azure Function chunks: {count}')

# Check recent sessions
cursor.execute('''
    SELECT session_id, document_id, COUNT(*) as chunk_count, 
           MIN(created_at) as first_chunk, MAX(created_at) as last_chunk
    FROM azure_function_chunks 
    GROUP BY session_id, document_id
    ORDER BY session_id DESC
''')
sessions = cursor.fetchall()
print(f'\nAzure Function sessions: {len(sessions)}')
for session in sessions:
    print(f'  Session {session[0]}, Doc {session[1]}: {session[2]} chunks ({session[3]} to {session[4]})')

conn.close()