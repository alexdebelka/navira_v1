#!/usr/bin/env python3
"""
User Management Utility for Navira
Command-line tool to create, delete, and manage users
"""

import sys
import os
import sqlite3
import argparse
from auth import DB_PATH, hash_password, create_user

def list_users():
    """List all users in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, created_at, is_active 
            FROM users ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            print("No users found in the database.")
            return
        
        print("\n📋 Current Users:")
        print("=" * 80)
        print(f"{'ID':<3} {'Username':<15} {'Email':<25} {'Role':<8} {'Status':<8} {'Created'}")
        print("-" * 80)
        
        for user in users:
            status = "Active" if user[5] else "Inactive"
            print(f"{user[0]:<3} {user[1]:<15} {user[2]:<25} {user[3]:<8} {status:<8} {user[4]}")
        
        print(f"\nTotal users: {len(users)}")
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def create_new_user(username, email, password, role="user"):
    """Create a new user."""
    try:
        success = create_user(username, email, password, role)
        if success:
            print(f"✅ User '{username}' created successfully!")
            print(f"   Email: {email}")
            print(f"   Role: {role}")
        else:
            print(f"❌ Failed to create user '{username}'. Username or email may already exist.")
    except Exception as e:
        print(f"❌ Error creating user: {e}")

def delete_user(user_id):
    """Delete a user by ID."""
    try:
        from auth import delete_user as auth_delete_user
        
        # Get user info before deletion
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT username, email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            print(f"❌ User with ID {user_id} not found.")
            return
        
        # Delete user using auth function
        success = auth_delete_user(user_id)
        if success:
            print(f"✅ User '{user[0]}' ({user[1]}) deleted successfully!")
        else:
            print(f"❌ Failed to delete user '{user[0]}'")
        
    except Exception as e:
        print(f"❌ Error deleting user: {e}")

def reset_admin_password():
    """Reset admin password to default."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        admin_password_hash = hash_password("admin123")
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (admin_password_hash,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print("✅ Admin password reset to 'admin123'")
        else:
            print("❌ Admin user not found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error resetting admin password: {e}")

def main():
    parser = argparse.ArgumentParser(description="Navira User Management Utility")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List users command
    subparsers.add_parser("list", help="List all users")
    
    # Create user command
    create_parser = subparsers.add_parser("create", help="Create a new user")
    create_parser.add_argument("username", help="Username")
    create_parser.add_argument("email", help="Email address")
    create_parser.add_argument("password", help="Password")
    create_parser.add_argument("--role", choices=["user", "admin"], default="user", help="User role")
    
    # Delete user command
    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("user_id", type=int, help="User ID to delete")
    
    # Reset admin password command
    subparsers.add_parser("reset-admin", help="Reset admin password to default")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🏥 Navira User Management")
    print("=" * 40)
    
    if args.command == "list":
        list_users()
    elif args.command == "create":
        create_new_user(args.username, args.email, args.password, args.role)
    elif args.command == "delete":
        delete_user(args.user_id)
    elif args.command == "reset-admin":
        reset_admin_password()

if __name__ == "__main__":
    main()
