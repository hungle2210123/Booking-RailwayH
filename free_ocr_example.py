#!/usr/bin/env python3
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
