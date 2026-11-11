


@app.route('/api/apartments', methods=['POST'])
def add_apartment():
    """Add new apartment"""
    try:
        from core.models import Apartment, db
        data = request.get_json()

        new_apartment = Apartment(
            apartment_name=data['apartment_name'],
            apartment_address=data.get('apartment_address', ''),
            apartment_type=data.get('apartment_type', 'Hostel'),
            is_active=True
        )

        db.session.add(new_apartment)
        db.session.commit()

        return jsonify({'success': True, 'apartment_id': new_apartment.apartment_id})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding apartment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/railway_status', methods=['GET'])
def railway_status():
    """Debug endpoint for Railway deployment status"""
    try:
        # Check environment
        env_status = {
            'DATABASE_URL': 'DATABASE_URL' in os.environ,
            'GOOGLE_API_KEY': 'GOOGLE_API_KEY' in os.environ,
            'RAILWAY': 'RAILWAY' in os.environ,
            'PORT': os.environ.get('PORT', 'Not set')
        }
        
        # Check database connection
        from core.models import db
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db_status = 'Connected'
        except Exception as e:
            db_status = f'Error: {str(e)}'
        
        # Check if we can load booking data
        try:
            df = load_booking_data_for_calculations()
            data_status = f'Loaded {len(df)} bookings'
        except Exception as e:
            data_status = f'Error: {str(e)}'
        
        return jsonify({
            'environment': env_status,
            'database': db_status,
            'data_loading': data_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


