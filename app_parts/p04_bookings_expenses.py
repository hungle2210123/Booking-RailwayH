# p04_bookings_expenses — /bookings list + add/edit/cancel/delete, manual entry, expenses API, save extracted
# Part of app.py (lines 3531-5447 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/bookings')
def view_bookings():
    """Professional booking management with optimized search and filtering"""
    import time
    start_time = time.time()
    
    try:
        # Check if we need to force fresh data (e.g., after payment collection)
        force_fresh = request.args.get('refresh', 'false').lower() == 'true'
        df, _ = load_data(force_fresh=force_fresh)

        if df.empty:
            return render_template('bookings.html',
                                 bookings=[],
                                 total_bookings=0,
                                 pagination={'total': 0, 'page': 1, 'total_pages': 0})

        # Get URL parameters with professional pagination
        search_term = request.args.get('search_term', '').strip().lower()
        sort_by = request.args.get('sort_by', 'Check-in Date')
        auto_filter = request.args.get('auto_filter', 'true').lower() == 'true'
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        # Default sort: always by check-in date, ascending for both views
        default_order = 'asc'  # Always ascending for check-in date sorting
        order = request.args.get('order', default_order)
        
        # PROFESSIONAL PAGINATION PARAMETERS
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))  # Professional default
        except (ValueError, TypeError):
            page = 1
            per_page = 50
            print("⚠️ PAGINATION: Invalid parameters, using defaults")
        
        # Professional parameter validation
        if page < 1:
            page = 1
        if per_page not in [25, 50, 100, 200]:
            per_page = 50

        # Filter data
        filtered_df = df.copy()

        # PROFESSIONAL SEARCH IMPLEMENTATION
        if search_term:
            # Multi-field search with weighted relevance
            search_lower = search_term.lower()

            # Create search masks for different fields
            name_mask = filtered_df['Tên người đặt'].str.lower().str.contains(search_lower, na=False)
            booking_id_mask = filtered_df['Số đặt phòng'].astype(str).str.lower().str.contains(search_lower, na=False)

            # Additional search fields for comprehensive search
            phone_mask = filtered_df.get('phone', pd.Series([False] * len(filtered_df))).astype(str).str.lower().str.contains(search_lower, na=False)
            notes_mask = filtered_df.get('Ghi chú thanh toán', pd.Series([False] * len(filtered_df))).astype(str).str.lower().str.contains(search_lower, na=False)

            # Combine all search criteria
            combined_mask = name_mask | booking_id_mask | phone_mask | notes_mask

            # Apply search filter
            filtered_df = filtered_df.loc[combined_mask].copy()

        # DATE FILTERING (MONTH/YEAR/DATE RANGE)
        filter_month = request.args.get('filter_month', '').strip()
        filter_year = request.args.get('filter_year', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        
        # Apply month/year filtering
        if filter_month or filter_year or start_date or end_date:
            # Convert check-in date to datetime for filtering
            if 'Check-in Date' in filtered_df.columns:
                filtered_df['Check-in Date'] = pd.to_datetime(filtered_df['Check-in Date'], errors='coerce')

                # Filter by month
                if filter_month:
                    try:
                        month_num = int(filter_month)
                        filtered_df = filtered_df.loc[filtered_df['Check-in Date'].dt.month == month_num].copy()
                    except (ValueError, TypeError):
                        pass

                # Filter by year
                if filter_year:
                    try:
                        year_num = int(filter_year)
                        filtered_df = filtered_df.loc[filtered_df['Check-in Date'].dt.year == year_num].copy()
                    except (ValueError, TypeError):
                        pass

                # Filter by date range
                if start_date:
                    try:
                        start_dt = pd.to_datetime(start_date)
                        filtered_df = filtered_df.loc[filtered_df['Check-in Date'] >= start_dt].copy()
                    except (ValueError, TypeError):
                        pass

                if end_date:
                    try:
                        end_dt = pd.to_datetime(end_date)
                        filtered_df = filtered_df.loc[filtered_df['Check-in Date'] <= end_dt].copy()
                    except (ValueError, TypeError):
                        pass
        
        # Duplicate detection and marking (NO AUTO-HIDING)
        duplicate_report = {'total_groups': 0, 'total_duplicates': 0, 'filtered_count': 0}
        duplicate_booking_ids = set()
        
        # Always analyze duplicates but don't auto-filter unless specifically requested
        duplicates = analyze_existing_duplicates(filtered_df)
        
        # Mark duplicate bookings for visual indication (don't hide them)
        try:
            duplicate_groups = duplicates.get('duplicate_groups', [])
            for group in duplicate_groups:
                if isinstance(group, dict) and 'bookings' in group:
                    for booking in group['bookings'][1:]:  # Mark duplicates (keep first)
                        if isinstance(booking, dict) and 'Số đặt phòng' in booking:
                            duplicate_booking_ids.add(booking['Số đặt phòng'])
        except Exception as e:
            print(f"⚠️ [DUPLICATE_PROCESS] Error processing duplicate groups: {e}")
            duplicate_groups = []
        
        # Clean duplicate groups to prevent JSON serialization errors
        def clean_duplicate_groups(groups):
            """Clean duplicate groups data to prevent JSON serialization errors"""
            if not groups:
                return []
            
            cleaned_groups = []
            for group in groups:
                try:
                    cleaned_group = {}
                    for key, value in group.items():
                        if value is None or str(value) == 'nan' or str(value) == 'NaT':
                            cleaned_group[key] = ''
                        elif hasattr(value, 'to_dict'):  # Handle pandas objects
                            cleaned_group[key] = value.to_dict()
                        elif isinstance(value, list):
                            # Clean each item in the list
                            cleaned_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    cleaned_item = {k: (v if v is not None and str(v) not in ['nan', 'NaT'] else '') for k, v in item.items()}
                                    cleaned_list.append(cleaned_item)
                                else:
                                    cleaned_list.append(item if item is not None else '')
                            cleaned_group[key] = cleaned_list
                        else:
                            cleaned_group[key] = value
                    cleaned_groups.append(cleaned_group)
                except Exception as e:
                    print(f"⚠️ [DUPLICATE_CLEAN] Error cleaning group: {e}")
                    continue
            return cleaned_groups

        # Create duplicate report for template
        duplicate_report = {
            'total_groups': duplicates.get('total_groups', 0),
            'total_duplicates': duplicates.get('total_duplicates', 0),
            'filtered_count': len(duplicate_booking_ids),
            'duplicate_booking_ids': list(duplicate_booking_ids),  # For marking in template
            'duplicate_groups': clean_duplicate_groups(duplicates.get('duplicate_groups', []))  # Cleaned for JSON
        }
        
        # DEBUG: Log duplicate detection results
        print(f"🔍 [DUPLICATE_DEBUG] Duplicate analysis results:")
        print(f"   - total_groups: {duplicate_report['total_groups']}")
        print(f"   - total_duplicates: {duplicate_report['total_duplicates']}")
        print(f"   - filtered_count: {duplicate_report['filtered_count']}")
        print(f"   - duplicate_booking_ids count: {len(duplicate_report['duplicate_booking_ids'])}")
        print(f"   - duplicate_booking_ids: {duplicate_report['duplicate_booking_ids'][:5]}...")  # Show first 5
        print(f"   - duplicates raw result keys: {list(duplicates.keys())}")
        print(f"   - duplicates raw result: {duplicates}")
        
        # Only hide duplicates if auto_filter is specifically enabled AND user wants to hide duplicates
        if auto_filter and request.args.get('hide_duplicates') == 'true':
            print(f"🔍 [BOOKINGS] Hiding {len(duplicate_booking_ids)} duplicate bookings (user requested)")
            filtered_df = filtered_df.loc[~filtered_df['Số đặt phòng'].isin(duplicate_booking_ids)].copy()
        else:
            print(f"🔍 [BOOKINGS] Keeping {len(duplicate_booking_ids)} duplicate bookings visible for manual review")
        
        # "Only interested guests" filter - DEFAULT: Show actionable guests
        if not show_all:
            today = datetime.today().date()
            print(f"🎯 INTERESTED GUESTS FILTER (EXPANDED): Applying filter for date {today}")
            
            # Convert date columns for comparison
            filtered_df['Check-in Date'] = pd.to_datetime(filtered_df['Check-in Date'], errors='coerce')
            filtered_df['Check-out Date'] = pd.to_datetime(filtered_df['Check-out Date'], errors='coerce')
            
            # Reset index to ensure clean boolean indexing
            filtered_df = filtered_df.reset_index(drop=True)
            
            # Create mask for "interested" guests who need attention
            # EXPANDED FILTER: Show guests who need payment collection or management
            payment_issue_mask = (
                (filtered_df['Số tiền đã thu'].fillna(0) == 0) |  # No money collected
                (filtered_df['Số tiền đã thu'].fillna(0) < filtered_df['Tổng thanh toán']) |  # Partial payment
                (~filtered_df['Người thu tiền'].isin(['LOC LE', 'THAO LE']))  # Invalid collector
            )
            
            interested_mask = (
                # Condition 1: All upcoming guests (future check-ins) - but exclude cancelled ones
                (
                    (filtered_df['Check-in Date'].dt.date >= today) &
                    (filtered_df['Tình trạng'] != 'Đã hủy')
                ) |
                
                # Condition 2: Current/past guests with payment issues who haven't checked out yet
                # (checked out after today OR haven't checked out yet) - but exclude cancelled ones
                (
                    payment_issue_mask &
                    (filtered_df['Check-out Date'].dt.date >= today) &
                    (filtered_df['Tình trạng'] != 'Đã hủy')
                )
                
                # Condition 3: Cancelled bookings are excluded from "interested guests"
                # They will only appear in "All guests" view (when show_all=True)
            )
            
            # Apply the filter using loc for clean indexing
            before_count = len(filtered_df)
            filtered_df = filtered_df.loc[interested_mask].copy()
            after_count = len(filtered_df)
            
            # Debug information for expanded filter
            upcoming_guests = len(filtered_df.loc[filtered_df['Check-in Date'].dt.date >= today])
            current_unpaid_guests = len(filtered_df.loc[
                (payment_issue_mask) & 
                (filtered_df['Check-out Date'].dt.date >= today)
            ])
            cancelled_guests_still_relevant = len(filtered_df.loc[
                (filtered_df['Tình trạng'] == 'Đã hủy') &
                (filtered_df['Check-out Date'].dt.date >= today)
            ])
            
            print(f"🔍 EXPANDED INTERESTED GUESTS FILTER RESULTS:")
            print(f"   📊 Total guests filtered: {before_count} → {after_count}")
            print(f"   🏨 All upcoming guests: {upcoming_guests}")
            print(f"   💰 Current/staying unpaid guests: {current_unpaid_guests}")
            print(f"   ❌ Cancelled bookings (checkout date not passed): {cancelled_guests_still_relevant}")
            print(f"   📅 Focus: All future arrivals + current unpaid guests + active cancelled bookings")
            print(f"   🎯 Logic: Future check-ins OR (unpaid AND not checked out yet) OR (cancelled AND checkout date not passed)")
            
        else:
            print(f"📋 SHOWING ALL GUESTS: {len(filtered_df)} total guests")
        
        # Sort data
        if sort_by in filtered_df.columns:
            ascending = (order == 'asc')
            if sort_by in ['Check-in Date', 'Check-out Date']:
                filtered_df = filtered_df.sort_values(sort_by, ascending=ascending, na_position='last')
            else:
                filtered_df = filtered_df.sort_values(sort_by, ascending=ascending)
        
        # PROFESSIONAL PAGINATION IMPLEMENTATION
        total_bookings = len(filtered_df)
        total_pages = (total_bookings + per_page - 1) // per_page  # Ceiling division
        
        # Calculate pagination boundaries
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Apply pagination to filtered data
        paginated_df = filtered_df.iloc[start_idx:end_idx]
        bookings_list = safe_to_dict_records(paginated_df)
        
        # Professional pagination info with page range calculation
        # Calculate page range for template (avoid Jinja2 max/min issues)
        start_page = max(1, page - 2)
        end_page = min(total_pages + 1, page + 3)
        page_range = list(range(start_page, end_page))
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_bookings,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
            'start_item': start_idx + 1 if total_bookings > 0 else 0,
            'end_item': min(end_idx, total_bookings),
            'showing_count': len(bookings_list),
            'page_range': page_range  # Pre-calculated page range
        }
        
        print(f"📄 PAGINATION RESULT: Showing {pagination_info['start_item']}-{pagination_info['end_item']} of {total_bookings} items")
        
        # Professional performance monitoring
        total_time = time.time() - start_time
        print(f"⏱️ TOTAL PERFORMANCE: Booking management completed in {total_time:.3f}s")
        
        return render_template(
            'bookings.html',
                bookings=bookings_list,
                search_term=search_term,
                sort_by=sort_by,
                order=order,
                auto_filter=auto_filter,
                auto_filter_duplicates=auto_filter,  # For template compatibility
                duplicate_report=duplicate_report,
                show_all=show_all,
                total_bookings=total_bookings,
                booking_count=total_bookings,
                current_sort_by=sort_by,
                current_order=order,
                pagination=pagination_info,
                # Date filter parameters
                filter_month=filter_month,
                filter_year=filter_year,
                start_date=start_date,
                end_date=end_date
            )
        
    except Exception as e:
        print(f"❌ BOOKING MANAGEMENT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return safe fallback response
        flash(f'Lỗi tải dữ liệu đặt phòng: {str(e)}', 'error')
        return render_template('bookings.html', 
                             bookings=[], 
                             total_bookings=0,
                             search_term='',
                             filter_month='',
                             filter_year='',
                             start_date='',
                             end_date='',
                             sort_by='Check-in Date',
                             order='desc',
                             auto_filter=False,
                             show_all=False,
                             pagination={
                                 'total': 0, 
                                 'page': 1, 
                                 'total_pages': 0,
                                 'has_prev': False,
                                 'has_next': False,
                                 'page_range': [1],
                                 'start_item': 0,
                                 'end_item': 0,
                                 'showing_count': 0
                             },
                             error_message=str(e))

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

@app.route('/api/database/health')
def database_health():
    """Check PostgreSQL database health"""
    try:
        db_service = get_database_service()
        health_status = db_service.get_health_status()
        return jsonify(health_status)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'backend': 'postgresql',
            'error': str(e)
        }), 500

@app.route('/api/database/test_connection')
def test_database_connection():
    """Test PostgreSQL connection for pgAdmin/DBeaver compatibility"""
    try:
        db_service = get_database_service()
        connection_test = db_service.test_connection()
        
        # Additional connection info for pgAdmin/DBeaver
        connection_info = {
            'database_url': os.getenv('DATABASE_URL', '').split('@')[-1] if os.getenv('DATABASE_URL') else 'Not configured',
            'connection_details': {
                'backend': 'postgresql',
                'sqlalchemy_version': '2.0+',
                'supports_pgadmin': True,
                'supports_dbeaver': True
            }
        }
        
        return jsonify({
            **connection_test,
            **connection_info
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Database connection failed'
        }), 500

@app.route('/duplicate_management')
def duplicate_management_page():
    """Duplicate management interface"""
    return render_template('duplicate_management.html')

@app.route('/bookings/add', methods=['GET', 'POST'])
def add_booking():
    """Add new booking to PostgreSQL"""
    if request.method == 'POST':
        try:
            # Get form data with validation
            checkin_date_str = request.form.get('Ngày đến')
            checkout_date_str = request.form.get('Ngày đi')
            
            # Validate required fields
            if not checkin_date_str:
                flash('Check-in date is required', 'error')
                return render_template('add_booking.html')
            
            if not checkout_date_str:
                flash('Check-out date is required', 'error')
                return render_template('add_booking.html')
            
            booking_data = {
                'booking_id': request.form.get('Số đặt phòng'),
                'guest_name': request.form.get('Tên người đặt'),
                'email': request.form.get('Email'),
                'phone': request.form.get('Số điện thoại'),
                'checkin_date': datetime.strptime(checkin_date_str, '%Y-%m-%d').date(),
                'checkout_date': datetime.strptime(checkout_date_str, '%Y-%m-%d').date(),
                'room_amount': float(request.form.get('Tổng thanh toán', 0)),
                'commission': float(request.form.get('Hoa hồng', 0)),
                'taxi_amount': float(request.form.get('Taxi', 0)),
                'collector': request.form.get('Người thu tiền', ''),
                'notes': request.form.get('Ghi chú', '')
            }
            
            # Pre-flight check for Railway deployment
            try:
                from core.models import db
                from sqlalchemy import text
                db.session.execute(text('SELECT 1'))
                print("✅ [PRE_FLIGHT] Database connection verified")
            except Exception as db_test_error:
                print(f"❌ [PRE_FLIGHT] Database connection failed: {db_test_error}")
                flash(f'Database connection error: {str(db_test_error)}', 'error')
                return render_template('add_booking.html')
            
            if add_new_booking(booking_data):
                # Cache removed - data will be fresh automatically
                flash('Booking added successfully!', 'success')
                return redirect(url_for('view_bookings'))
            else:
                flash('Error adding booking to database', 'error')
        
        except Exception as e:
            import traceback
            error_msg = f'Error adding booking: {str(e)}'
            print(f"❌ [ADD_BOOKING_ERROR] {error_msg}")
            print(f"❌ [ADD_BOOKING_TRACEBACK] {traceback.format_exc()}")
            
            # Check for common Railway issues
            if "database" in str(e).lower() or "connection" in str(e).lower():
                print(f"🔍 [RAILWAY_DEBUG] Possible database connection issue")
                print(f"🔍 [RAILWAY_DEBUG] DATABASE_URL exists: {'DATABASE_URL' in os.environ}")
            
            flash(error_msg, 'error')
    
    return render_template('add_booking.html')

@app.route('/bookings/add_from_image', methods=['GET'])
def add_booking_from_image():
    """Manual text processing page for booking extraction"""
    return render_template('add_from_image.html')

@app.route('/booking/<booking_id>/edit', methods=['GET', 'POST'])
def edit_booking(booking_id):
    """Edit booking in PostgreSQL"""
    df, _ = load_data()
    
    # Find booking
    booking_data = df[df['Số đặt phòng'] == booking_id]
    if booking_data.empty:
        flash('Booking not found', 'error')
        return redirect(url_for('view_bookings'))
    
    booking = booking_data.iloc[0].to_dict()
    
    if request.method == 'POST':
        try:
            # Get form data with validation
            checkin_date_str = request.form.get('checkin_date')
            checkout_date_str = request.form.get('checkout_date')
            
            # Validate required date fields
            if not checkin_date_str:
                flash('Check-in date is required', 'error')
                return render_template('edit_booking.html', booking=booking)
            
            if not checkout_date_str:
                flash('Check-out date is required', 'error')
                return render_template('edit_booking.html', booking=booking)
            
            # Helper function to safely convert to float, treating empty strings as 0
            def safe_float(value, default=0):
                if value is None or value == '' or value == 'None':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Get room type selection
            room_type = request.form.get('Tên chỗ nghỉ', '118 Hang Bac Hostel')
            print(f"🏠 [EDIT_BOOKING] Room type updated to: {room_type}")
            
            update_data = {
                'guest_name': request.form.get('guest_name'),
                'checkin_date': datetime.strptime(checkin_date_str, '%Y-%m-%d').date(),
                'checkout_date': datetime.strptime(checkout_date_str, '%Y-%m-%d').date(),
                'room_amount': safe_float(request.form.get('room_amount'), 0),
                'commission': safe_float(request.form.get('commission'), 0),
                'taxi_amount': safe_float(request.form.get('taxi_amount'), 0),
                'collector': request.form.get('collector', ''),
                'notes': request.form.get('notes', ''),
                'status': request.form.get('Tình trạng', ''),  # Add status field extraction
                'accommodation_name': room_type  # Save room type to database
            }
            
            record_booking_history(booking_id, update_data, changed_by='edit_form')
            if update_booking(booking_id, update_data):
                # Cache removed - data will be fresh automatically
                flash('Booking updated successfully!', 'success')
                return redirect(url_for('view_bookings'))
            else:
                flash('Error updating booking', 'error')
        
        except Exception as e:
            flash(f'Error updating booking: {str(e)}', 'error')
    
    return render_template('edit_booking.html', booking=booking)

@app.route('/api/cancel_booking/<booking_id>', methods=['POST'])
def cancel_booking_api(booking_id):
    """Cancel booking (soft cancel - changes status to 'cancelled')"""
    try:
        if cancel_booking_by_id(booking_id):
            return jsonify({'status': 'success', 'success': True, 'message': 'Booking cancelled successfully'})
        else:
            return jsonify({'status': 'error', 'success': False, 'message': 'Failed to cancel booking'}), 400
    
    except Exception as e:
        return jsonify({'status': 'error', 'success': False, 'message': str(e)}), 500

@app.route('/api/delete_booking/<booking_id>', methods=['DELETE'])
def delete_booking_api(booking_id):
    """Delete booking permanently from PostgreSQL"""
    try:
        if delete_booking_by_id(booking_id):
            # Cache removed - data will be fresh automatically
            return jsonify({'status': 'success', 'success': True, 'message': 'Booking deleted permanently'})
        else:
            return jsonify({'status': 'error', 'success': False, 'message': 'Failed to delete booking'}), 400
    
    except Exception as e:
        return jsonify({'status': 'error', 'success': False, 'message': str(e)}), 500

@app.route('/bookings/cancel_multiple', methods=['POST'])
def cancel_multiple_bookings():
    """Cancel multiple bookings (soft cancel - changes status to 'cancelled')"""
    try:
        data = request.get_json()
        if not data or 'booking_ids' not in data:
            return jsonify({'success': False, 'message': 'No booking IDs provided'}), 400
        
        booking_ids = data['booking_ids']
        if not isinstance(booking_ids, list) or len(booking_ids) == 0:
            return jsonify({'success': False, 'message': 'Invalid booking IDs list'}), 400
        
        print(f"🔄 CANCEL MULTIPLE: Attempting to cancel {len(booking_ids)} bookings")
        print(f"🔄 BOOKING IDS: {booking_ids}")
        
        # Cancel each booking (soft cancel)
        cancelled_count = 0
        failed_ids = []
        
        for booking_id in booking_ids:
            try:
                if cancel_booking_by_id(booking_id):
                    cancelled_count += 1
                    print(f"✅ CANCELLED: Booking {booking_id}")
                else:
                    failed_ids.append(booking_id)
                    print(f"❌ FAILED TO CANCEL: Booking {booking_id}")
            except Exception as e:
                failed_ids.append(booking_id)
                print(f"❌ ERROR cancelling booking {booking_id}: {str(e)}")
        
        # Prepare response
        if cancelled_count > 0:
            message = f"Đã hủy thành công {cancelled_count} booking"
            if failed_ids:
                message += f", thất bại {len(failed_ids)} booking"
            
            print(f"🎯 CANCEL RESULT: {cancelled_count} success, {len(failed_ids)} failed")
            return jsonify({
                'success': True,
                'message': message,
                'cancelled_count': cancelled_count,
                'failed_count': len(failed_ids),
                'failed_ids': failed_ids
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Không thể hủy booking nào',
                'cancelled_count': 0,
                'failed_count': len(failed_ids),
                'failed_ids': failed_ids
            }), 400
    
    except Exception as e:
        print(f"❌ ERROR in cancel_multiple_bookings: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/bookings/delete_multiple', methods=['POST'])
def delete_multiple_bookings():
    """PERMANENTLY DELETE multiple bookings from PostgreSQL (NOT CANCEL)"""
    try:
        data = request.get_json()
        if not data or 'booking_ids' not in data:
            return jsonify({'success': False, 'message': 'No booking IDs provided'}), 400
        
        booking_ids = data['booking_ids']
        if not isinstance(booking_ids, list) or len(booking_ids) == 0:
            return jsonify({'success': False, 'message': 'Invalid booking IDs list'}), 400
        
        print(f"🗑️ DELETE MULTIPLE: Attempting to PERMANENTLY DELETE {len(booking_ids)} bookings")
        print(f"🗑️ BOOKING IDS: {booking_ids}")
        
        # PERMANENTLY DELETE each booking
        deleted_count = 0
        failed_ids = []
        
        for booking_id in booking_ids:
            try:
                if delete_booking_by_id(booking_id):
                    deleted_count += 1
                    print(f"✅ DELETED PERMANENTLY: Booking {booking_id}")
                else:
                    failed_ids.append(booking_id)
                    print(f"❌ FAILED TO DELETE: Booking {booking_id}")
            except Exception as e:
                failed_ids.append(booking_id)
                print(f"❌ ERROR deleting booking {booking_id}: {str(e)}")
        
        # Prepare response
        if deleted_count > 0:
            message = f"Đã XÓA VĨNH VIỄN {deleted_count} booking"
            if failed_ids:
                message += f", thất bại {len(failed_ids)} booking"
            
            print(f"🎯 DELETE RESULT: {deleted_count} success, {len(failed_ids)} failed")
            return jsonify({
                'success': True, 
                'message': message,
                'deleted_count': deleted_count,
                'failed_count': len(failed_ids),
                'failed_ids': failed_ids
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'Không thể xóa booking nào',
                'failed_ids': failed_ids
            }), 400
            
    except Exception as e:
        print(f"❌ DELETE MULTIPLE ERROR: {str(e)}")
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'}), 500

@app.route('/api/delete_booking', methods=['POST'])
def delete_single_booking():
    """Delete a single booking from PostgreSQL"""
    try:
        data = request.get_json()
        if not data or 'booking_id' not in data:
            return jsonify({'success': False, 'error': 'No booking ID provided'}), 400
        
        booking_id = data['booking_id']
        if not booking_id:
            return jsonify({'success': False, 'error': 'Invalid booking ID'}), 400
        
        print(f"🗑️ DELETE SINGLE: Attempting to delete booking {booking_id}")
        
        # Delete the booking
        if delete_booking_by_id(booking_id):
            print(f"✅ DELETED: Booking {booking_id}")
            return jsonify({
                'success': True, 
                'message': f'Đã xóa thành công booking {booking_id}'
            })
        else:
            print(f"❌ FAILED: Could not delete booking {booking_id}")
            return jsonify({
                'success': False, 
                'error': f'Không thể xóa booking {booking_id}'
            }), 400
            
    except Exception as e:
        print(f"❌ DELETE SINGLE ERROR: {str(e)}")
        return jsonify({'success': False, 'error': f'Lỗi server: {str(e)}'}), 500

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

@app.route('/api/process_booking_table', methods=['POST'])
def process_booking_table():
    """Process the specific booking table format with manual extraction"""
    try:
        # Manual extraction data based on example.png analysis
        bookings_data = [
            {
                "guest_name": "Piotr Konczakowski",
                "checkin_date": "2025-09-30",
                "checkout_date": "2025-10-03",
                "room_amount": 995950,
                "commission": 201001,
                "accommodation_name": "Căn Hộ 1 Phòng Ngủ",
                "booking_platform": "Genius",
                "guest_count": 2,
                "booking_id": "6675995308",
                "booking_status": "confirmed",
                "extraction_method": "manual_table_processing"
            },
            {
                "guest_name": "Lara Schroeder", 
                "checkin_date": "2025-09-30",
                "checkout_date": "2025-10-05",
                "room_amount": 1647845,
                "commission": 298786,
                "accommodation_name": "Căn Hộ 1 Phòng Ngủ",
                "booking_platform": "Genius",
                "guest_count": 2,
                "booking_id": "6848283925",
                "booking_status": "confirmed",
                "extraction_method": "manual_table_processing"
            },
            {
                "guest_name": "murat percin",
                "checkin_date": "2025-10-01",
                "checkout_date": "2025-10-05",
                "room_amount": 2178540,
                "commission": 326781,
                "accommodation_name": "Căn Hộ 1 Phòng Ngủ",
                "booking_platform": "Genius",
                "guest_count": 2,
                "booking_id": "6213677291",
                "booking_status": "confirmed",
                "extraction_method": "manual_table_processing",
                "notes": "1 tin nhắn từ khách đang chờ - Quý vị trả lời"
            },
            {
                "guest_name": "SUBODH KUMAR BARAL",
                "checkin_date": "2025-10-03",
                "checkout_date": "2025-10-04",
                "room_amount": 542513,
                "commission": 81377,
                "accommodation_name": "Căn Hộ 1 Phòng Ngủ",
                "booking_platform": "Genius",
                "guest_count": 3,
                "booking_id": "5822406722",
                "booking_status": "confirmed",
                "extraction_method": "manual_table_processing"
            },
            {
                "guest_name": "Lang Van Thiên",
                "checkin_date": "2025-10-03",
                "checkout_date": "2025-10-06",
                "room_amount": 1417163,
                "commission": 212574,
                "accommodation_name": "Căn Hộ 1 Phòng Ngủ",
                "booking_platform": "Genius",
                "guest_count": 2,
                "booking_id": "6525759449",
                "booking_status": "confirmed",
                "extraction_method": "manual_table_processing"
            }
        ]
        
        # Add bookings to database
        from core.models import Booking, db
        from datetime import datetime
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        for booking_data in bookings_data:
            try:
                # Check if booking already exists
                existing = Booking.query.filter(
                    (Booking.guest_name == booking_data["guest_name"]) &
                    (Booking.checkin_date == datetime.strptime(booking_data["checkin_date"], "%Y-%m-%d").date()) &
                    (Booking.checkout_date == datetime.strptime(booking_data["checkout_date"], "%Y-%m-%d").date())
                ).first()
                
                if existing:
                    print(f"⚠️ Booking already exists: {booking_data['guest_name']} - {booking_data['checkin_date']}")
                    skipped_count += 1
                    continue
                
                # Create new booking
                new_booking = Booking(
                    guest_name=booking_data["guest_name"],
                    checkin_date=datetime.strptime(booking_data["checkin_date"], "%Y-%m-%d").date(),
                    checkout_date=datetime.strptime(booking_data["checkout_date"], "%Y-%m-%d").date(),
                    room_amount=booking_data["room_amount"],
                    commission=booking_data.get("commission", 0),
                    accommodation_name=booking_data["accommodation_name"],
                    booking_platform=booking_data["booking_platform"],
                    guest_count=booking_data["guest_count"],
                    booking_status=booking_data["booking_status"],
                    extraction_method=booking_data["extraction_method"],
                    notes=booking_data.get("notes", "Imported from booking table image"),
                    collector="Manual Import"
                )
                
                db.session.add(new_booking)
                added_count += 1
                print(f"✅ Added: {booking_data['guest_name']} - {booking_data['checkin_date']} to {booking_data['checkout_date']}")
                
            except Exception as e:
                error_msg = f"Error adding booking {booking_data['guest_name']}: {str(e)}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
                skipped_count += 1
        
        # Commit all changes
        if added_count > 0:
            db.session.commit()
            print(f"🎯 Database committed: {added_count} bookings added")
        
        # Calculate summary
        total_revenue = sum(b["room_amount"] for b in bookings_data)
        total_commission = sum(b["commission"] for b in bookings_data)
        
        return jsonify({
            "success": True,
            "message": f"Successfully processed {len(bookings_data)} bookings from table",
            "results": {
                "total_bookings": len(bookings_data),
                "added": added_count,
                "skipped": skipped_count,
                "errors": len(errors)
            },
            "summary": {
                "total_revenue": total_revenue,
                "total_commission": total_commission,
                "date_range": "2025-09-30 to 2025-10-06"
            },
            "bookings": bookings_data,
            "error_details": errors if errors else None
        })
        
    except Exception as e:
        print(f"❌ Processing error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Processing error: {str(e)}"
        }), 500

@app.route('/api/booking_entry_options', methods=['GET'])
def get_booking_entry_options():
    """Get available booking entry methods and their status"""
    try:
        # Check API availability (simplified check)
        gemini_keys = []
        openrouter_keys = []
        
        for i in range(1, 6):
            key_name = f'GEMINI_API_KEY_{i}' if i > 1 else 'GEMINI_API_KEY'
            key = os.getenv(key_name)
            if key and key.strip():
                gemini_keys.append(key_name)
        
        for i in range(1, 6):
            key_name = f'OPENROUTER_API_KEY_{i}' if i > 1 else 'OPENROUTER_API_KEY'
            key = os.getenv(key_name)
            if key and key.strip():
                openrouter_keys.append(key_name)
        
        total_api_keys = len(gemini_keys) + len(openrouter_keys)
        ai_available = total_api_keys > 0
        
        return jsonify({
            'success': True,
            'options': {
                'ai_extraction': {
                    'available': ai_available,
                    'description': f'Upload booking screenshot for automatic extraction ({total_api_keys} APIs configured)',
                    'status': f'{total_api_keys} APIs configured' if ai_available else 'No APIs configured',
                    'api_details': {
                        'gemini_keys': len(gemini_keys),
                        'openrouter_keys': len(openrouter_keys)
                    }
                },
                'manual_entry': {
                    'available': True,
                    'description': 'Manual form entry - always available as fallback',
                    'status': 'Always available'
                }
            },
            'recommendation': 'ai_extraction' if ai_available else 'manual_entry',
            'fallback_message': 'Manual entry is available when AI extraction fails'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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

@app.route('/api/fix_expense_descriptions', methods=['POST'])
def fix_expense_descriptions():
    """Fix expense descriptions that show dates instead of content"""
    try:
        print("🔧 [FIX_DESCRIPTIONS] Starting expense description fix...")
        
        # Correct descriptions mapping based on your data
        CORRECT_DESCRIPTIONS = {
            118: "ăn đêm", 117: "mua dầu ăn", 116: "thay hộp cửa cuốn", 115: "Hưng mượn",
            114: "mua trứng", 113: "an cơm trưa", 112: "sửa xe", 111: "đổ xăng",
            110: "mua cháo", 109: "Ăn bánh xèo", 108: "mua sữa tắm", 107: "thanh toán shopeee",
            106: "thanh toán visa", 105: "Ăn phở rán", 104: "in tờ hướng dẫn", 103: "mua chậu giặt cây lau",
            102: "ăn đêm", 101: "Đổ xăng", 100: "Ăn bún riêu", 99: "Mua dầu gội + sáp thơm",
            98: "thanh toán booking ta hien Hưng", 97: "mua đèn ( 3 bóng , 1 ray )", 96: "mua tương ớt",
            95: "trả tiền xe", 94: "Ăn cơm", 93: "Mua tủ quần áo", 92: "Gửi hàng cho Hưng",
            91: "ăn nướng", 90: "Ăn vặt", 89: "Mua 1 chậu ngâm tẩy", 88: "Mua 2 chai xịt phòng"
        }
        
        # Import models
        from core.models import db, Expense
        
        fixed_count = 0
        not_found_count = 0
        
        for expense_id, correct_description in CORRECT_DESCRIPTIONS.items():
            # Find the expense
            expense = Expense.query.filter_by(expense_id=expense_id).first()
            
            if expense:
                old_desc = expense.description
                expense.description = correct_description
                print(f"✅ Fixed ID {expense_id}: '{old_desc}' → '{correct_description}'")
                fixed_count += 1
            else:
                print(f"⚠️ Expense ID {expense_id} not found in database")
                not_found_count += 1
        
        # Commit all changes
        db.session.commit()
        
        message = f"Fixed {fixed_count} expense descriptions successfully!"
        if not_found_count > 0:
            message += f" ({not_found_count} IDs not found)"
            
        print(f"🎉 [FIX_DESCRIPTIONS] {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'fixed_count': fixed_count,
            'not_found_count': not_found_count
        })
        
    except Exception as e:
        print(f"❌ [FIX_DESCRIPTIONS] Error: {e}")
        # Rollback on error
        try:
            from core.models import db
            db.session.rollback()
        except:
            pass
            
        return jsonify({
            'success': False,
            'message': f'Error fixing descriptions: {str(e)}'
        }), 500

@app.route('/api/expense_categories', methods=['GET', 'POST'])
def expense_categories_api():
    """Save and load expense categorizations (Personal/Work)"""
    try:
        from core.models import db, ExpenseCategory
        
        if request.method == 'GET':
            # Load all categorizations
            categories = ExpenseCategory.query.all()
            result = {}
            for cat in categories:
                result[str(cat.expense_id)] = cat.category
            
            print(f"📂 [LOAD_CATEGORIES] Loaded {len(result)} categorizations")
            return jsonify({
                'success': True,
                'categories': result
            })
            
        elif request.method == 'POST':
            # Save categorizations
            data = request.get_json()
            expense_ids = data.get('expense_ids', [])
            category = data.get('category', '')
            
            if not expense_ids or category not in ['personal', 'work']:
                return jsonify({
                    'success': False,
                    'message': 'Invalid expense IDs or category'
                }), 400
            
            # Remove duplicates from expense_ids to prevent constraint violations
            unique_expense_ids = list(set(expense_ids))
            
            saved_count = 0
            errors = []
            
            # Fix sequence issue by resetting PostgreSQL auto-increment sequence first
            from sqlalchemy import text
            
            try:
                # Reset the sequence to avoid ID conflicts
                db.session.execute(text("SELECT setval('expense_categories_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM expense_categories), false)"))
                print("🔧 [SEQUENCE_FIX] Reset auto-increment sequence for expense_categories")
            except Exception as seq_error:
                print(f"⚠️ [SEQUENCE_WARNING] Could not reset sequence: {seq_error}")
            
            for expense_id in unique_expense_ids:
                try:
                    print(f"🔍 [UPSERT_CATEGORY] Processing expense {expense_id} → {category}")
                    
                    # First try to update existing record
                    update_result = db.session.execute(
                        text("""
                            UPDATE expense_categories 
                            SET category = :category, updated_at = CURRENT_TIMESTAMP 
                            WHERE expense_id = :expense_id
                            RETURNING id, expense_id, category
                        """), 
                        {"expense_id": expense_id, "category": category}
                    )
                    
                    row = update_result.fetchone()
                    if row:
                        print(f"✅ [UPDATE_SUCCESS] Updated expense {expense_id} → {category} (Record ID: {row[0]})")
                        saved_count += 1
                    else:
                        # No existing record, create new one
                        insert_result = db.session.execute(
                            text("""
                                INSERT INTO expense_categories (expense_id, category, created_at, updated_at)
                                VALUES (:expense_id, :category, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                RETURNING id, expense_id, category
                            """), 
                            {"expense_id": expense_id, "category": category}
                        )
                        
                        row = insert_result.fetchone()
                        if row:
                            print(f"✅ [INSERT_SUCCESS] Created expense {expense_id} → {category} (Record ID: {row[0]})")
                            saved_count += 1
                        else:
                            errors.append(f"Expense {expense_id}: Failed to insert or update")
                    
                except Exception as item_error:
                    # Simple error handling for UPSERT approach
                    print(f"❌ [UPSERT_ERROR] Failed to process expense {expense_id}: {str(item_error)}")
                    db.session.rollback()
                    errors.append(f"Expense {expense_id}: {str(item_error)}")
            
            # Final commit for any remaining changes
            try:
                db.session.commit()
            except Exception as final_error:
                db.session.rollback()
                errors.append(f"Final commit failed: {str(final_error)}")
            
            if errors:
                return jsonify({
                    'success': saved_count > 0,
                    'message': f'Saved {saved_count} categorizations. Errors: {"; ".join(errors)}',
                    'saved_count': saved_count,
                    'errors': errors
                }), 422 if saved_count > 0 else 500
            else:
                return jsonify({
                    'success': True,
                    'message': f'Saved {saved_count} categorizations successfully!',
                    'saved_count': saved_count
                })
            
    except Exception as e:
        print(f"❌ [EXPENSE_CATEGORIES] Error: {e}")
        db.session.rollback() 
        return jsonify({
            'success': False,
            'message': f'Error with categorizations: {str(e)}'
        }), 500

@app.route('/api/create_categories_table', methods=['POST'])
def create_categories_table():
    """Create expense_categories table if it doesn't exist"""
    try:
        from core.models import db, ExpenseCategory
        
        # Create the table
        db.create_all()
        
        print("✅ [CREATE_TABLE] expense_categories table created successfully")
        return jsonify({
            'success': True,
            'message': 'Categories table created successfully!'
        })
        
    except Exception as e:
        print(f"❌ [CREATE_TABLE] Error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error creating table: {str(e)}'
        }), 500

@app.route('/api/analyze_expense_image', methods=['POST'])
def analyze_expense_image():
    """Analyze expense image using Gemini AI to extract expense data"""
    try:
        from datetime import datetime
        import json

        if not GOOGLE_API_KEY or not genai:
            return jsonify({'success': False, 'error': 'Gemini AI not configured'}), 500

        # Check if image was uploaded
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        print(f"📸 [EXPENSE_AI] Processing image: {file.filename}")

        # Read image
        from PIL import Image
        import io

        image_bytes = file.read()
        image = Image.open(io.BytesIO(image_bytes))

        # Prepare AI prompt with enhanced date parsing
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        current_year = now.year
        current_month = now.month

        prompt = f"""
You are an AI assistant that extracts expense/revenue data from images (screenshots, receipts, chat messages, etc.).

**Task:** Extract ALL expense entries from this image and return them as a JSON array.

**Expected Input Formats:**
- Chat messages: "Mua 3 cây giá 900,000." or "Đổ xăng 90,000"
- Receipts with itemized lists
- Handwritten notes
- Bank transaction screenshots

**Extraction Rules:**
1. **Description:** Extract the full expense description in Vietnamese
   - Example: "Mua 3 cây giá" → "Mua 3 cây giá"
   - Example: "Đổ xăng" → "Đổ xăng"

2. **Amount:** Extract numeric value only (remove commas, currency symbols)
   - "900,000đ" → 900000
   - "90.000" → 90000
   - "170k" → 170000

3. **Date:** Extract or infer date (CRITICAL RULES - READ CAREFULLY)
   - **Format:** YYYY-MM-DD (e.g., {today})

   - **DAY-ONLY inputs** (e.g., "20", "20th", "ngày 20", "mùng 20"):
     * Use CURRENT month and year: {current_year}-{current_month:02d}-[day]
     * Example: "20" → "{current_year}-{current_month:02d}-20"
     * Example: "15th" → "{current_year}-{current_month:02d}-15"
     * Example: "ngày 5" → "{current_year}-{current_month:02d}-05"
     * ⚠️ DO NOT interpret "20" as month "02"! It's day 20!

   - **Full date visible** (e.g., "20/01/2026", "2026-01-20"):
     * Extract exact date in YYYY-MM-DD format
     * "20/01/2026" → "2026-01-20"
     * "01/20/2026" → "2026-01-20"

   - **"Hôm nay", "Today", or time only** (e.g., "15:02", "16:05"):
     * Use TODAY's date: {today}

   - **Validation:**
     * Day must be 01-31
     * Month must be 01-12
     * Use leading zeros (05, not 5)

4. **Category:** Auto-categorize as "personal" or "work" or null
   - Personal: food, gas, personal items → "personal"
   - Work: office supplies, equipment → "work"
   - Uncertain: leave as null

**Output Format (JSON Array):**
```json
[
  {{
    "description": "Mua 3 cây giá",
    "amount": 900000,
    "date": "{today}",
    "category": "work"
  }},
  {{
    "description": "Mua 1 máy sấy",
    "amount": 170000,
    "date": "{today}",
    "category": "personal"
  }}
]
```

**Important:**
- Return ONLY the JSON array, no other text
- Include ALL expenses found in the image
- Use null for missing/uncertain values
- Preserve Vietnamese characters exactly
- Today's date is: {today}
- Current month/year: {current_year}-{current_month:02d}

Extract all expenses now:
"""

        # Call Gemini AI
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image])

        print(f"🤖 [EXPENSE_AI] AI Response: {response.text[:200]}...")

        # Parse JSON from response
        response_text = response.text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()

        # Parse JSON
        expenses = json.loads(response_text)

        if not isinstance(expenses, list):
            raise ValueError('AI response is not a JSON array')

        print(f"✅ [EXPENSE_AI] Extracted {len(expenses)} expenses")

        return jsonify({
            'success': True,
            'expenses': expenses,
            'count': len(expenses)
        })

    except json.JSONDecodeError as e:
        print(f"❌ [EXPENSE_AI] JSON parsing error: {e}")
        print(f"   Response was: {response_text if 'response_text' in locals() else 'N/A'}")
        return jsonify({'success': False, 'error': 'AI response is not valid JSON. Please try again or use manual entry.'}), 400

    except Exception as e:
        print(f"❌ [EXPENSE_AI] Error analyzing image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/expenses/bulk', methods=['POST'])
def bulk_add_expenses():
    """Add multiple expenses at once (from AI or JSON input)"""
    try:
        from core.models import db, Expense
        from datetime import datetime

        data = request.get_json()
        if not data or 'expenses' not in data:
            return jsonify({'success': False, 'error': 'No expenses provided'}), 400

        expenses_data = data['expenses']
        if not isinstance(expenses_data, list):
            return jsonify({'success': False, 'error': 'Expenses must be an array'}), 400

        print(f"💾 [BULK_EXPENSES] Adding {len(expenses_data)} expenses...")

        added_count = 0
        for exp_data in expenses_data:
            # Validate required fields
            if not exp_data.get('description') or not exp_data.get('amount') or not exp_data.get('date'):
                print(f"⚠️ Skipping invalid expense: {exp_data}")
                continue

            # Create expense
            new_expense = Expense(
                description=exp_data['description'],
                amount=float(exp_data['amount']),
                expense_date=datetime.strptime(exp_data['date'], '%Y-%m-%d').date()
            )

            db.session.add(new_expense)
            db.session.flush()  # Get expense_id

            # Add category if provided
            if exp_data.get('category'):
                from core.models import ExpenseCategory
                category = ExpenseCategory(
                    expense_id=new_expense.expense_id,
                    category=exp_data['category']
                )
                db.session.add(category)

            added_count += 1
            print(f"  ✅ Added: {exp_data['description']} - {exp_data['amount']}đ")

        db.session.commit()

        print(f"✅ [BULK_EXPENSES] Successfully added {added_count} expenses")

        return jsonify({
            'success': True,
            'count': added_count,
            'message': f'Added {added_count} expenses successfully'
        })

    except Exception as e:
        print(f"❌ [BULK_EXPENSES] Error: {e}")
        import traceback
        traceback.print_exc()

        try:
            db.session.rollback()
        except:
            pass

        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/bookings/save_extracted', methods=['POST'])
def save_extracted_bookings():
    """Save multiple extracted bookings from AI photo processing"""
    try:
        print("🚀 [SAVE_EXTRACTED] API called - saving multiple bookings")
        
        # Get extracted bookings from form data
        extracted_json = request.form.get('extracted_json')
        force_add_duplicates = request.form.get('force_add_duplicates') == 'true'
        
        print(f"🔧 [SAVE_EXTRACTED] Force add duplicates setting: {force_add_duplicates}")
        print(f"🔧 [SAVE_EXTRACTED] Raw form value: '{request.form.get('force_add_duplicates')}'")
        print(f"🔧 [SAVE_EXTRACTED] All form keys: {list(request.form.keys())}")
        
        if not extracted_json:
            print("❌ [SAVE_EXTRACTED] No extracted_json provided")
            return jsonify({'success': False, 'error': 'Không có dữ liệu booking để lưu'})
        
        try:
            bookings_data = json.loads(extracted_json)
            print(f"📊 [SAVE_EXTRACTED] Received {len(bookings_data)} bookings to save")
        except json.JSONDecodeError as e:
            print(f"❌ [SAVE_EXTRACTED] JSON decode error: {e}")
            return jsonify({'success': False, 'error': 'Dữ liệu booking không hợp lệ'})
        
        if not isinstance(bookings_data, list) or len(bookings_data) == 0:
            print("❌ [SAVE_EXTRACTED] Invalid bookings data format")
            return jsonify({'success': False, 'error': 'Dữ liệu booking không hợp lệ'})
        
        # Process and save each booking
        saved_count = 0
        replaced_count = 0
        forced_duplicate_count = 0  # Track bookings added despite being duplicates
        failed_bookings = []
        existing_bookings = []  # Track bookings that already exist
        
        for i, booking_data in enumerate(bookings_data):
            try:
                guest_name = booking_data.get('guest_name', '')
                booking_id = booking_data.get('booking_id', '')
                
                print(f"💾 [SAVE_EXTRACTED] Processing booking {i+1}: {guest_name}")
                
                # Check if this is a replacement operation FIRST (before checking existing)
                is_replacement = booking_data.get('replace_mode') and booking_data.get('replace_existing_id')
                
                # Check if booking ID already exists (only skip if NOT a replacement AND force_add not enabled)
                existing_booking = load_booking_data()
                booking_exists = not existing_booking.empty and booking_id and booking_id in existing_booking['Số đặt phòng'].values
                
                if booking_exists and not is_replacement and not force_add_duplicates:
                    print(f"ℹ️ [SAVE_EXTRACTED] Booking ID {booking_id} already exists - skipping (not an error)")
                    existing_bookings.append(f"Booking {i+1}: {guest_name} - Already exists in system ({booking_id})")
                    continue
                elif booking_exists and force_add_duplicates:
                    print(f"💪 [SAVE_EXTRACTED] FORCE ADD MODE: Booking ID {booking_id} already exists - FORCE ADDING as requested")
                    # Generate new unique booking ID for the duplicate
                    original_booking_id = booking_id
                    booking_id = f"{booking_id}_DUP_{datetime.now().strftime('%H%M%S')}"
                    print(f"🆔 [SAVE_EXTRACTED] Generated NEW duplicate booking ID: {original_booking_id} → {booking_id}")
                    booking_data['booking_id'] = booking_id  # Update the booking data
                    forced_duplicate_count += 1
                elif booking_exists:
                    print(f"⚠️ [SAVE_EXTRACTED] Booking ID {booking_id} exists but conditions unclear:")
                    print(f"   - is_replacement: {is_replacement}")
                    print(f"   - force_add_duplicates: {force_add_duplicates}")
                    existing_bookings.append(f"Booking {i+1}: {guest_name} - Already exists in system ({booking_id})")
                    continue
                elif is_replacement:
                    print(f"🔄 [SAVE_EXTRACTED] Replacement mode detected for {guest_name} - proceeding with replacement")
                
                # Generate unique booking ID if empty or duplicate
                if not booking_id:
                    booking_id = f"AI_{datetime.now().strftime('%Y%m%d%H%M%S')}{i:02d}"
                    print(f"🔄 [SAVE_EXTRACTED] Generated new booking ID: {booking_id}")
                
                # Generate unique email to avoid constraint violations
                unique_email = f"guest{booking_id.lower()}@ai-extracted.local"
                print(f"📧 [SAVE_EXTRACTED] Generated unique email: {unique_email}")
                
                # Parse dates with multiple format support
                checkin_date = None
                checkout_date = None
                
                # Try multiple date formats
                checkin_str = booking_data.get('checkin_date') or booking_data.get('check_in_date', '')
                checkout_str = booking_data.get('checkout_date') or booking_data.get('check_out_date', '')
                
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
                
                for date_format in date_formats:
                    try:
                        if checkin_str and not checkin_date:
                            checkin_date = datetime.strptime(str(checkin_str), date_format).date()
                        if checkout_str and not checkout_date:
                            checkout_date = datetime.strptime(str(checkout_str), date_format).date()
                        if checkin_date and checkout_date:
                            break
                    except ValueError:
                        continue
                
                # Extract accommodation name from the booking data (set by frontend)
                accommodation_name = (booking_data.get('Tên chỗ nghỉ') or
                                     booking_data.get('room_type') or
                                     booking_data.get('room_name') or
                                     '118 Hang Bac Hostel')
                print(f"🏠 [SAVE_EXTRACTED] Room type selected: {accommodation_name}")
                print(f"🔍 [DEBUG_ROOM] All room-related fields in booking_data:")
                print(f"   - 'Tên chỗ nghỉ': {booking_data.get('Tên chỗ nghỉ', 'NOT SET')}")
                print(f"   - 'room_name': {booking_data.get('room_name', 'NOT SET')}")
                print(f"   - 'room_type': {booking_data.get('room_type', 'NOT SET')}")
                print(f"   - 'accommodation_name': {booking_data.get('accommodation_name', 'NOT SET')}")
                
                # Convert to expected format for add_new_booking function
                processed_booking = {
                    'guest_name': str(guest_name).strip() if guest_name else '',
                    'booking_id': str(booking_id).strip() if booking_id else '',
                    'email': unique_email,
                    'phone': str(booking_data.get('phone', '')).strip(),
                    'nationality': str(booking_data.get('nationality', '')).strip(),
                    'passport_number': str(booking_data.get('passport_number', '')).strip(),
                    'accommodation_name': accommodation_name,  # Include room type/property name
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'room_amount': safe_parse_vietnamese_number(booking_data.get('room_amount'), 0.0),
                    'commission': safe_parse_vietnamese_number(booking_data.get('commission'), 0.0),
                    'taxi_amount': safe_parse_vietnamese_number(booking_data.get('taxi_amount'), 0.0),
                    'collector': '',
                    'notes': f"AI extracted on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                }
                
                # Validate and clean guest name (ensure it's text, not ID)
                if not processed_booking['guest_name']:
                    raise ValueError("Missing guest name")
                
                # Ensure guest name contains letters (not just numbers)
                guest_name_clean = processed_booking['guest_name'].strip()
                if guest_name_clean.isdigit():
                    print(f"⚠️ [SAVE_EXTRACTED] Guest name is numeric ID '{guest_name_clean}', skipping this booking")
                    raise ValueError(f"Tên khách '{guest_name_clean}' chỉ là số — vui lòng nhập tên thật")
                
                if len(guest_name_clean) < 2:
                    print(f"⚠️ [SAVE_EXTRACTED] Guest name too short '{guest_name_clean}', skipping this booking")
                    raise ValueError(f"Guest name too short: {guest_name_clean}")
                
                # Update with cleaned name
                processed_booking['guest_name'] = guest_name_clean
                
                if not processed_booking['checkin_date']:
                    raise ValueError("Missing check-in date")
                if not processed_booking['checkout_date']:
                    raise ValueError("Missing check-out date")
                if processed_booking['room_amount'] <= 0:
                    raise ValueError("Invalid room amount")
                
                # Check if this is a replacement operation
                print(f"🔍 [DEBUG] Checking booking {i+1} for replacement mode:")
                print(f"   - replace_mode: {booking_data.get('replace_mode')}")
                print(f"   - replace_existing_id: {booking_data.get('replace_existing_id')}")
                
                if booking_data.get('replace_mode') and booking_data.get('replace_existing_id'):
                    # Handle replacement of existing booking
                    replace_existing_id = booking_data.get('replace_existing_id')
                    print(f"🔄 [REPLACE_MODE] Replacing existing booking ID: {replace_existing_id}")
                    print(f"🔄 [REPLACE_MODE] New data: {processed_booking['guest_name']} - {processed_booking['room_amount']}")
                    
                    if update_booking(replace_existing_id, processed_booking):
                        replaced_count += 1
                        print(f"✅ [SAVE_EXTRACTED] Replaced booking {i+1}: {processed_booking['guest_name']} (ID: {replace_existing_id})")
                    else:
                        failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - Replacement failed")
                        print(f"❌ [REPLACE_MODE] Replacement failed for booking {i+1}")
                else:
                    print(f"➕ [NEW_BOOKING] Creating new booking for {processed_booking['guest_name']}")
                    # Save as new booking using existing function
                    if add_new_booking(processed_booking):
                        saved_count += 1
                        print(f"✅ [SAVE_EXTRACTED] Saved booking {i+1}: {processed_booking['guest_name']}")
                    else:
                        failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - Database save failed")
                    
            except Exception as booking_error:
                print(f"❌ [SAVE_EXTRACTED] Error saving booking {i+1}: {booking_error}")
                import traceback
                traceback.print_exc()
                failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - {str(booking_error)}")
        
        # Prepare result message
        total_processed = saved_count + replaced_count + forced_duplicate_count
        if total_processed > 0:
            success_parts = []
            if saved_count > 0:
                success_parts.append(f"{saved_count} booking mới")
            if replaced_count > 0:
                success_parts.append(f"{replaced_count} booking đã thay thế")
            if forced_duplicate_count > 0:
                success_parts.append(f"{forced_duplicate_count} booking trùng lặp được thêm")
            
            success_msg = f"✅ Đã xử lý thành công {' và '.join(success_parts)}"
            if existing_bookings or failed_bookings:
                total_skipped = len(existing_bookings) + len(failed_bookings)
                success_msg += f" (bỏ qua {total_skipped} booking)"
            flash(success_msg, 'success')
            
            # Show forced duplicates message
            if forced_duplicate_count > 0:
                flash(f"💪 Đã thêm {forced_duplicate_count} booking trùng lặp với ID mới (có thể chỉnh sửa riêng biệt)", 'warning')
            
        # Show replacement summary if any
        if replaced_count > 0:
            flash(f"🔄 Đã thay thế {replaced_count} booking cũ với dữ liệu mới", 'info')
        
        # Show existing bookings as info (not errors)
        if existing_bookings:
            for existing in existing_bookings:
                flash(f"ℹ️ {existing}", 'info')
        
        # Show actual errors
        if failed_bookings:
            for error in failed_bookings:
                flash(f"❌ {error}", 'error')
        
        # If nothing was processed and no existing bookings
        if total_processed == 0 and len(existing_bookings) == 0:
            flash('❌ Không thể lưu booking nào. Vui lòng kiểm tra dữ liệu và thử lại.', 'error')
        
        print(f"🎯 [SAVE_EXTRACTED] Complete: {saved_count} saved, {replaced_count} replaced, {len(existing_bookings)} existing, {len(failed_bookings)} failed")
        
        # Return JSON response for frontend compatibility
        return jsonify({
            'success': True,
            'saved_count': saved_count,
            'replaced_count': replaced_count,
            'existing_count': len(existing_bookings),
            'failed_count': len(failed_bookings),
            'failed_details': failed_bookings,
            'message': f'Đã xử lý {total_processed} booking thành công'
        })
        
    except Exception as e:
        print(f"❌ [SAVE_EXTRACTED] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Lỗi hệ thống khi lưu booking: {str(e)}'})

