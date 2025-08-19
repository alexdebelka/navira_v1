#!/usr/bin/env python3
"""
Project Cleanup Script for Navira
Safely removes development and testing files
"""

import os
import shutil
import sys

def cleanup_project():
    """Clean up the Navira project by removing unnecessary files."""
    
    print("🧹 Navira Project Cleanup")
    print("=" * 40)
    
    # Files to delete (with confirmation)
    files_to_delete = [
        # Test files
        "test_auth.py",
        "test_navigation.py", 
        "quick_test.py",
        "tests/test_data_pipeline.py",
        
        # Development/Setup files
        "create_test_users.py",
        "setup_auth.py",
        
        # Redundant documentation
        "AUTHENTICATION_README.md",
        "IMPLEMENTATION_SUMMARY.md",
        "ANALYTICS_INTEGRATION_GUIDE.md",
        
        # System files
        ".DS_Store",
    ]
    
    # Directories to delete
    dirs_to_delete = [
        "__pycache__",
        "pages/__pycache__",
        "tests/__pycache__",
        "navira/__pycache__",
        "lib/__pycache__",
    ]
    
    # Optional analytics files (ask user)
    optional_analytics = [
        "analytics_custom.py",
        "analytics_mixpanel.py",
    ]
    
    print("📋 Files to be deleted:")
    for file in files_to_delete:
        if os.path.exists(file):
            print(f"  - {file}")
    
    print("\n📁 Directories to be deleted:")
    for dir in dirs_to_delete:
        if os.path.exists(dir):
            print(f"  - {dir}/")
    
    print("\n❓ Optional analytics files (you can choose):")
    for file in optional_analytics:
        if os.path.exists(file):
            print(f"  - {file}")
    
    # Confirm deletion
    print("\n⚠️  WARNING: This will permanently delete the files listed above.")
    confirm = input("Do you want to proceed? (yes/no): ").lower().strip()
    
    if confirm not in ['yes', 'y']:
        print("❌ Cleanup cancelled.")
        return
    
    # Delete files
    deleted_files = []
    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.remove(file)
                deleted_files.append(file)
                print(f"✅ Deleted: {file}")
            except Exception as e:
                print(f"❌ Error deleting {file}: {e}")
    
    # Delete directories
    deleted_dirs = []
    for dir in dirs_to_delete:
        if os.path.exists(dir):
            try:
                shutil.rmtree(dir)
                deleted_dirs.append(dir)
                print(f"✅ Deleted: {dir}/")
            except Exception as e:
                print(f"❌ Error deleting {dir}: {e}")
    
    # Ask about optional analytics files
    print("\n🤔 Optional Analytics Files:")
    print("These files provide alternative analytics solutions:")
    print("- analytics_custom.py: Custom database analytics")
    print("- analytics_mixpanel.py: Mixpanel integration")
    print("You're currently using Google Analytics 4, so these are optional.")
    
    for file in optional_analytics:
        if os.path.exists(file):
            delete_optional = input(f"Delete {file}? (yes/no): ").lower().strip()
            if delete_optional in ['yes', 'y']:
                try:
                    os.remove(file)
                    deleted_files.append(file)
                    print(f"✅ Deleted: {file}")
                except Exception as e:
                    print(f"❌ Error deleting {file}: {e}")
            else:
                print(f"✅ Kept: {file}")
    
    # Summary
    print("\n📊 Cleanup Summary:")
    print(f"✅ Files deleted: {len(deleted_files)}")
    print(f"✅ Directories deleted: {len(deleted_dirs)}")
    
    if deleted_files:
        print("\n🗑️  Deleted files:")
        for file in deleted_files:
            print(f"  - {file}")
    
    if deleted_dirs:
        print("\n🗑️  Deleted directories:")
        for dir in deleted_dirs:
            print(f"  - {dir}/")
    
    print("\n🎉 Project cleanup completed!")
    print("\n📋 Remaining essential files:")
    essential_files = [
        "app.py", "main.py", "auth.py", "auth_wrapper.py", "sidebar_utils.py",
        "analytics_ga4.py", "analytics_integration.py", "analytics_dashboard.py",
        "pages/dashboard.py", "pages/national.py", "pages/hospital_explorer.py",
        "users.db", "session.json", "requirements.txt", "README.md"
    ]
    
    for file in essential_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (missing!)")

if __name__ == "__main__":
    cleanup_project()
