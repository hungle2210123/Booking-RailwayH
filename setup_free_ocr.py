#!/usr/bin/env python3
"""
Set up truly free OCR alternatives
"""

print("🆓 FREE OCR ALTERNATIVES FOR ELECTRICITY METERS")
print("=" * 60)

print("🔥 OPTION 1: Hugging Face Transformers (100% Free)")
print("   Models: Florence-2, BLIP-2, LLaVA")
print("   Install: pip install transformers torch pillow")
print("   Runs locally on your computer")
print("   No API keys needed")
print()

print("🔥 OPTION 2: Ollama + LLaVA (100% Free)")  
print("   Install Ollama: https://ollama.ai/")
print("   Run: ollama pull llava")
print("   Vision model runs locally")
print("   No internet needed after download")
print()

print("🔥 OPTION 3: Google Gemini (Free Tier)")
print("   15 requests/minute free")
print("   Need Google AI Studio API key (free)")
print("   Visit: https://aistudio.google.com/")
print()

print("🔥 OPTION 4: Enhanced Python OCR (Free)")
print("   Install Tesseract: sudo apt install tesseract-ocr")
print("   Enhance with preprocessing")
print("   Less accurate but completely free")
print()

print("💡 QUICK SETUP COMMANDS:")
print()
print("# For Hugging Face:")
print("pip install transformers torch pillow accelerate")
print()
print("# For Google Gemini:")
print("# Get free API key from https://aistudio.google.com/")
print()
print("# For Tesseract:")
print("sudo apt install tesseract-ocr tesseract-ocr-vie")

def create_free_ocr_example():
    """Create example using free Hugging Face model"""
    
    code = '''#!/usr/bin/env python3
"""
Free OCR using Hugging Face Florence-2 model
"""

from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image
import torch

def setup_free_ocr():
    """Setup free Florence-2 model for OCR"""
    
    model_name = "microsoft/Florence-2-large"
    
    # Load model and processor
    model = AutoModelForCausalLM.from_pretrained(
        model_name, 
        torch_dtype=torch.float16,
        trust_remote_code=True
    )
    processor = AutoProcessor.from_pretrained(
        model_name, 
        trust_remote_code=True
    )
    
    return model, processor

def extract_meter_data_free(image_path):
    """Extract meter data using free Florence-2"""
    
    model, processor = setup_free_ocr()
    
    # Load image
    image = Image.open(image_path)
    
    # Create prompt for OCR
    prompt = "<OCR>Extract all text from this electricity meter"
    
    # Process
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=100)
    
    # Decode result
    result = processor.decode(outputs[0], skip_special_tokens=True)
    
    return result

# Usage:
# result = extract_meter_data_free("meter_image.jpg")
# print(f"OCR Result: {result}")
'''
    
    with open('free_ocr_example.py', 'w') as f:
        f.write(code)
    
    print(f"\n✅ Created: free_ocr_example.py")
    print(f"📝 Example code for 100% free OCR using Hugging Face")

if __name__ == "__main__":
    create_free_ocr_example()