# p04_bookings_expenses — /bookings list + add/edit/cancel/delete, manual entry, expenses API, save extracted
# Part of app.py (lines 3531-5447 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.

@app.route('/health')
def health_check():
    """Enhanced health check endpoint for Railway with database validation"""
    try:
        # Check database connection
        database_url = os.getenv('DATABASE_URL', 'not_set')
        db_type = 'postgresql' if database_url.startswith('postgresql://') else 'sqlite_fallback'
        
        # Test database connection
        db_status = 'unknown'
        db_error = None
        try:
            from core.models import db
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            db_status = 'connected'
        except Exception as e:
            db_status = 'error'
            db_error = str(e)
        
        return jsonify({
            'status': 'healthy',
            'message': 'Hotel Booking System is running',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'type': db_type,
                'status': db_status,
                'error': db_error,
                'url_configured': database_url != 'not_set'
            },
            'railway': {
                'postgresql_ready': db_type == 'postgresql' and db_status == 'connected',
                'needs_setup': db_type == 'sqlite_fallback'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/manual_booking_entry', methods=['POST'])
def manual_booking_entry():
    """Manual booking entry when all AI APIs fail"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['guest_name', 'checkin_date', 'checkout_date', 'room_amount']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Parse and validate dates
        from datetime import datetime
        try:
            checkin_date = datetime.strptime(data['checkin_date'], '%Y-%m-%d').date()
            checkout_date = datetime.strptime(data['checkout_date'], '%Y-%m-%d').date()
            
            if checkout_date <= checkin_date:
                return jsonify({
                    'success': False,
                    'error': 'Check-out date must be after check-in date'
                }), 400
                
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid date format. Use YYYY-MM-DD: {str(e)}'
            }), 400
        
        # Validate room amount
        try:
            room_amount = float(data['room_amount'])
            if room_amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': 'Room amount must be a positive number'
            }), 400
        
        # Create booking object
        from core.models import Booking, db
        
        new_booking = Booking(
            guest_name=data['guest_name'].strip(),
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            room_amount=room_amount,
            accommodation_name=data.get('accommodation_name', '118 Hang Bac Hostel'),
            booking_platform=data.get('booking_platform', 'Manual Entry'),
            guest_count=data.get('guest_count', 1),
            room_type=data.get('room_type', 'Standard'),
            booking_status='confirmed',
            collector=data.get('collector', 'Manual'),
            extraction_method='manual_entry',
            notes=f"Manual entry - All AI APIs were exhausted. Entered by user on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        db.session.add(new_booking)
        db.session.commit()
        
        print(f"✅ [MANUAL_BOOKING] Added: {data['guest_name']} - {checkin_date} to {checkout_date}")
        
        return jsonify({
            'success': True,
            'message': 'Booking added successfully via manual entry',
            'booking_id': new_booking.booking_id,
            'guest_name': new_booking.guest_name,
            'checkin_date': checkin_date.isoformat(),
            'checkout_date': checkout_date.isoformat(),
            'room_amount': room_amount,
            'extraction_method': 'manual_entry'
        })
        
    except Exception as e:
        print(f"❌ [MANUAL_BOOKING] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Manual booking entry failed: {str(e)}'
        }), 500


@app.route('/api/expenses', methods=['GET', 'POST'])
def expenses_api():
    """Expense management with PostgreSQL and Railway compatibility"""
    if request.method == 'GET':
        try:
            print(f"🔍 [EXPENSES_API] Starting expenses loading...")
            
            # 🚀 RAILWAY FIX: Enhanced error handling for database connection issues
            try:
                # First, check if expenses table exists
                from core.models import db
                from sqlalchemy import text
                
                # Test table existence using SQLite/PostgreSQL compatible query
                with db.engine.connect() as conn:
                    try:
                        # Try PostgreSQL first
                        table_check = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expenses')")).scalar()
                        print(f"🔍 [EXPENSES_API] Expenses table exists: {table_check}")
                        
                        if table_check:
                            # Check table structure
                            columns_result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'expenses'"))
                            columns = columns_result.fetchall()
                            print(f"🔍 [EXPENSES_API] Table structure: {columns}")
                    except:
                        # Fallback to SQLite
                        table_check = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")).fetchone()
                        print(f"🔍 [EXPENSES_API] Expenses table exists (SQLite): {table_check is not None}")
                        
                        if table_check:
                            # Check table structure for SQLite
                            columns_result = conn.execute(text("PRAGMA table_info(expenses)"))
                            columns = columns_result.fetchall()
                            print(f"🔍 [EXPENSES_API] Table structure (SQLite): {columns}")
                
                expenses_df = get_expenses_from_database()
                print(f"🔍 [EXPENSES_API] Database query successful, got DataFrame with {len(expenses_df)} rows")
                
                if not expenses_df.empty:
                    print(f"🔍 [EXPENSES_API] DataFrame columns: {list(expenses_df.columns)}")
                    
            except Exception as db_error:
                print(f"❌ [EXPENSES_API] Database error: {db_error}")
                import traceback
                traceback.print_exc()
                # Railway fallback: return empty data instead of crashing
                return jsonify({
                    'success': True, 
                    'data': [], 
                    'status': 'success',
                    'warning': f'Database connection issue: {str(db_error)}',
                    'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
                })
            
            # Convert to records with enhanced error handling
            try:
                expenses_list = safe_to_dict_records(expenses_df)
                print(f"💰 [EXPENSES_API] Successfully converted to {len(expenses_list)} expense records")
                
                # Debug: Print first record structure if exists
                if expenses_list:
                    print(f"🔍 [EXPENSES_API] Sample record structure: {list(expenses_list[0].keys())}")
                    print(f"🔍 [EXPENSES_API] Sample record: {expenses_list[0]}")
                    
            except Exception as convert_error:
                print(f"❌ [EXPENSES_API] Conversion error: {convert_error}")
                # Fallback conversion
                expenses_list = expenses_df.to_dict('records') if not expenses_df.empty else []
                print(f"🔄 [EXPENSES_API] Fallback conversion: {len(expenses_list)} records")
                
                # Debug fallback structure too
                if expenses_list:
                    print(f"🔍 [EXPENSES_API] Fallback sample: {expenses_list[0]}")
            
            # Return format expected by frontend JavaScript
            return jsonify({'success': True, 'data': expenses_list, 'status': 'success'})
        except Exception as e:
            print(f"❌ [EXPENSES_API] CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Railway-safe error response
            return jsonify({
                'success': False, 
                'data': [], 
                'status': 'error',
                'error': f'Expenses loading failed: {str(e)}',
                'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
            }), 500
    
    elif request.method == 'POST':
        try:
            expense_data = {
                'date': datetime.strptime(request.json.get('date'), '%Y-%m-%d').date(),
                'amount': float(request.json.get('amount', 0)),
                'description': request.json.get('description', ''),
                'category': request.json.get('category', 'general'),
                'collector': request.json.get('collector', '')
            }
            
            expense_id = add_expense_to_database(expense_data)
            if expense_id:
                return jsonify({
                    'success': True, 
                    'status': 'success', 
                    'message': 'Expense added successfully',
                    'expense_id': expense_id  # Return expense_id for auto-categorization
                })
            else:
                return jsonify({'success': False, 'status': 'error', 'message': 'Failed to add expense'}), 400
        
        except Exception as e:
            return jsonify({'success': False, 'status': 'error', 'message': str(e)}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE', 'PUT'])
def expense_operations(expense_id):
    """Delete or update specific expense"""
    if request.method == 'DELETE':
        try:
            print(f"🗑️ [DELETE_EXPENSE] Attempting to delete expense ID: {expense_id}")
            
            # Use database service instead of direct model access
            from core.models import db, Expense, ExpenseCategory
            
            # Find the expense in the database
            expense = db.session.query(Expense).filter_by(expense_id=expense_id).first()
            
            if not expense:
                print(f"❌ [DELETE_EXPENSE] Expense {expense_id} not found")
                return jsonify({'success': False, 'status': 'error', 'message': 'Expense not found'}), 404
            
            # CRITICAL FIX: Delete category first to avoid foreign key constraint violations
            print(f"🗑️ [DELETE_EXPENSE] Checking for existing categorization...")
            existing_category = ExpenseCategory.query.filter_by(expense_id=expense_id).first()
            if existing_category:
                print(f"🗑️ [DELETE_EXPENSE] Found category {existing_category.category}, deleting...")
                db.session.delete(existing_category)
            
            # Then delete the expense
            print(f"🗑️ [DELETE_EXPENSE] Deleting expense {expense_id}...")
            db.session.delete(expense)
            db.session.commit()
            
            print(f"✅ [DELETE_EXPENSE] Successfully deleted expense {expense_id} and its categorization")
            return jsonify({'success': True, 'status': 'success', 'message': 'Expense deleted successfully'})
            
        except Exception as e:
            print(f"❌ [DELETE_EXPENSE] Error deleting expense {expense_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to rollback
            try:
                from core.models import db
                db.session.rollback()
            except:
                pass
                
            return jsonify({'success': False, 'status': 'error', 'message': f'Failed to delete expense: {str(e)}'}), 500
    
    elif request.method == 'PUT':
        try:
            print(f"✏️ [UPDATE_EXPENSE] Attempting to update expense ID: {expense_id}")
            
            # Import here to avoid circular imports
            from core.models import db, Expense
            
            # Find the expense
            expense = db.session.query(Expense).filter_by(expense_id=expense_id).first()
            if not expense:
                print(f"❌ [UPDATE_EXPENSE] Expense {expense_id} not found")
                return jsonify({'success': False, 'status': 'error', 'message': 'Expense not found'}), 404
            
            # Get update data
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'status': 'error', 'message': 'No update data provided'}), 400
            
            # Update fields if provided
            if 'date' in data:
                expense.expense_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            if 'amount' in data:
                expense.amount = float(data['amount'])
            if 'description' in data:
                expense.description = data['description']
            if 'category' in data:
                expense.category = data['category']
            if 'collector' in data:
                expense.collector = data['collector']
            
            # Save changes
            db.session.commit()
            
            print(f"✅ [UPDATE_EXPENSE] Successfully updated expense {expense_id}")
            return jsonify({'success': True, 'status': 'success', 'message': 'Expense updated successfully'})
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [UPDATE_EXPENSE] Error updating expense {expense_id}: {e}")
            return jsonify({'success': False, 'status': 'error', 'message': f'Failed to update expense: {str(e)}'}), 500


