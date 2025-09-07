#!/usr/bin/env python3
"""
Installation script for Python OCR dependencies
Replaces expensive API calls with free Tesseract OCR
"""

import subprocess
import sys
import os
import platform

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Error: {e}")
        return False

def install_python_packages():
    """Install Python OCR packages"""
    packages = [
        "pytesseract==0.3.10",
        "Pillow==10.0.1", 
        "opencv-python==4.8.1.78",
        "numpy==1.24.3"
    ]
    
    for package in packages:
        success = run_command(f"pip install {package}", f"Installing {package}")
        if not success:
            print(f"⚠️ Failed to install {package} - continuing...")

def install_tesseract_engine():
    """Install Tesseract OCR engine based on OS"""
    system = platform.system().lower()
    
    if system == "linux":
        # Ubuntu/Debian
        if os.path.exists("/usr/bin/apt-get"):
            run_command("sudo apt-get update", "Updating package list")
            run_command("sudo apt-get install -y tesseract-ocr", "Installing Tesseract OCR")
            run_command("sudo apt-get install -y tesseract-ocr-vie", "Installing Vietnamese language pack")
        # CentOS/RHEL
        elif os.path.exists("/usr/bin/yum"):
            run_command("sudo yum install -y tesseract", "Installing Tesseract OCR")
        else:
            print("⚠️ Unknown Linux distribution. Please install tesseract-ocr manually")
    
    elif system == "darwin":  # macOS
        run_command("brew install tesseract", "Installing Tesseract OCR with Homebrew")
    
    elif system == "windows":
        print("🪟 Windows detected:")
        print("   Please download and install Tesseract from:")
        print("   https://github.com/UB-Mannheim/tesseract/wiki")
        print("   Add tesseract.exe to your PATH environment variable")
    
    else:
        print(f"⚠️ Unknown operating system: {system}")

def test_installation():
    """Test if OCR installation works"""
    print("\n🧪 Testing OCR installation...")
    
    try:
        import pytesseract
        from PIL import Image
        import cv2
        import numpy as np
        
        print("✅ All Python packages imported successfully")
        
        # Test Tesseract availability
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR version: {version}")
        
        # Create a simple test image
        test_image = np.ones((100, 400, 3), dtype=np.uint8) * 255
        cv2.putText(test_image, "24222573 1234 kWh", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # Test OCR
        pil_image = Image.fromarray(cv2.cvtColor(test_image, cv2.COLOR_BGR2RGB))
        text = pytesseract.image_to_string(pil_image)
        print(f"✅ OCR Test Result: {text.strip()}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Python package missing: {e}")
        return False
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
        return False

def main():
    """Main installation process"""
    print("🚀 Installing Python OCR for Electricity Meter Reading")
    print("=" * 60)
    print("This replaces expensive Google Gemini API with free Tesseract OCR")
    print()
    
    # Step 1: Install Python packages
    print("📦 Step 1: Installing Python packages...")
    install_python_packages()
    
    # Step 2: Install Tesseract engine
    print("\n🔧 Step 2: Installing Tesseract OCR engine...")
    install_tesseract_engine()
    
    # Step 3: Test installation
    print("\n🧪 Step 3: Testing installation...")
    if test_installation():
        print("\n🎉 SUCCESS! Python OCR is ready to use!")
        print("\n📋 Next steps:")
        print("1. Start your Flask app: python app.py")
        print("2. Go to /electricity-calculator")  
        print("3. Upload meter images - OCR will work without API costs!")
    else:
        print("\n❌ Installation incomplete. Please check errors above.")
        print("\n🔧 Manual installation:")
        print("pip install pytesseract opencv-python Pillow numpy")
        print("Install Tesseract OCR engine for your OS")

if __name__ == "__main__":
    main()