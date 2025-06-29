#!/usr/bin/env python3
"""
Railway Sync Setup - Configure Railway database connection
"""

import os
import psycopg2
from dotenv import load_dotenv, set_key

# Load current environment
load_dotenv()

def setup_railway_connection():
    """Interactive setup for Railway database connection"""
    print("🚄 Railway Database Setup")
    print("=" * 40)
    print("")
    
    # Check current configuration
    current_render_url = os.getenv('DATABASE_URL')
    current_railway_url = os.getenv('RAILWAY_DATABASE_URL')
    
    print("📋 Current Configuration:")
    print(f"   Render DB: {current_render_url[:50] if current_render_url else 'Not set'}...")
    print(f"   Railway DB: {current_railway_url[:50] if current_railway_url else 'Not set'}...")
    print("")
    
    if not current_render_url:
        print("❌ Your current DATABASE_URL (Render) is not configured!")
        print("   This is needed as the source database for sync.")
        return False
    
    # Get Railway database URL
    if current_railway_url:
        print(f"✅ Railway database URL already configured")
        use_existing = input("Use existing Railway URL? (y/n): ").lower().strip()
        if use_existing == 'y':
            railway_url = current_railway_url
        else:
            railway_url = input("Enter new Railway PostgreSQL URL: ").strip()
    else:
        print("📝 Railway database URL needed for sync target")
        print("")
        print("🔧 How to get Railway database URL:")
        print("1. Go to https://railway.app/dashboard")
        print("2. Create new project or select existing project")
        print("3. Click 'New' → 'Database' → 'PostgreSQL'")
        print("4. Wait for deployment to complete")
        print("5. Go to PostgreSQL service → 'Connect' tab")
        print("6. Copy the 'Database URL' (starts with postgresql://)")
        print("")
        
        print("💡 Your Railway URL should look like:")
        print("   postgresql://postgres:password@mainline.proxy.rlwy.net:port/railway")
        print("")
        railway_url = input("Enter Railway PostgreSQL URL: ").strip()
    
    if not railway_url:
        print("❌ No Railway URL provided")
        return False
    
    # Validate Railway URL format
    if not railway_url.startswith('postgresql://'):
        print("❌ Invalid Railway URL format")
        print("   Expected: postgresql://user:pass@host:port/database")
        return False
    
    # Test Railway connection
    print("")
    print("🔌 Testing Railway database connection...")
    try:
        conn = psycopg2.connect(railway_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Railway connection successful!")
        print(f"📊 PostgreSQL Version: {version[:100]}...")
        
        # Check if database is empty
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]
        print(f"📋 Tables in Railway database: {table_count}")
        
        if table_count > 0:
            print("⚠️ Railway database is not empty")
            overwrite = input("Continue with sync (will overwrite existing data)? (y/n): ").lower().strip()
            if overwrite != 'y':
                print("❌ Sync cancelled by user")
                return False
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Railway connection failed: {e}")
        print("")
        print("🔧 Troubleshooting:")
        print("1. Double-check the Railway database URL")
        print("2. Ensure Railway PostgreSQL service is running")
        print("3. Check Railway service logs for errors")
        return False
    
    # Save to .env file
    print("")
    print("💾 Saving Railway URL to .env file...")
    try:
        env_file = '.env'
        set_key(env_file, 'RAILWAY_DATABASE_URL', railway_url)
        print("✅ Railway URL saved successfully!")
        
        # Update current environment
        os.environ['RAILWAY_DATABASE_URL'] = railway_url
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to save Railway URL: {e}")
        print("💡 You can manually add this line to your .env file:")
        print(f"RAILWAY_DATABASE_URL={railway_url}")
        return False

def main():
    """Main setup function"""
    success = setup_railway_connection()
    
    if success:
        print("")
        print("🎉 Setup completed successfully!")
        print("")
        print("🚀 Next steps:")
        print("1. Run: python railway_sync_fix.py")
        print("2. This will sync all your data from Render to Railway")
        print("3. After successful sync, update your Railway app environment variables")
        print("4. Deploy your Railway app")
        print("")
        
        # Ask if user wants to run sync now
        run_sync = input("Run sync now? (y/n): ").lower().strip()
        if run_sync == 'y':
            print("")
            print("🔄 Starting sync...")
            os.system('python railway_sync_fix.py')
    else:
        print("")
        print("❌ Setup failed. Please check the instructions above and try again.")

if __name__ == "__main__":
    main()