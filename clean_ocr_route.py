#!/usr/bin/env python3
"""
Clean OCR route with ONLY OpenRouter API
"""

@app.route('/api/electricity/process_meter', methods=['POST'])
def process_electricity_meter():
    """Process electricity meter image using ONLY OpenRouter API with GPT-4o Mini Vision"""
    try:
        # Get the uploaded image
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        month_type = request.form.get('monthType', 'current')
        image_index = request.form.get('imageIndex', 'unknown')
        file_name = request.form.get('fileName', 'unknown')
        request_id = request.form.get('requestId', 'unknown')
        
        print(f"📥 [OPENROUTER_OCR] {request_id} - Processing image {image_index} ({file_name}) for {month_type}")
        
        # Read image content
        image_content = image_file.read()
        
        # Check OpenRouter availability
        if not OPENROUTER_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'OpenRouter API not available. Install with: pip install openai',
                'error_type': 'openrouter_missing'
            }), 503
        
        # Check API key
        if not os.getenv('OPENROUTER_API_KEY'):
            return jsonify({
                'success': False,
                'error': 'OPENROUTER_API_KEY environment variable required.',
                'error_type': 'api_key_missing'
            }), 503
        
        # Process with OpenRouter API
        try:
            print(f"🤖 [OPENROUTER_AI] {request_id} - Using GPT-4o Mini Vision for {file_name}")
            meter_data = extract_meter_data_with_deepseek(image_content, file_name)
            
            # Log success
            print(f"✅ [OPENROUTER_SUCCESS] {request_id} - Meter {meter_data['meter_id']}: {meter_data['reading']} kWh")
            
            return jsonify({
                'success': True,
                'meterId': meter_data['meter_id'],
                'reading': meter_data['reading'],
                'brand': meter_data['brand'],
                'model': meter_data['model'],
                'extraction_method': meter_data['extraction_method'],
                'debug_available': meter_data.get('debug_available', False),
                'confidence': meter_data.get('confidence', 'high')
            })
            
        except Exception as api_error:
            print(f"❌ [OPENROUTER_ERROR] {request_id} - {api_error}")
            return jsonify({
                'success': False,
                'error': f'OpenRouter API failed: {str(api_error)}. Please use manual entry.',
                'error_type': 'openrouter_api_failed'
            }), 500
            
    except Exception as e:
        print(f"❌ [ROUTE_ERROR] {request_id} - {e}")
        return jsonify({'success': False, 'error': str(e)}), 500