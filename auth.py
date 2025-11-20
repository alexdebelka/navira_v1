import streamlit as st
import sqlite3
import hashlib
import os
import json
import tempfile
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional, Dict, List

# Configuration with Streamlit secrets support
def get_config():
    """Get configuration from Streamlit secrets or use defaults."""
    if hasattr(st, 'secrets') and st.secrets:
        return {
            'database_path': st.secrets.get("database", {}).get("path", "users.db"),
            'admin_username': st.secrets.get("admin", {}).get("username", "admin"),
            'admin_email': st.secrets.get("admin", {}).get("email", "admin@navira.com"),
            'admin_password': st.secrets.get("admin", {}).get("password", "admin123"),
            'session_expiry_hours': st.secrets.get("session", {}).get("expiry_hours", 24),
            'cleanup_interval': st.secrets.get("session", {}).get("cleanup_interval", 3600)
        }
    else:
        return {
            'database_path': "users.db",
            'admin_username': "admin",
            'admin_email': "admin@navira.com",
            'admin_password': "admin123",
            'session_expiry_hours': 24,
            'cleanup_interval': 3600
        }

# Get configuration
config = get_config()
DB_PATH = config['database_path']
SESSION_FILE = "session.json"

def init_database():
    """Initialize the SQLite database for user management."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Create user_sessions table for session management
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create user_permissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            page_access TEXT NOT NULL,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

    # Seed required users (idempotent)
    try:
        create_default_admin()
    except Exception:
        pass
    try:
        _ensure_pilot_users()
    except Exception:
        pass

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == hashed

def create_user(username: str, email: str, password: str, role: str = 'user') -> bool:
    """Create a new user account."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, role))
        
        user_id = cursor.lastrowid
        
        # Grant default permissions based on role
        if role == 'user':
            default_pages = ['dashboard', 'national', 'hospital_explorer', 'hospital']
        else:  # admin
            default_pages = ['dashboard', 'national', 'hospital_explorer', 'hospital', 'admin']
        
        for page in default_pages:
            cursor.execute('''
                INSERT INTO user_permissions (user_id, page_access)
                VALUES (?, ?)
            ''', (user_id, page))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # Username or email already exists

def delete_user(user_id: int) -> bool:
    """Delete a user and all related data."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get user info before deletion
        cursor.execute("SELECT username, email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return False
        
        # Delete related records first (foreign key constraints)
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        
        # Now delete the user
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        user_deleted = cursor.rowcount
        
        if user_deleted == 0:
            return False
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user and return user data if successful."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, email, password_hash, role, is_active
        FROM users WHERE username = ?
    ''', (username,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user and user[5] and verify_password(password, user[3]):
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[4]
        }
    return None

def create_session(user_id: int) -> str:
    """Create a new session for a user."""
    import secrets
    
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=config['session_expiry_hours'])  # Use config
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update last login
    cursor.execute('''
        UPDATE users SET last_login = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (user_id,))
    
    # Create session
    cursor.execute('''
        INSERT INTO user_sessions (user_id, session_token, expires_at)
        VALUES (?, ?, ?)
    ''', (user_id, session_token, expires_at))
    
    conn.commit()
    conn.close()
    
    return session_token

def validate_session(session_token: str) -> Optional[Dict]:
    """Validate a session token and return user data if valid."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, u.email, u.role, us.expires_at
        FROM users u
        JOIN user_sessions us ON u.id = us.user_id
        WHERE us.session_token = ? AND us.expires_at > CURRENT_TIMESTAMP
    ''', (session_token,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'role': user[3]
        }
    return None

def get_user_permissions(user_id: int) -> List[str]:
    """Get list of pages a user has access to."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT page_access FROM user_permissions
        WHERE user_id = ?
    ''', (user_id,))
    
    permissions = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return permissions

def logout_user(session_token: str):
    """Logout a user by removing their session."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM user_sessions WHERE session_token = ?
    ''', (session_token,))
    
    conn.commit()
    conn.close()

def cleanup_expired_sessions():
    """Remove expired sessions from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP
    ''')
    
    conn.commit()
    conn.close()

# Streamlit session state management
def init_session_state():
    """Initialize session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None

def save_session_to_file(session_token: str, user_data: Dict):
    """Save session data to a file for persistence."""
    try:
        session_data = {
            'session_token': session_token,
            'user': user_data,
            'timestamp': datetime.now().isoformat()
        }
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f)
    except Exception as e:
        print(f"Error saving session: {e}")

def load_session_from_file() -> Optional[Dict]:
    """Load session data from file."""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                session_data = json.load(f)
            
            # Check if session is still valid
            session_token = session_data.get('session_token')
            if session_token:
                user = validate_session(session_token)
                if user:
                    return session_data
        return None
    except Exception as e:
        print(f"Error loading session: {e}")
        return None

def clear_session_file():
    """Clear the session file."""
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception as e:
        print(f"Error clearing session file: {e}")

def check_persistent_session():
    """Check for existing session and restore if valid."""
    # If already authenticated, return True
    if st.session_state.authenticated and st.session_state.user:
        return True
    
    # Try to restore session from file first
    session_data = load_session_from_file()
    if session_data:
        st.session_state.authenticated = True
        st.session_state.user = session_data['user']
        st.session_state.session_token = session_data['session_token']
        st.session_state.current_page = "dashboard"
        return True
    
    # Try to restore session from database
    if st.session_state.session_token:
        user = validate_session(st.session_state.session_token)
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            st.session_state.current_page = "dashboard"
            return True
        else:
            # Session expired, clear state
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.session_token = None
    
    return False

def login_page():
    """Display the login page."""
    st.title("🔐 Login to Navira")
    st.markdown("---")
    
    # Initialize database
    init_database()
    
    # Clean up expired sessions
    cleanup_expired_sessions()
    
    # Check if user is already logged in
    if check_persistent_session():
        st.success(f"Welcome back, {st.session_state.user['username']}!")
        
        # Add navigation options for logged-in users
        st.markdown("---")
        st.markdown("### 🚀 Quick Navigation")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🏠 Go to Dashboard", use_container_width=True):
                from navigation_utils import navigate_to_dashboard
                navigate_to_dashboard()
        
        with col2:
            if st.button("🏥 Hospital Explorer", use_container_width=True):
                from navigation_utils import navigate_to_hospital_explorer
                navigate_to_hospital_explorer()
        
        with col3:
            if st.button("📈 National Overview", use_container_width=True):
                from navigation_utils import navigate_to_national
                navigate_to_national()
        
        # Admin panel option for admin users
        if st.session_state.user['role'] == 'admin':
            st.markdown("---")
            if st.button("⚙️ Admin Panel", use_container_width=True):
                from navigation_utils import navigate_to_admin
                navigate_to_admin()
        
        # Logout option
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            if st.session_state.session_token:
                logout_user(st.session_state.session_token)
            
            # Clear session file
            clear_session_file()
            
            # Clear session state
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.session_token = None
            
            st.success("Logged out successfully!")
            st.rerun()
        
        return True
    
    # Login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username and password:
                user = authenticate_user(username, password)
                if user:
                    # Create session
                    session_token = create_session(user['id'])
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.session_token = session_token
                    
                    # Save session to file for persistence
                    save_session_to_file(session_token, user)
                    
                    st.success("Login successful!")
                    # For limited pilot users, go straight to hospital dashboard with their assigned hospital
                    # Mapping of pilot users to their FINESS codes
                    pilot_user_hospitals = {
                        'andrea.lazzati': '930100037',      # Hôpital Avicenne
                        'federica.papini': '940000573',     # CHIC DE CRETEIL
                        'sergio.carandina': '830100459',    # CLINIQUE SAINT MICHEL
                        'claire.blanchard': '440000271',    # CHU DE NANTES
                        'thomas.auguste': '560008799',      # CHBA VANNES
                        'laurent.genser': '750100125'       # GROUPEMENT HOSPITALIER PITIE-SALPETRIERE
                    }
                    
                    try:
                        uname = (user or {}).get('username', '')
                        is_limited = uname in pilot_user_hospitals
                    except Exception:
                        is_limited = False
                    
                    if is_limited:
                        try:
                            st.session_state._limited_user = True
                            st.session_state.selected_hospital_id = pilot_user_hospitals.get(uname)
                            st.session_state.current_page = "hospital"
                            from navigation_utils import navigate_to_hospital_dashboard
                            navigate_to_hospital_dashboard()
                            return True
                        except Exception:
                            st.session_state.navigate_to = "hospital"
                            st.rerun()
                    else:
                        st.session_state.current_page = "dashboard"
                    
                    # Track login
                    try:
                        from analytics_integration import track_login
                        track_login(username)
                    except Exception as e:
                        print(f"Analytics tracking error: {e}")
                    
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")
    
    # Registration disabled - only admins can create accounts
    st.markdown("---")
    st.info("🔒 **Account Creation Disabled**")
    st.markdown("""
    New accounts can only be created by administrators. 
    Please contact your system administrator to request access.
    """)
    
    return False

def register_page():
    """Display the registration page."""
    st.title("📝 Create New Account")
    st.markdown("---")
    
    with st.form("register_form"):
        username = st.text_input("Username (required)")
        email = st.text_input("Email (required)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit_button = st.form_submit_button("Create Account")
        
        if submit_button:
            if not all([username, email, password, confirm_password]):
                st.error("Please fill in all fields.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters long.")
            else:
                success = create_user(username, email, password)
                if success:
                    st.success("Account created successfully! You can now login.")
                    st.session_state.show_register = False
                    st.rerun()
                else:
                    st.error("Username or email already exists.")
    
    # Back to login
    st.markdown("---")
    if st.button("Back to Login"):
        st.session_state.show_register = False
        st.rerun()

def user_dashboard():
    """Display the user dashboard."""
    if not st.session_state.authenticated or not st.session_state.user:
        st.error("Please login to access the dashboard.")
        return
    
    user = st.session_state.user
    
    st.title(f"👋 Welcome, {user['username']}!")
    st.markdown("---")
    
    # User info
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Your Account")
        st.write(f"**Username:** {user['username']}")
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Role:** {user['role'].title()}")
    
    with col2:
        st.subheader("🔐 Account Actions")
        if st.button("Logout"):
            if st.session_state.session_token:
                logout_user(st.session_state.session_token)
            
            # Clear session file
            clear_session_file()
            
            # Clear session state
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.session_token = None
            
            st.success("Logged out successfully!")
            st.rerun()
    
    # User permissions
    permissions = get_user_permissions(user['id'])
    st.subheader("📋 Your Access")
    st.write("You have access to the following pages:")
    for page in permissions:
        st.write(f"• {page.title()}")
    
    # Quick navigation
    st.subheader("🚀 Quick Navigation")
    
    # Show admin panel button for admin users
    if user['role'] == 'admin':
        if st.button("⚙️ Admin Panel", use_container_width=True):
            from navigation_utils import navigate_to_admin
            navigate_to_admin()
        st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏥 Hospital Explorer"):
            from navigation_utils import navigate_to_hospital_explorer
            navigate_to_hospital_explorer()
    
    with col2:
        if st.button("📈 National Overview"):
            from navigation_utils import navigate_to_national
            navigate_to_national()
    
    with col3:
        if st.button("📊 Hospital Dashboard"):
            from navigation_utils import navigate_to_hospital_dashboard
            navigate_to_hospital_dashboard()



def require_auth(page_name: str = None):
    """Decorator to require authentication for a page."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.authenticated:
                st.error("Please login to access this page.")
                st.stop()
            
            # Check page-specific permissions
            if page_name:
                user_permissions = get_user_permissions(st.session_state.user['id'])
                if page_name not in user_permissions and st.session_state.user['role'] != 'admin':
                    st.error("You don't have permission to access this page.")
                    st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Initialize default admin user
def create_default_admin():
    """Create a default admin user if none exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
    admin_count = cursor.fetchone()[0]
    
    if admin_count == 0:
        # Create default admin user
        admin_username = config['admin_username']
        admin_email = config['admin_email']
        admin_password = config['admin_password'] # Use config
        
        success = create_user(admin_username, admin_email, admin_password, "admin")
        if success:
            print("Default admin user created:")
            print(f"Username: {admin_username}")
            print(f"Password: {admin_password}")
            print("Please change the password after first login!")
    
    conn.close()

def _ensure_pilot_users():
    """Ensure all pilot users exist with default password."""
    pilot_users = [
        ("andrea.lazzati", "andrea.lazzati@navira.com"),
        ("federica.papini", "federica.papini@navira.com"),
        ("sergio.carandina", "sergio.carandina@navira.com"),
        ("claire.blanchard", "claire.blanchard@navira.com"),
        ("thomas.auguste", "thomas.auguste@navira.com"),
        ("laurent.genser", "laurent.genser@navira.com")
    ]
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for username, email in pilot_users:
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if not row:
                # Create user if not exists
                # Note: We call create_user separately to handle password hashing and permissions
                # But we need to close this connection first or use a different connection
                pass
        
        conn.close()
        
        # Now create missing users
        # We do this outside the loop to avoid connection conflicts if create_user opens its own connection
        for username, email in pilot_users:
            # Check again (inefficient but safe)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                print(f"Creating pilot user: {username}")
                create_user(username, email, "12345!", role="user")
                
    except Exception as e:
        print(f"Error ensuring pilot users: {e}")

if __name__ == "__main__":
    # Initialize database and create default admin
    init_database()
    create_default_admin()
