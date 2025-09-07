#!/usr/bin/env python3
"""
Windows Tesseract installation helper and PATH configuration
"""

import os
import sys
import subprocess
import winreg
import urllib.request
import tempfile

def download_tesseract():
    """Download Tesseract installer for Windows"""
    print("📥 Downloading Tesseract OCR installer...")
    
    # Tesseract installer URL (latest version)
    url = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
    
    # Download to temp directory
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "tesseract-installer.exe")
    
    try:
        urllib.request.urlretrieve(url, installer_path)
        print(f"✅ Downloaded to: {installer_path}")
        return installer_path
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None

def add_to_path(directory):
    """Add directory to Windows PATH environment variable"""
    try:
        # Open registry key for environment variables
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        
        # Get current PATH
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""
        
        # Check if directory already in PATH
        if directory.lower() in current_path.lower():
            print(f"✅ {directory} already in PATH")
            return True
            
        # Add directory to PATH
        new_path = f"{current_path};{directory}" if current_path else directory
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        
        print(f"✅ Added {directory} to PATH")
        return True
        
    except Exception as e:
        print(f"❌ Failed to update PATH: {e}")
        return False

def find_tesseract():
    """Find Tesseract installation on Windows"""
    common_paths = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
        r"C:\Users\%USERNAME%\AppData\Local\Tesseract-OCR",
        r"C:\Tesseract-OCR"
    ]
    
    for path in common_paths:
        expanded_path = os.path.expandvars(path)
        tesseract_exe = os.path.join(expanded_path, "tesseract.exe")
        if os.path.exists(tesseract_exe):
            return expanded_path
    
    return None

def configure_pytesseract(tesseract_path):
    """Configure pytesseract to use specific Tesseract path"""
    config_content = f'''# Tesseract configuration for Python OCR
import pytesseract

# Set Tesseract executable path
pytesseract.pytesseract.tesseract_cmd = r"{os.path.join(tesseract_path, 'tesseract.exe')}"

print("✅ Tesseract configured at: {tesseract_path}")
'''
    
    config_file = os.path.join(os.path.dirname(__file__), "tesseract_config.py")
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"✅ Created configuration file: {config_file}")
    return config_file

def test_tesseract():
    """Test if Tesseract is working"""
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Try to get version
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR version: {version}")
        
        # Test with simple image
        from PIL import Image, ImageDraw, ImageFont
        
        # Create test image
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "24222573 1234 kWh", fill='black')
        
        # Test OCR
        text = pytesseract.image_to_string(img)
        print(f"✅ OCR test result: {text.strip()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tesseract test failed: {e}")
        return False

def main():
    """Main installation process"""
    print("🪟 Windows Tesseract OCR Installation Helper")
    print("=" * 50)
    
    # Step 1: Check if already installed
    tesseract_path = find_tesseract()
    if tesseract_path:
        print(f"✅ Found Tesseract at: {tesseract_path}")
        
        # Add to PATH
        add_to_path(tesseract_path)
        
        # Configure pytesseract
        configure_pytesseract(tesseract_path)
        
        # Test installation
        if test_tesseract():
            print("\n🎉 Tesseract OCR is ready!")
            return True
    
    # Step 2: Download installer if not found
    print("🔧 Tesseract not found. Starting installation...")
    
    installer_path = download_tesseract()
    if not installer_path:
        print("❌ Could not download installer")
        print("\n📋 Manual installation steps:")
        print("1. Go to: https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. Download tesseract-ocr-w64-setup-5.x.x.exe")
        print("3. Run installer with default settings")
        print("4. Run this script again")
        return False
    
    # Step 3: Run installer
    print(f"🚀 Running installer: {installer_path}")
    print("   Follow the installation wizard (use default settings)")
    
    try:
        subprocess.run([installer_path], check=True)
        print("✅ Installation completed")
    except subprocess.CalledProcessError:
        print("❌ Installation failed or was cancelled")
        return False
    
    # Step 4: Find and configure after installation
    tesseract_path = find_tesseract()
    if tesseract_path:
        add_to_path(tesseract_path)
        configure_pytesseract(tesseract_path)
        
        if test_tesseract():
            print("\n🎉 Tesseract OCR installation complete!")
            print("\n📋 Next steps:")
            print("1. Restart your command prompt/IDE")
            print("2. Test the electricity calculator")
            return True
    
    print("❌ Installation verification failed")
    return False

if __name__ == "__main__":
    if os.name != 'nt':
        print("❌ This script is for Windows only")
        sys.exit(1)
    
    main()