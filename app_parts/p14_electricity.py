# p14_electricity — electricity calculator + meters/readings/bills
# Part of app.py (lines 18400-18983 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/electricity-calculator')
def electricity_calculator():
    """Render the electricity bill calculator page"""
    return render_template('electricity_calculator.html')

@app.route('/api/electricity/process_meter', methods=['POST'])
def process_electricity_meter():
    """Multi-API OCR with automatic fallback - Gemini → OpenRouter → Manual"""
    try:
        # Get the uploaded image info
        image_file = request.files.get('image')
        month_type = request.form.get('monthType', 'current')
        image_index = request.form.get('imageIndex', 'unknown')
        file_name = request.form.get('fileName', 'unknown')
        request_id = request.form.get('requestId', 'unknown')
        
        print(f"🚀 [MULTI_API_OCR] {request_id} - Processing {file_name} with Multi-API system")
        
        if not image_file:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        
        # Read and encode image
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Use Multi-API system with automatic fallback
        result = extract_meter_data_with_multi_api(image_base64, request_id)
        
        if result['success']:
            print(f"✅ [OCR_SUCCESS] {request_id} - Meter: {result['data']['meter_id']}, Reading: {result['data']['reading']}")
            return jsonify(result)
        else:
            print(f"🔄 [MANUAL_FALLBACK] {request_id} - All APIs exhausted, falling back to manual entry")
            # Fall back to manual entry
            return jsonify({
                'success': False,
                'error': 'All OCR APIs exhausted - please enter manually',
                'error_type': 'manual_entry_required',
                'manual_entry_required': True,
                'file_name': file_name,
                'instructions': {
                    'step1': 'Look at the LCD display in your uploaded image',
                    'step2': 'Find the main reading number (ignore decimal places)', 
                    'step3': 'Enter the number in the manual input field below'
                },
                'examples': [
                    'LCD shows "01363.5" → Enter: 1363',
                    'LCD shows "00982.2" → Enter: 982',
                    'LCD shows "00936.8" → Enter: 936'
                ],
                'apis_tried': result.get('all_apis_tried', False)
            }), 200
        
    except Exception as e:
        print(f"❌ [OCR_ERROR] {request_id} - {e}")
        return jsonify({
            'success': False,
            'error': 'OCR processing failed - please enter manually',
            'error_type': 'manual_entry_required',
            'manual_entry_required': True
        }), 200

@app.route('/api/electricity/calculate', methods=['POST'])
def calculate_electricity_bill():
    """Calculate electricity bill based on meter readings"""
    try:
        data = request.get_json()
        last_month = data.get('lastMonth', {})
        current_month = data.get('currentMonth', {})
        electricity_price = data.get('electricityPrice', 3600)  # Default to 3600 if not provided
        
        if not last_month or not current_month:
            return jsonify({'success': False, 'error': 'Missing meter data'}), 400
            
        if not electricity_price or electricity_price <= 0:
            return jsonify({'success': False, 'error': 'Invalid electricity price'}), 400
        
        # Calculate bills for each meter
        results = {'meters': [], 'summary': {}}
        
        for meter_id, current_data in current_month.items():
            if meter_id in last_month:
                last_reading = float(last_month[meter_id]['reading'])
                current_reading = float(current_data['reading'])
                
                # Calculate consumption
                consumption = current_reading - last_reading
                
                # Calculate amount using dynamic electricity price
                amount = consumption * electricity_price
                
                results['meters'].append({
                    'meterId': meter_id,
                    'lastReading': last_reading,
                    'currentReading': current_reading,
                    'consumption': consumption,
                    'amount': amount
                })
        
        # Calculate summary
        total_consumption = sum(m['consumption'] for m in results['meters'])
        total_amount = sum(m['amount'] for m in results['meters'])
        
        results['summary'] = {
            'totalMeters': len(results['meters']),
            'totalConsumption': total_consumption,
            'totalAmount': total_amount,
            'averageConsumption': total_consumption / len(results['meters']) if results['meters'] else 0
        }
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Electricity Management Routes ---
from core.electricity_service import ElectricityService
from datetime import date, datetime

@app.route('/electricity-management')
def electricity_management():
    """Render the electricity management page"""
    return render_template('electricity_management.html')

@app.route('/api/electricity/meters', methods=['GET'])
def get_electricity_meters():
    """Get all electricity meters"""
    try:
        meters = ElectricityService.get_all_meters()
        return jsonify({'success': True, 'data': meters})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/meters', methods=['POST'])
def create_electricity_meter():
    """Create a new electricity meter"""
    try:
        data = request.get_json()
        result = ElectricityService.create_meter(
            meter_id=data.get('meter_id'),
            location=data.get('location'),
            brand=data.get('brand'),
            model=data.get('model'),
            notes=data.get('notes')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/meters/<int:meter_uuid>', methods=['PUT'])
def update_electricity_meter(meter_uuid):
    """Update an electricity meter"""
    try:
        data = request.get_json()
        result = ElectricityService.update_meter(meter_uuid, **data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/meters/<int:meter_uuid>', methods=['DELETE'])
def delete_electricity_meter(meter_uuid):
    """Delete (deactivate) an electricity meter"""
    try:
        result = ElectricityService.delete_meter(meter_uuid)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/readings', methods=['GET'])
def get_electricity_readings():
    """Get electricity readings with optional filters"""
    try:
        meter_id = request.args.get('meter_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        
        # Parse dates
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        
        readings = ElectricityService.get_readings(meter_id, start_date, end_date, limit)
        return jsonify({'success': True, 'data': readings})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/readings', methods=['POST'])
def create_electricity_reading():
    """Create a new electricity reading"""
    try:
        data = request.get_json()
        
        # Parse reading date
        reading_date = None
        if data.get('reading_date'):
            reading_date = datetime.strptime(data['reading_date'], '%Y-%m-%d').date()
        
        result = ElectricityService.create_reading(
            meter_id=data.get('meter_id'),
            kwh_reading=float(data.get('kwh_reading')),
            electricity_price=float(data.get('electricity_price')),
            reading_date=reading_date,
            notes=data.get('notes')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/readings/<int:reading_id>', methods=['PUT'])
def update_electricity_reading(reading_id):
    """Update an electricity reading"""
    try:
        data = request.get_json()
        
        # Parse reading date if provided
        if 'reading_date' in data and data['reading_date']:
            data['reading_date'] = datetime.strptime(data['reading_date'], '%Y-%m-%d').date()
        
        result = ElectricityService.update_reading(reading_id, **data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/readings/<int:reading_id>', methods=['DELETE'])
def delete_electricity_reading(reading_id):
    """Delete an electricity reading"""
    try:
        result = ElectricityService.delete_reading(reading_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/save_calculation', methods=['POST'])
def save_electricity_calculation():
    """Save calculation results to database"""
    try:
        data = request.get_json()
        results = data.get('results', {})
        electricity_price = data.get('electricityPrice', 3600)
        
        saved_readings = []
        
        for meter in results.get('meters', []):
            # Create/update meter if it doesn't exist
            meter_result = ElectricityService.get_meter_by_id(meter['meterId'])
            if not meter_result:
                ElectricityService.create_meter(
                    meter_id=meter['meterId'],
                    location=f"Meter {meter['meterId']}",
                    brand="Auto-detected",
                    model="Unknown"
                )
            
            # Save current reading
            reading_result = ElectricityService.create_reading(
                meter_id=meter['meterId'],
                kwh_reading=meter['currentReading'],
                electricity_price=electricity_price,
                notes=f"Calculated reading - Consumption: {meter['consumption']} kWh"
            )
            
            if reading_result['success']:
                saved_readings.append(reading_result['data'])
        
        return jsonify({
            'success': True,
            'data': saved_readings,
            'message': f'Saved {len(saved_readings)} readings to database'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/dashboard_stats', methods=['GET'])
def get_electricity_dashboard_stats():
    """Get electricity dashboard statistics"""
    try:
        result = ElectricityService.get_dashboard_stats()
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/search', methods=['GET'])
def search_electricity_data():
    """Search electricity data"""
    try:
        query = request.args.get('q', '')
        search_type = request.args.get('type', 'all')
        
        result = ElectricityService.search_data(query, search_type)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/bills', methods=['GET'])
def get_electricity_bills():
    """Get electricity bills"""
    try:
        limit = int(request.args.get('limit', 50))
        bills = ElectricityService.get_bills(limit)
        return jsonify({'success': True, 'data': bills})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/bills', methods=['POST'])
def create_electricity_bill():
    """Create a new electricity bill from readings"""
    try:
        data = request.get_json()
        
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        result = ElectricityService.create_bill_from_readings(
            start_date=start_date,
            end_date=end_date,
            notes=data.get('notes')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/debug/<filename>')
def view_ocr_debug(filename):
    """View OCR debug information and processed images"""
    try:
        debug_dir = "static/debug_ocr"
        
        # Find all debug images for this filename
        base_name = filename.replace('.jpg', '').replace('.png', '').replace('.jpeg', '')
        debug_images = []
        
        if os.path.exists(debug_dir):
            for file in os.listdir(debug_dir):
                if base_name in file:
                    debug_images.append({
                        'name': file,
                        'url': f'/static/debug_ocr/{file}',
                        'step': file.replace(base_name + '_', '').replace('.jpg', '')
                    })
        
        # Sort by step number
        debug_images.sort(key=lambda x: x['step'])
        
        return jsonify({
            'success': True,
            'filename': filename,
            'base_name': base_name,
            'debug_images': debug_images,
            'debug_available': len(debug_images) > 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/images/<int:reading_id>', methods=['POST'])
def save_electricity_image(reading_id):
    """Save image for an electricity reading"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        image_content = image_file.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        result = ElectricityService.save_image(
            reading_id=reading_id,
            image_data=image_base64,
            image_filename=image_file.filename,
            description=request.form.get('description', '')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/images/<int:image_id>', methods=['GET'])
def get_electricity_image(image_id):
    """Get electricity image data"""
    try:
        image_data = ElectricityService.get_image_data(image_id)
        if image_data:
            return jsonify({'success': True, 'data': image_data})
        else:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/images/<int:image_id>', methods=['DELETE'])
def delete_electricity_image(image_id):
    """Delete electricity image"""
    try:
        result = ElectricityService.delete_image(image_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/electricity/analytics', methods=['GET'])
def get_electricity_analytics():
    """Get electricity analytics data for charts and comparisons"""
    try:
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        from sqlalchemy import func, extract
        from core.models import ElectricityReading, ElectricityMeter
        
        period = int(request.args.get('period', 12))  # months
        end_date = datetime.now().date()
        start_date = end_date - relativedelta(months=period)
        
        # Get monthly aggregated data
        monthly_data = db.session.query(
            extract('year', ElectricityReading.reading_date).label('year'),
            extract('month', ElectricityReading.reading_date).label('month'),
            func.sum(ElectricityReading.consumption).label('total_consumption'),
            func.sum(ElectricityReading.amount).label('total_amount'),
            func.avg(ElectricityReading.electricity_price).label('avg_price'),
            func.count(func.distinct(ElectricityReading.meter_uuid)).label('meter_count')
        ).filter(
            ElectricityReading.reading_date >= start_date,
            ElectricityReading.reading_date <= end_date,
            ElectricityReading.consumption.isnot(None)
        ).group_by(
            extract('year', ElectricityReading.reading_date),
            extract('month', ElectricityReading.reading_date)
        ).order_by('year', 'month').all()
        
        # Format monthly data
        monthly_formatted = []
        for row in monthly_data:
            month_name = f"{int(row.month):02d}/{int(row.year)}"
            monthly_formatted.append({
                'month': month_name,
                'consumption': float(row.total_consumption or 0),
                'amount': float(row.total_amount or 0),
                'averagePrice': float(row.avg_price or 0),
                'meterCount': int(row.meter_count or 0),
                'notes': None
            })
        
        # Get meter distribution data
        meter_data = db.session.query(
            ElectricityMeter.meter_id,
            ElectricityMeter.location,
            func.sum(ElectricityReading.consumption).label('total_consumption'),
            func.sum(ElectricityReading.amount).label('total_amount')
        ).join(
            ElectricityReading, ElectricityMeter.meter_uuid == ElectricityReading.meter_uuid
        ).filter(
            ElectricityReading.reading_date >= start_date,
            ElectricityReading.reading_date <= end_date,
            ElectricityReading.consumption.isnot(None)
        ).group_by(
            ElectricityMeter.meter_uuid,
            ElectricityMeter.meter_id,
            ElectricityMeter.location
        ).all()
        
        # Calculate percentages for meter distribution
        total_amount = sum(float(row.total_amount or 0) for row in meter_data)
        meter_distribution = []
        for row in meter_data:
            amount = float(row.total_amount or 0)
            percentage = (amount / total_amount * 100) if total_amount > 0 else 0
            meter_distribution.append({
                'meter_id': row.meter_id,
                'location': row.location,
                'consumption': float(row.total_consumption or 0),
                'amount': amount,
                'percentage': round(percentage, 1)
            })
        
        # Get top 5 meters by consumption
        top_meters = sorted(meter_distribution, key=lambda x: x['consumption'], reverse=True)[:5]
        
        # Calculate summary statistics
        amounts = [item['amount'] for item in monthly_formatted if item['amount'] > 0]
        
        if amounts:
            highest_month = max(monthly_formatted, key=lambda x: x['amount'])
            lowest_month = min(monthly_formatted, key=lambda x: x['amount'] if x['amount'] > 0 else float('inf'))
            average_amount = sum(amounts) / len(amounts)
            
            # Calculate trend (compare last 3 months with previous 3 months)
            recent_months = amounts[-3:] if len(amounts) >= 3 else amounts
            previous_months = amounts[-6:-3] if len(amounts) >= 6 else amounts[:-3] if len(amounts) > 3 else []
            
            if previous_months and recent_months:
                recent_avg = sum(recent_months) / len(recent_months)
                previous_avg = sum(previous_months) / len(previous_months)
                trend = ((recent_avg - previous_avg) / previous_avg) * 100 if previous_avg > 0 else 0
            else:
                trend = 0
        else:
            highest_month = {'month': 'N/A', 'amount': 0}
            lowest_month = {'month': 'N/A', 'amount': 0}
            average_amount = 0
            trend = 0
        
        analytics_data = {
            'summary': {
                'highestMonth': {
                    'month': highest_month['month'],
                    'amount': highest_month['amount']
                },
                'lowestMonth': {
                    'month': lowest_month['month'],
                    'amount': lowest_month['amount']
                },
                'averageAmount': average_amount,
                'trend': trend
            },
            'monthly': monthly_formatted,
            'meters': meter_distribution,
            'topMeters': top_meters
        }
        
        return jsonify({'success': True, 'data': analytics_data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


