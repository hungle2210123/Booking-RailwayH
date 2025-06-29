#!/usr/bin/env python3
"""
Enhanced AI extractor specifically for Booking.com admin table
Uses improved prompts for better extraction accuracy
"""

import os
import json
from io import BytesIO

try:
    import google.generativeai as genai
    from PIL import Image
    HAS_GENAI = True
except ImportError:
    print("⚠️ Google AI or PIL not available")
    HAS_GENAI = False

def extract_booking_table_with_enhanced_ai(image_data: bytes, google_api_key: str) -> dict:
    """Enhanced AI extraction specifically for Booking.com admin table"""
    if not HAS_GENAI or not google_api_key:
        return {'error': 'Gemini AI not available'}
    
    try:
        genai.configure(api_key=google_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Convert image for Gemini
        image = Image.open(BytesIO(image_data))
        
        # Enhanced prompt specifically for Booking.com admin table
        prompt = """
        You are analyzing a screenshot from Booking.com extranet admin panel showing a reservations table.
        
        This table typically has columns like:
        - Guest name (guest name)
        - Check-in (arrival date)
        - Departure date (checkout date)  
        - Room (room type)
        - Placed (booking placed date)
        - Status (booking status)
        - Price (room price/amount)
        - Reservation number (booking ID)
        
        Extract ALL visible booking/reservation data from this table.
        
        IMPORTANT INSTRUCTIONS:
        1. Look for tabular data with guest names and dates
        2. Extract EVERY row of booking data you can see
        3. Pay attention to Vietnamese date formats (like "thg 7" for July)
        4. Look for prices in VND, EUR, USD, or other currencies
        5. Booking IDs are usually long numbers (8+ digits)
        6. Guest names can be in various languages (Vietnamese, English, etc.)
        
        Return ONLY a JSON response in this exact format:
        
        {
            "type": "multiple",
            "count": [number_of_bookings_found],
            "bookings": [
                {
                    "guest_name": "exact guest name from table",
                    "booking_id": "reservation number",
                    "checkin_date": "YYYY-MM-DD",
                    "checkout_date": "YYYY-MM-DD", 
                    "room_amount": [numeric_amount_only],
                    "room_type": "room type if visible",
                    "status": "booking status",
                    "currency": "VND/EUR/USD",
                    "placed_date": "when booking was placed",
                    "nights": [number_of_nights]
                }
            ]
        }
        
        CRITICAL EXTRACTION RULES:
        - If you see 10 bookings in the table, return all 10
        - If you see 5 bookings, return all 5  
        - Don't skip any visible bookings
        - Convert dates to YYYY-MM-DD format (e.g. "15 thg 7, 2025" → "2025-07-15")
        - Extract numbers only for room_amount (e.g. "€120.00" → 120)
        - If a field is not visible or unclear, use empty string "" or 0
        
        Return ONLY the JSON, no other text.
        """
        
        print("🤖 Sending enhanced prompt to Gemini AI...")
        response = model.generate_content([prompt, image])
        
        # Parse JSON from response
        try:
            response_text = response.text.strip()
            print(f"🤖 Gemini response (first 300 chars): {response_text[:300]}...")
            
            # Clean response and extract JSON with better handling
            # Remove any markdown code blocks
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end == -1:
                    json_end = len(response_text)
                json_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                if json_end == -1:
                    json_end = len(response_text)
                json_text = response_text[json_start:json_end].strip()
            else:
                # Find JSON object bounds
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                else:
                    return {'error': 'No valid JSON found in AI response', 'raw_response': response_text}
            
            # Clean up common JSON issues
            import re
            # Remove trailing commas before closing brackets/braces
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            # Remove any incomplete lines that might cause issues
            json_text = json_text.strip()
            
            print(f"📝 Extracted JSON (first 200 chars): {json_text[:200]}...")
            
            # Parse JSON
            result = json.loads(json_text)
            
            # Validate and enhance result
            if result.get('type') == 'multiple' and 'bookings' in result:
                bookings = result['bookings']
                print(f"✅ AI found {len(bookings)} bookings in the table")
                
                # Enhance booking data
                for i, booking in enumerate(bookings):
                    # Add sequence number
                    booking['sequence'] = i + 1
                    
                    # Validate required fields
                    if not booking.get('guest_name'):
                        print(f"⚠️ Booking {i+1}: Missing guest name")
                    
                    # Convert room_amount to number if it's a string
                    if isinstance(booking.get('room_amount'), str):
                        try:
                            # Extract numbers from string like "€120.00" → 120
                            import re
                            amount_str = booking['room_amount']
                            numbers = re.findall(r'\d+\.?\d*', amount_str)
                            if numbers:
                                booking['room_amount'] = float(numbers[0])
                        except:
                            booking['room_amount'] = 0
                
                result['extraction_method'] = 'enhanced_ai'
                result['extraction_timestamp'] = json.dumps(None)  # Will be set by caller
                
                return result
            else:
                print("⚠️ AI response doesn't match expected format")
                return {'error': 'AI response format unexpected', 'raw_response': response_text}
                
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON decode error: {json_error}")
            return {
                'error': f'Invalid JSON from AI: {str(json_error)}',
                'raw_response': response.text[:1000]
            }
        
    except Exception as e:
        print(f"❌ Enhanced AI extraction error: {e}")
        return {'error': str(e)}

def test_enhanced_extractor():
    """Test function for the enhanced extractor"""
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        return
    
    print("🧪 Enhanced AI Extractor Test")
    print("=" * 40)
    print("This function is ready to process Booking.com admin screenshots")
    print("Use it with the AI-enhanced crawler for best results")

if __name__ == "__main__":
    test_enhanced_extractor()