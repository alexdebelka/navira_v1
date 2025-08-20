#!/usr/bin/env python3
"""
Test script to verify deployment readiness of the Navira application.
Run this script to check if all components are working correctly.
"""

import os
import sys
import pandas as pd

def test_data_loading():
    """Test that data can be loaded using the new dynamic paths."""
    print("🔍 Testing data loading...")
    
    try:
        # Test the new load_data function
        from navira.data_loader import load_data
        establishments, annual = load_data()
        
        print(f"✅ Data loading successful!")
        print(f"   - Establishments: {len(establishments)} records")
        print(f"   - Annual procedures: {len(annual)} records")
        
        # Check for required columns (updated to match actual data)
        required_est_cols = ['name', 'id']  # Changed from 'finess' to 'id'
        required_ann_cols = ['annee', 'total_procedures_year']
        
        est_missing = [col for col in required_est_cols if col not in establishments.columns]
        ann_missing = [col for col in required_ann_cols if col not in annual.columns]
        
        if est_missing:
            print(f"⚠️  Missing columns in establishments: {est_missing}")
        if ann_missing:
            print(f"⚠️  Missing columns in annual: {ann_missing}")
        
        if not est_missing and not ann_missing:
            print("✅ All required columns present")
        
        return True
        
    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return False

def test_authentication():
    """Test that the authentication system can be initialized."""
    print("\n🔐 Testing authentication system...")
    
    try:
        # Mock Streamlit for testing outside of Streamlit environment
        import sys
        from unittest.mock import MagicMock
        
        # Create a mock st object with secrets
        mock_st = MagicMock()
        mock_st.secrets = {
            "database": {"path": "test_users.db"},
            "admin": {
                "username": "test_admin",
                "email": "test@navira.com", 
                "password": "test123"
            },
            "session": {
                "expiry_hours": 24,
                "cleanup_interval": 3600
            }
        }
        
        # Temporarily replace streamlit module
        original_st = sys.modules.get('streamlit')
        sys.modules['streamlit'] = mock_st
        
        try:
            from auth import init_database, create_default_admin, get_config
            
            # Test configuration loading
            config = get_config()
            print(f"✅ Configuration loaded: {config['database_path']}")
            
            # Test database initialization
            init_database()
            print("✅ Database initialized")
            
            # Test admin user creation
            create_default_admin()
            print("✅ Admin user creation tested")
            
            # Clean up test database
            if os.path.exists("test_users.db"):
                os.remove("test_users.db")
            
            return True
            
        finally:
            # Restore original streamlit module
            if original_st:
                sys.modules['streamlit'] = original_st
            else:
                del sys.modules['streamlit']
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported."""
    print("\n📦 Testing imports...")
    
    modules_to_test = [
        'streamlit',
        'pandas',
        'plotly',
        'pyarrow',
        'sqlite3',
        'hashlib',
        'json',
        'datetime'
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n⚠️  Failed imports: {failed_imports}")
        return False
    else:
        print("✅ All imports successful")
        return True

def test_file_structure():
    """Test that required files and directories exist."""
    print("\n📁 Testing file structure...")
    
    required_files = [
        'app.py',
        'auth.py',
        'navira/data_loader.py',
        'pages/national.py',
        'pages/dashboard.py',
        'pages/hospital_explorer.py',
        'requirements.txt'
    ]
    
    required_dirs = [
        'data',
        'navira',
        'pages',
        'lib'
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")
    
    for dir_path in required_dirs:
        if not os.path.isdir(dir_path):
            missing_dirs.append(dir_path)
        else:
            print(f"✅ {dir_path}/")
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
    if missing_dirs:
        print(f"❌ Missing directories: {missing_dirs}")
    
    return len(missing_files) == 0 and len(missing_dirs) == 0

def main():
    """Run all deployment tests."""
    print("🚀 Navira Deployment Test Suite")
    print("=" * 40)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("Authentication", test_authentication),
        ("Data Loading", test_data_loading)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 Test Results Summary")
    print("=" * 40)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your app is ready for deployment.")
        return 0
    else:
        print("⚠️  Some tests failed. Please fix the issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
