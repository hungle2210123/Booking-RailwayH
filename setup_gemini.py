#!/usr/bin/env python3
"""
Gemini Setup Helper
Interactive script to help set up Gemini 2.0 Flash for the learning mode.
"""

import os
import subprocess
import sys
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is too old")
        print("💡 Gemini requires Python 3.8 or newer")
        return False

def install_gemini_library():
    """Install google-generativeai library"""
    print("📦 Installing google-generativeai library...")
    
    try:
        # Try importing first
        import google.generativeai as genai
        print("✅ google-generativeai is already installed")
        return True
    except ImportError:
        pass
    
    try:
        # Try pip install
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai"])
        print("✅ google-generativeai installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install google-generativeai")
        print("💡 Try manually: pip install google-generativeai")
        return False

def setup_api_key():
    """Interactive API key setup"""
    print("🔑 Setting up Gemini API Key...")
    
    # Check if already exists
    existing_key = os.getenv("GOOGLE_API_KEY")
    if existing_key:
        print(f"✅ API key already set: {existing_key[:15]}...")
        
        while True:
            choice = input("Would you like to update it? (y/n): ").lower().strip()
            if choice in ['n', 'no']:
                return True
            elif choice in ['y', 'yes']:
                break
            else:
                print("Please enter 'y' or 'n'")
    
    print("\n📋 To get your API key:")
    print("1. Visit: https://makersuite.google.com/app/apikey")
    print("2. Sign in with your Google account")
    print("3. Click 'Create API Key'")
    print("4. Copy the generated key")
    
    while True:
        api_key = input("\n🔐 Enter your Gemini API key (or 'skip' to continue without): ").strip()
        
        if api_key.lower() == 'skip':
            print("⚠️  Skipping API key setup - you can set it later")
            return False
        
        if len(api_key) < 20:
            print("❌ API key seems too short. Please check and try again.")
            continue
        
        if not api_key.startswith("AIza"):
            print("⚠️  API key should start with 'AIza'. Are you sure this is correct?")
            confirm = input("Continue anyway? (y/n): ").lower().strip()
            if confirm not in ['y', 'yes']:
                continue
        
        # Try to set the environment variable
        os.environ["GOOGLE_API_KEY"] = api_key
        
        # Also try to write to .env file
        try:
            env_file = Path(__file__).parent / ".env"
            
            # Read existing .env file
            env_lines = []
            if env_file.exists():
                with open(env_file, 'r') as f:
                    env_lines = f.readlines()
            
            # Remove any existing GOOGLE_API_KEY line
            env_lines = [line for line in env_lines if not line.startswith('GOOGLE_API_KEY=')]
            
            # Add new API key
            env_lines.append(f"GOOGLE_API_KEY={api_key}\n")
            
            # Write back to .env file
            with open(env_file, 'w') as f:
                f.writelines(env_lines)
            
            print(f"✅ API key saved to {env_file}")
            
        except Exception as e:
            print(f"⚠️  Could not save to .env file: {e}")
            print("💡 You can manually add this line to .env:")
            print(f"GOOGLE_API_KEY={api_key}")
        
        print("✅ API key configured!")
        return True

def test_gemini_connection():
    """Test connection to Gemini API"""
    print("🧪 Testing Gemini connection...")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ No API key found - skipping connection test")
        return False
    
    try:
        import google.generativeai as genai
        
        # Configure API
        genai.configure(api_key=api_key)
        
        # Try to list models (lightweight test)
        models = list(genai.list_models())
        print(f"✅ Connected successfully! Found {len(models)} available models")
        
        # Test a simple generation
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content("Say 'Hello, Learning Mode!' in a friendly way.")
        
        if response and response.text:
            print(f"✅ Test response: {response.text.strip()}")
            return True
        else:
            print("⚠️  Connected but no response generated")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        
        if "API_KEY" in str(e).upper():
            print("💡 This looks like an API key issue. Please check your key.")
        elif "QUOTA" in str(e).upper():
            print("💡 This looks like a quota issue. Check your API usage limits.")
        
        return False

def verify_learning_mode_files():
    """Verify learning mode files are present"""
    print("📁 Verifying learning mode files...")
    
    required_files = [
        "learning_mode/__init__.py",
        "learning_mode/routes.py", 
        "learning_mode/services.py",
        "learning_mode/ai_service.py",
        "static/learning_mode/css/learning_mode.css",
        "static/learning_mode/js/learning_mode.js",
        "static/learning_mode/js/chat_assistant.js"
    ]
    
    base_path = Path(__file__).parent
    missing_files = []
    
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"⚠️  {len(missing_files)} files are missing")
        return False
    else:
        print("✅ All learning mode files are present")
        return True

def create_demo_env_file():
    """Create a demo .env file with placeholder"""
    print("📝 Creating demo .env file...")
    
    env_file = Path(__file__).parent / ".env.example"
    
    env_content = """# Hotel Booking System Environment Variables

# Gemini AI Configuration
GOOGLE_API_KEY=your_gemini_api_key_here

# Database Configuration  
DATABASE_SOURCE=auto
LOCAL_DATABASE_URL=postgresql://postgres:locloc123@localhost:5432/hotel_booking
RAILWAY_DATABASE_URL=postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@mainline.proxy.rlwy.net:36647/railway

# Flask Configuration
FLASK_SECRET_KEY=a_secure_secret_key_for_production

# Instructions:
# 1. Copy this file to .env
# 2. Replace 'your_gemini_api_key_here' with your actual API key
# 3. Update other values as needed for your environment
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"✅ Created {env_file}")
        print("💡 Copy this to .env and update with your actual values")
        return True
    except Exception as e:
        print(f"❌ Failed to create example file: {e}")
        return False

def show_next_steps():
    """Show what to do next"""
    print("\n🚀 SETUP COMPLETE! Next Steps:")
    print("=" * 50)
    
    print("\n1️⃣  Start your Flask app:")
    print("   python3 app.py")
    
    print("\n2️⃣  Open your browser and navigate to the app")
    
    print("\n3️⃣  Look for the Learning Mode toggle (top-right corner)")
    
    print("\n4️⃣  Enable Learning Mode and start exploring!")
    
    print("\n5️⃣  Try the AI chat assistant (bottom-right corner)")
    
    print("\n💡 Tips:")
    print("   • Click any UI element to get AI explanations")
    print("   • Ask questions in the chat assistant")
    print("   • Use keyboard shortcuts: Alt+L (toggle), Alt+H (help)")
    print("   • Check the 'powered by' indicator to see if Gemini is active")
    
    print("\n🆘 Need help?")
    print("   • Run: python3 test_gemini_api_live.py")
    print("   • Check the documentation files for more info")

def main():
    """Run the interactive setup"""
    print("🧠 Gemini 2.0 Flash Setup for Learning Mode")
    print("=" * 60)
    print("This script will help you set up Gemini AI for your hotel booking learning system.\n")
    
    steps = [
        ("Check Python Version", check_python_version),
        ("Install Gemini Library", install_gemini_library),
        ("Verify Learning Mode Files", verify_learning_mode_files),
        ("Setup API Key", setup_api_key),
        ("Test Gemini Connection", test_gemini_connection),
        ("Create Demo .env File", create_demo_env_file)
    ]
    
    completed = 0
    total = len(steps)
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name} {'='*20}")
        
        try:
            if step_func():
                print(f"✅ {step_name} completed successfully")
                completed += 1
            else:
                print(f"⚠️  {step_name} had issues (you can continue)")
        except Exception as e:
            print(f"❌ {step_name} failed: {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 Setup Results: {completed}/{total} steps completed")
    
    if completed >= 4:  # Core functionality should work
        print("🎉 Setup successful! Your learning mode is ready!")
        show_next_steps()
    else:
        print("⚠️  Some setup steps had issues, but you can still try using the system.")
        print("💡 The learning mode will work in fallback mode without Gemini.")
    
    return completed >= 4

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)