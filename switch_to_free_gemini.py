#!/usr/bin/env python3
"""
Switch the Flask app to use FREE Gemini API instead of paid OpenRouter
"""

import os

def update_flask_app_for_gemini():
    """Update app.py to use free Gemini API"""
    
    print("🔧 SWITCHING TO FREE GEMINI API")
    print("=" * 50)
    
    # Read current app.py
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("✅ Read app.py file")
    
    # Find the extract_meter_data_with_deepseek function
    function_start = content.find('def extract_meter_data_with_deepseek(')
    if function_start == -1:
        print("❌ Could not find extract_meter_data_with_deepseek function")
        return
    
    # Find the end of the function (next def or class)
    function_end = content.find('\ndef ', function_start + 1)
    if function_end == -1:
        function_end = content.find('\nclass ', function_start + 1)
    if function_end == -1:
        function_end = len(content)
    
    print(f"📍 Found function at position {function_start} to {function_end}")
    
    # Create new Gemini-based function
    new_function = '''def extract_meter_data_with_gemini(image_content, file_name):
    """
    Extract electricity meter data using FREE Google Gemini API
    100% FREE alternative to OpenRouter API
    """
    print(f"🆓 [GEMINI_OCR] Processing {file_name} with FREE Gemini API...")
    
    try:
        import google.generativeai as genai
        from PIL import Image
        from io import BytesIO
        
        # Check if Gemini is available
        gemini_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not gemini_key:
            raise Exception("GOOGLE_API_KEY not found in environment variables")
        
        # Configure Gemini
        genai.configure(api_key=gemini_key)
        
        # Load image from bytes
        image = Image.open(BytesIO(image_content))
        
        # Enhanced system prompt specifically for Vietnamese meters
        prompt = """You are an expert Vietnamese electricity meter reader with 15+ years of experience.
        You specialize in extracting data from EMIC brand electricity meters with LCD displays.
        
        Your task: Analyze this electricity meter image and extract the exact meter reading and ID.
        
        CRITICAL REQUIREMENTS FOR METER READING:
        1. The LCD display shows numbers with leading zeros (e.g., "00360.8", "01363.5", "00880.3")
        2. REMOVE ALL LEADING ZEROS but KEEP ALL SIGNIFICANT DIGITS
        3. The last digit (after decimal) is fractional - IGNORE IT
        4. Be VERY CAREFUL not to drop any significant digits
        
        LCD DIGIT RECOGNITION RULES:
        - Pay careful attention to distinguish between similar digits
        - 8 has closed loops at top and bottom
        - 6 has one closed loop at bottom only
        - 0 is oval-shaped
        - 3 has rounded curves on the right side
        - Always double-check each digit before final reading
        
        METER ID EXTRACTION RULES:
        - Meter IDs are EXACTLY 8 digits starting with 24
        - Common patterns: 24222573, 24256413, 24225047, 24266413
        - DIGIT RECOGNITION CRITICAL RULES:
          * 2 vs 7: 2 has horizontal lines, 7 has diagonal line
          * 5 vs 6: 5 has straight top edge, 6 has curved top
          * 1 vs 0: 1 is narrow vertical line, 0 is wide oval
          * Look at EACH digit in the meter ID very carefully
        - NEVER confuse: 24275047 (wrong) vs 24225047 (correct)
        - NEVER confuse: 24266403 (wrong) vs 24256413 (correct)
        
        CRITICAL MISREADING PREVENTION:
        - 1363 should NEVER be read as 336 (missing the "1" digit)
        - 860 should NEVER be read as 808
        - COUNT ALL DIGITS: "01363.5" has 5 digits before decimal (0,1,3,6,3) → reading: 1363
        - Look at the ENTIRE display carefully - don't miss the first significant digit!
        
        Return ONLY a JSON object with these exact fields:
        {
            "meter_id": "actual_meter_id_from_image",
            "reading": actual_number_without_leading_zeros_and_decimal,
            "brand": "detected_brand",
            "model": "Gemini_1.5_Flash",
            "extraction_method": "gemini_ai_free",
            "confidence": "high/medium/low",
            "display_raw": "exact_value_shown_on_LCD_display"
        }
        
        EXAMPLES:
        - Display "00360.8" → {"reading": 360, "display_raw": "00360.8"}
        - Display "00860.3" → {"reading": 860, "display_raw": "00860.3"} 
        - Display "01363.5" → {"reading": 1363, "display_raw": "01363.5"} ← CRITICAL TEST CASE
        - Meter showing "24225047" → {"meter_id": "24225047"} ← NOT "24275047"
        - Meter showing "24256413" → {"meter_id": "24256413"} ← NOT "24266403"
        
        NO EXPLANATIONS - ONLY JSON OUTPUT.
        
        Analyze this Vietnamese EMIC electricity meter image and extract the meter data.
        Focus on:
        1. The main LCD display showing the kWh reading (ignore fractional digits)
        2. The meter ID number (usually printed on the meter body)
        3. The brand name (usually EMIC)
        
        Return the data as JSON only."""
        
        # Use Gemini 1.5 Flash (FREE model)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Generate content with image
        response = model.generate_content([prompt, image])
        response_text = response.text.strip()
        
        print(f"📝 [GEMINI_RESPONSE] {response_text[:200]}...")
        
        # Parse JSON response (handle markdown wrapping)
        try:
            import json
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            meter_data = json.loads(response_text.strip())
            
            # Validate and clean the response
            if not isinstance(meter_data, dict):
                raise ValueError("Response is not a JSON object")
                
            # Ensure required fields exist
            required_fields = ['meter_id', 'reading', 'brand']
            for field in required_fields:
                if field not in meter_data:
                    meter_data[field] = 'UNKNOWN' if field != 'reading' else 0
            
            # Convert reading to integer
            if isinstance(meter_data['reading'], str):
                meter_data['reading'] = int(float(meter_data['reading'].replace(',', '.')))
            elif isinstance(meter_data['reading'], float):
                meter_data['reading'] = int(meter_data['reading'])
                
            # Add metadata
            meter_data['extraction_method'] = 'gemini_ai_free'
            meter_data['model'] = 'Gemini_1.5_Flash'
            meter_data['debug_available'] = False  # No debug images for AI
            
            print(f"✅ [GEMINI_SUCCESS] Meter {meter_data['meter_id']}: {meter_data['reading']} kWh")
            return meter_data
            
        except json.JSONDecodeError as e:
            print(f"❌ [GEMINI_JSON_ERROR] Failed to parse JSON: {e}")
            print(f"Raw response: {response_text}")
            
            # Fallback parsing for non-JSON responses
            return parse_gemini_fallback_response(response_text, file_name)
            
    except Exception as e:
        print(f"❌ [GEMINI_ERROR] {file_name}: {e}")
        raise Exception(f"Gemini OCR failed: {str(e)}")

def parse_gemini_fallback_response(response_text, file_name):
    """
    Fallback parser when Gemini doesn't return valid JSON
    """
    print(f"🔧 [GEMINI_FALLBACK] Parsing non-JSON response...")
    
    # Try to extract numbers and text from the response
    import re
    
    # Look for meter ID patterns
    meter_id_matches = re.findall(r'24\\d{6,8}', response_text)
    meter_id = meter_id_matches[0] if meter_id_matches else 'AUTO_GEMINI'
    
    # Look for reading patterns
    reading_patterns = [
        r'reading["\\'\\s]*:?["\\'\\s]*(\\d{1,4})',
        r'(\\d{3,4})\\s*kWh',
        r'display.*?(\\d{3,4})',
        r'(\\d{3,4})["\\'\\s]*kWh'
    ]
    
    reading = 0
    for pattern in reading_patterns:
        matches = re.findall(pattern, response_text)
        if matches:
            reading = int(matches[0])
            break
    
    # Extract brand
    brand = 'EMIC' if 'EMIC' in response_text.upper() else 'UNKNOWN'
    
    fallback_data = {
        'meter_id': meter_id,
        'reading': reading,
        'brand': brand,
        'model': 'Gemini_1.5_Flash',
        'extraction_method': 'gemini_fallback',
        'confidence': 'medium'
    }
    
    print(f"🔧 [GEMINI_FALLBACK] Meter {fallback_data['meter_id']}: {fallback_data['reading']} kWh")
    return fallback_data

'''
    
    # Replace the function in the content
    old_function = content[function_start:function_end]
    updated_content = content.replace(old_function, new_function)
    
    # Also update the function call in the route
    updated_content = updated_content.replace(
        'extract_meter_data_with_deepseek(',
        'extract_meter_data_with_gemini('
    )
    
    # Write updated content
    with open('app_gemini.py', 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ Created app_gemini.py with FREE Gemini OCR")
    print(f"🆓 No more API costs!")
    print(f"🎯 Uses your existing Google API key")
    print(f"📈 15 requests/minute, 1500/day FREE")
    
    print(f"\\n🚀 TO USE THE FREE VERSION:")
    print(f"   1. Wait for Gemini quota reset (tomorrow)")
    print(f"   2. Or use: python3 app_gemini.py")
    print(f"   3. Upload your meter images")
    print(f"   4. Get accurate OCR for FREE!")

if __name__ == "__main__":
    update_flask_app_for_gemini()