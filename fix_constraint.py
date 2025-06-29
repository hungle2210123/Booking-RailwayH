#\!/usr/bin/env python3
"""
Quick script to fix the QuickNotes constraint issue
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import from our project
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def fix_constraint():
    """Fix the QuickNotes constraint to allow flexible note types"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found in environment")
            return False
        
        # Create engine
        engine = create_engine(database_url)
        
        # Apply the fix
        with engine.connect() as conn:
            # Drop the restrictive constraint
            conn.execute(text("ALTER TABLE quick_notes DROP CONSTRAINT IF EXISTS chk_note_type;"))
            
            # Add flexible constraint
            conn.execute(text("""
                ALTER TABLE quick_notes ADD CONSTRAINT chk_note_type CHECK (
                    note_type IS NOT NULL AND LENGTH(note_type) > 0
                );
            """))
            
            conn.commit()
        
        print("✅ Quick notes constraint fixed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing constraint: {e}")
        return False

if __name__ == "__main__":
    fix_constraint()
