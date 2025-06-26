#!/usr/bin/env python3
"""
Check current template database structure and fix category mapping
"""
import sqlite3
import os

def check_database_structure():
    # Check if there's a SQLite database file (for debugging)
    db_files = [f for f in os.listdir('.') if f.endswith('.db') or f.endswith('.sqlite')]
    
    if db_files:
        print(f"Found database files: {db_files}")
        
        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Check if message_templates table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message_templates';")
                table_exists = cursor.fetchone()
                
                if table_exists:
                    print(f"\n📋 Found message_templates table in {db_file}")
                    
                    # Get table structure
                    cursor.execute("PRAGMA table_info(message_templates);")
                    columns = cursor.fetchall()
                    print("Table structure:")
                    for col in columns:
                        print(f"  - {col[1]} ({col[2]})")
                    
                    # Get sample data
                    cursor.execute("SELECT template_id, template_name, category, substr(template_content, 1, 50) as content_preview FROM message_templates LIMIT 5;")
                    rows = cursor.fetchall()
                    
                    print("\nSample data:")
                    for row in rows:
                        print(f"  ID: {row[0]}, Name: {row[1]}, Category: {row[2]}, Content: {row[3]}...")
                    
                    # Get unique categories
                    cursor.execute("SELECT DISTINCT category FROM message_templates WHERE category IS NOT NULL;")
                    categories = cursor.fetchall()
                    print(f"\nUnique categories: {[cat[0] for cat in categories]}")
                    
                    # Count templates
                    cursor.execute("SELECT COUNT(*) FROM message_templates;")
                    count = cursor.fetchone()[0]
                    print(f"Total templates: {count}")
                
                conn.close()
                
            except Exception as e:
                print(f"Error checking {db_file}: {e}")
    else:
        print("No SQLite database files found. The app might be using PostgreSQL.")
        print("You'll need to check the PostgreSQL database directly or run the Flask app.")

if __name__ == "__main__":
    check_database_structure()