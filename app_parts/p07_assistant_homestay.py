# p07_assistant_homestay — /ai_assistant page, homestay setup, quick notes, arrival times, hidden guests, no-show
# Part of app.py (lines 8547-9612 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# AI Assistant - Message Templates (Mẫu câu)


def process_product_image_with_ai(image_data):
    """Process product image with Gemini AI to extract metadata"""
    try:
        if not GOOGLE_API_KEY or not genai:
            return None

        import base64
        from PIL import Image
        import io

        # Convert image to base64 for Gemini
        img = Image.open(io.BytesIO(image_data))

        # Resize if too large
        max_size = 1024
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format or 'PNG')
        img_byte_arr = img_byte_arr.getvalue()

        # Configure Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """Analyze this product image and extract the following information in JSON format:
{
    "title": "Product name/title (in Vietnamese if detected, otherwise English)",
    "category": "One of: Furniture, Appliances, Bedding, Kitchen, Bathroom, Decor, Electronics, Other",
    "vendor": "Store/vendor name if visible (Shopee, Lazada, etc.)",
    "price": "Price if visible (with currency)",
    "description": "Brief product description (2-3 sentences in Vietnamese)",
    "tags": "Comma-separated keywords for search (in Vietnamese)"
}

Important:
- If this is a screenshot from e-commerce site (Shopee, Lazada, etc.), extract all visible information
- Generate descriptive title even if not explicitly shown
- Infer category from product appearance
- Tags should include: product type, color, material, size keywords
- Use Vietnamese language for title, description, and tags if possible
- Return ONLY valid JSON, no other text"""

        # Call Gemini AI
        response = model.generate_content([prompt, img])

        if not response or not response.text:
            return None

        # Parse JSON response
        import json
        import re

        # Extract JSON from response
        response_text = response.text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = re.sub(r'```json\n?|\n?```', '', response_text)

        metadata = json.loads(response_text)

        return metadata

    except Exception as e:
        print(f"❌ AI processing error: {str(e)}")
        return None


@app.route('/api/arrival_times', methods=['GET', 'POST'])
def arrival_times():
    """Arrival times management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all arrival times
            arrival_times = db_service.get_arrival_times()
            return jsonify([at.to_dict() for at in arrival_times])
        
        elif request.method == 'POST':
            # Create or update arrival time
            data = request.get_json()
            print(f"🕐 [ARRIVAL_TIME] Received data: {data}")
            
            booking_id = data.get('booking_id')
            estimated_arrival = data.get('estimated_arrival')
            notes = data.get('notes', '')
            
            if not booking_id:
                return jsonify({'success': False, 'error': 'booking_id is required'}), 400
            
            try:
                arrival_time = db_service.upsert_arrival_time(
                    booking_id=booking_id,
                    estimated_arrival=estimated_arrival,
                    notes=notes
                )
                print(f"🕐 [ARRIVAL_TIME] Successfully saved: booking_id={booking_id}, time={estimated_arrival}")
                return jsonify({'success': True, 'data': arrival_time.to_dict()})
            
            except Exception as e:
                print(f"🕐 [ARRIVAL_TIME] Error saving: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/arrival_times/<booking_id>', methods=['DELETE'])
def delete_arrival_time(booking_id):
    """Clear late-arrival record for a booking."""
    try:
        from core.models import db as _atdb, ArrivalTime as _AT
        _AT.query.filter_by(booking_id=booking_id).delete()
        _atdb.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        try:
            from core.models import db as _atdb2
            _atdb2.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


