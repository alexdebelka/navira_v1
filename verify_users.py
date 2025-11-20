import sys
from unittest.mock import MagicMock

# Mock streamlit before importing auth
mock_st = MagicMock()
mock_st.secrets = None  # Force default config
sys.modules["streamlit"] = mock_st

import sqlite3
import os
from auth import init_database, _ensure_pilot_users, DB_PATH

# Ensure DB is initialized and users are seeded
print("Initializing database and seeding users...")
init_database()
_ensure_pilot_users()

# Check if users exist
print("\nChecking users in database:")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

pilot_users = [
    "andrea.lazzati",
    "federica.papini",
    "sergio.carandina",
    "claire.blanchard",
    "thomas.auguste",
    "laurent.genser"
]

all_exist = True
for username in pilot_users:
    cursor.execute('SELECT id, email, role FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    if row:
        print(f"✅ User '{username}' found. ID: {row[0]}, Role: {row[2]}")
    else:
        print(f"❌ User '{username}' NOT found!")
        all_exist = False

conn.close()

if all_exist:
    print("\nSUCCESS: All pilot users exist in the database.")
else:
    print("\nFAILURE: Some pilot users are missing.")
