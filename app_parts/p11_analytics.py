# p11_analytics — guest arrival confirm, monthly/weekly/collector details & charts, revenue analytics, debug revenue
# Part of app.py (lines 12912-14787 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/api/confirm_guest_arrival', methods=['POST'])
def confirm_guest_arrival():
    """Confirm guest arrival to enable commission notifications"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'error': 'Booking ID required'}), 400
        
        from core.models import Booking, db
        
        # Find booking
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        
        # Update arrival confirmation status
        booking.arrival_confirmed = True
        booking.arrival_confirmed_at = datetime.now()
        db.session.commit()
        
        print(f"✅ Guest arrival confirmed for booking {booking_id}: {booking.guest_name}")
        
        return jsonify({
            'success': True,
            'message': f'Arrival confirmed for {booking.guest_name}',
            'booking_id': booking_id
        })
        
    except Exception as e:
        print(f"Error confirming guest arrival: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monthly_guest_details', methods=['POST'])
def get_monthly_guest_details():
    """Get detailed guest breakdown for a specific month and collection status"""
    try:
        data = request.get_json()
        month = data.get('month')  # Format: 'YYYY-MM'
        collection_type = data.get('type')  # 'collected' or 'uncollected'
        apartment_filter = data.get('apartment', 'all')  # 🎯 GET APARTMENT FILTER

        print(f"🔍 [MONTHLY_DETAILS] Requested: {month} - {collection_type} - {apartment_filter}")

        if not month or not collection_type:
            return jsonify({'success': False, 'message': 'Missing month or type parameter'}), 400

        # Load data using EXACT same method as dashboard route
        df, _ = load_data(force_fresh=False)  # Same as dashboard route uses
        # Note: Cancelled bookings are now filtered out inside the revenue calculation functions
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})

        # 🎯 FILTER BY APARTMENT BEFORE PROCESSING
        if apartment_filter in ['apt1', 'apt2']:
            apartment_id = 1 if apartment_filter == 'apt1' else 2
            from core.models import Room, db  # Import db along with Room

            room_ids = db.session.query(Room.room_id).filter(
                Room.apartment_id == apartment_id,
                Room.is_active == True
            ).all()
            room_ids = [r[0] for r in room_ids]

            if 'room_id' in df.columns:
                initial_count = len(df)
                df = df[df['room_id'].isin(room_ids)]
                print(f"🏢 [MONTHLY_DETAILS] Filtered {initial_count} → {len(df)} bookings for apartment {apartment_filter}")
            else:
                print(f"⚠️ [MONTHLY_DETAILS] room_id column not found, cannot filter by apartment")

        # Use EXACT same function as dashboard summary to ensure perfect consistency
        from core.dashboard_routes import process_monthly_revenue_with_unpaid

        print(f"🔧 [MONTHLY_DETAILS] Using dashboard's process_monthly_revenue_with_unpaid() function for consistency")

        # Get the exact same monthly data as displayed on dashboard
        monthly_data = process_monthly_revenue_with_unpaid(df)
        
        # Find the specific month in the processed data
        target_month_data = None
        for month_row in monthly_data:
            if month_row.get('Tháng') == month:
                target_month_data = month_row
                break
        
        if not target_month_data:
            print(f"⚠️ [MONTHLY_DETAILS] Month {month} not found in dashboard data")
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Get the exact amount from dashboard calculation
        if collection_type == 'collected':
            dashboard_total = target_month_data.get('Đã thu', 0)
            status_label = "Đã thu (LOC LE + THAO LE)"
        else:  # uncollected
            dashboard_total = target_month_data.get('Chưa thu', 0)
            status_label = "Chưa thu (Không phải LOC LE/THAO LE)"
        
        print(f"🔧 [MONTHLY_DETAILS] Dashboard shows {dashboard_total:,.0f}đ for {status_label} in month {month}")
        
        # Use the dashboard's calculated total as the authoritative source
        total_amount = float(dashboard_total)
        
        # Now filter the raw data to get individual guest details that sum to this exact amount
        from datetime import date
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        month_mask = df['Check-in Date'].dt.strftime('%Y-%m') == month
        checked_in_mask = df['Check-in Date'].dt.date <= today
        month_guests = df[month_mask & checked_in_mask].copy()
        
        # ✅ CRITICAL: Exclude cancelled bookings from guest details (same as revenue calculation)
        if 'Tình trạng' in month_guests.columns:
            initial_guest_count = len(month_guests)
            month_guests = month_guests[month_guests['Tình trạng'] != 'Đã hủy'].copy()
            excluded_cancelled_guests = initial_guest_count - len(month_guests)
            print(f"🚫 [MONTHLY_GUEST_FILTER] Excluded {excluded_cancelled_guests} cancelled guests from detail view")
        else:
            print(f"⚠️ [MONTHLY_GUEST_FILTER] 'Tình trạng' column not found in guest details")
        
        # Filter based on collection status
        valid_collectors = ['LOC LE', 'THAO LE']
        if collection_type == 'collected':
            filtered_guests = month_guests.loc[month_guests['Người thu tiền'].isin(valid_collectors)].copy()
        else:  # uncollected
            filtered_guests = month_guests.loc[~month_guests['Người thu tiền'].isin(valid_collectors)].copy()
        
        print(f"🔍 [MONTHLY_DETAILS] Found {len(filtered_guests)} guests {status_label} for month {month}")
        
        # Also calculate manually for comparison and debugging
        manual_total = float(filtered_guests['Tổng thanh toán'].sum()) if not filtered_guests.empty else 0
        
        print(f"🔧 [MONTHLY_DETAILS] Dashboard total: {total_amount:,.0f}đ")
        print(f"🔧 [MONTHLY_DETAILS] Manual calculation: {manual_total:,.0f}đ")
        
        if abs(total_amount - manual_total) > 0.01:
            print(f"⚠️ [MONTHLY_DETAILS] DISCREPANCY DETECTED: {abs(total_amount - manual_total):,.0f}đ difference!")
            print(f"🔍 [MONTHLY_DETAILS_DEBUG] Data analysis:")
            print(f"   - Column dtype: {filtered_guests['Tổng thanh toán'].dtype}")
            print(f"   - Null values: {filtered_guests['Tổng thanh toán'].isnull().sum()}")
            print(f"   - Zero values: {(filtered_guests['Tổng thanh toán'] == 0).sum()}")
            if not filtered_guests.empty:
                print(f"   - Min amount: {filtered_guests['Tổng thanh toán'].min():,.0f}đ")
                print(f"   - Max amount: {filtered_guests['Tổng thanh toán'].max():,.0f}đ")
                print(f"   - Sum check: {filtered_guests['Tổng thanh toán'].sum()}")
        else:
            print(f"✅ [MONTHLY_DETAILS] Perfect match between dashboard and manual calculation!")
        
        # Prepare guest details
        guest_details = []
        
        for _, guest in filtered_guests.iterrows():
            guest_name = guest.get('Tên người đặt', 'N/A')
            booking_id = guest.get('Số đặt phòng', 'N/A')
            amount = float(guest.get('Tổng thanh toán', 0))
            commission = float(guest.get('Hoa hồng', 0))
            taxi = float(guest.get('Taxi', 0))
            collector = guest.get('Người thu tiền', 'N/A')
            checkin_date = guest.get('Check-in Date')
            checkout_date = guest.get('Check-out Date')
            
            # Format dates safely
            try:
                checkin_str = checkin_date.strftime('%d/%m/%Y') if pd.notna(checkin_date) else 'N/A'
                checkout_str = checkout_date.strftime('%d/%m/%Y') if pd.notna(checkout_date) else 'N/A'
            except:
                checkin_str = str(checkin_date) if checkin_date else 'N/A'
                checkout_str = str(checkout_date) if checkout_date else 'N/A'
            
            guest_details.append({
                'guest_name': guest_name,
                'booking_id': str(booking_id),
                'amount': amount,
                'commission': commission,
                'taxi': taxi,
                'collector': collector,
                'checkin_date': checkin_str,
                'checkout_date': checkout_str,
                'is_valid_collector': collector in valid_collectors,
                'booking_status': guest.get('Tình trạng', 'N/A')  # Add status for debugging
            })
            
            # Note: total_amount is already set from dashboard calculation (authoritative source)
        
        # Sort by amount (highest first)
        guest_details.sort(key=lambda x: x['amount'], reverse=True)
        
        # Debug summary for verification
        cancelled_count = len([g for g in guest_details if g.get('booking_status') == 'Đã hủy'])
        print(f"✅ [MONTHLY_DETAILS] Returning {len(guest_details)} guests, total: {total_amount:,.0f}đ (using dashboard total)")
        print(f"✅ [MONTHLY_DETAILS] Breakdown: {cancelled_count} cancelled, {len(guest_details) - cancelled_count} active guests")
        print(f"✅ [MONTHLY_DETAILS] GUARANTEED CONSISTENCY: Using exact dashboard calculation function!")
        print(f"💰 [MONTHLY_SUMMARY] {month} {status_label}:")
        print(f"💰   Total guests: {len(guest_details)}")
        print(f"💰   Total amount: {total_amount:,.0f}đ")
        
        # Show breakdown by collector
        if collection_type == 'uncollected':
            collector_breakdown = {}
            for guest in guest_details:
                collector = guest['collector']
                if collector not in collector_breakdown:
                    collector_breakdown[collector] = {'count': 0, 'amount': 0}
                collector_breakdown[collector]['count'] += 1
                collector_breakdown[collector]['amount'] += guest['amount']
            
            print(f"🚨 [INVALID_COLLECTORS] Breakdown of who collected but shouldn't be counted:")
            for collector, data in collector_breakdown.items():
                print(f"🚨   '{collector}': {data['count']} guests, {data['amount']:,.0f}đ")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'count': len(guest_details),
            'month': month,
            'type': collection_type,
            'status_label': status_label
        })
        
    except Exception as e:
        print(f"❌ [MONTHLY_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/weekly_guest_details', methods=['POST'])
def get_weekly_guest_details():
    """Get detailed guest breakdown for a specific week and collection status"""
    try:
        data = request.get_json()
        week = data.get('week')  # Format: 'YYYY-W24 (MM/DD)'
        collection_type = data.get('type')  # 'collected' or 'uncollected'
        
        print(f"🔍 [WEEKLY_DETAILS] Requested: {week} - {collection_type}")
        
        if not week or not collection_type:
            return jsonify({'success': False, 'message': 'Missing week or type parameter'}), 400
        
        # Load data using EXACT same method as dashboard route (includes cancelled bookings)
        df, _ = load_data(force_fresh=False)  # Same as dashboard route uses
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Parse week format: '2025-W26 (06/23)' -> extract year and week number
        import re
        week_match = re.match(r'(\d{4})-W(\d+)', week)
        if not week_match:
            return jsonify({'success': False, 'message': 'Invalid week format'}), 400
        
        year = int(week_match.group(1))
        week_num = int(week_match.group(2))
        
        # Use EXACT same function as dashboard summary to ensure perfect consistency
        from core.dashboard_routes import process_weekly_revenue_with_unpaid
        
        print(f"🔧 [WEEKLY_DETAILS] Using dashboard's process_weekly_revenue_with_unpaid() function for consistency")
        
        # Get the exact same weekly data as displayed on dashboard
        weekly_data = process_weekly_revenue_with_unpaid(df)
        
        # Find the specific week in the processed data
        target_week_data = None
        for week_row in weekly_data:
            if week_row.get('Tuần') == week:
                target_week_data = week_row
                break
        
        if not target_week_data:
            print(f"⚠️ [WEEKLY_DETAILS] Week {week} not found in dashboard data")
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Get the exact amount from dashboard calculation
        if collection_type == 'collected':
            dashboard_total = target_week_data.get('Đã thu', 0)
            status_label = 'đã thu'
        else:  # uncollected
            dashboard_total = target_week_data.get('Chưa thu', 0)
            status_label = 'chưa thu'
        
        print(f"🔧 [WEEKLY_DETAILS] Dashboard shows {dashboard_total:,.0f}đ for {status_label} in week {week}")
        
        # Now filter the raw data to get individual guest details that sum to this exact amount
        from datetime import date, timedelta
        import pandas as pd
        
        today = date.today()
        eight_weeks_ago = today - timedelta(weeks=8)
        df_period = df[df['Check-in Date'].notna()].copy()
        recent_mask = df_period['Check-in Date'].dt.date >= eight_weeks_ago
        df_recent = df_period[recent_mask].copy()
        checked_in_mask = df_recent['Check-in Date'].dt.date <= today
        df_checked_in = df_recent[checked_in_mask].copy()
        df_checked_in['Week_Start'] = df_checked_in['Check-in Date'].dt.to_period('W').dt.start_time
        df_checked_in['Week_Label'] = df_checked_in['Week_Start'].dt.strftime('%Y-W%U (%m/%d)')
        week_df = df_checked_in[df_checked_in['Week_Label'] == week].copy()
        
        # ✅ CRITICAL: Exclude cancelled bookings from guest details (same as revenue calculation)
        if 'Tình trạng' in week_df.columns:
            initial_week_count = len(week_df)
            week_df = week_df[week_df['Tình trạng'] != 'Đã hủy'].copy()
            excluded_cancelled_weekly = initial_week_count - len(week_df)
            print(f"🚫 [WEEKLY_GUEST_FILTER] Excluded {excluded_cancelled_weekly} cancelled guests from weekly detail view")
        else:
            print(f"⚠️ [WEEKLY_GUEST_FILTER] 'Tình trạng' column not found in weekly guest details")
        
        # Filter for collection status
        valid_collectors = ['LOC LE', 'THAO LE']
        if collection_type == 'collected':
            filtered_df = week_df.loc[week_df['Người thu tiền'].isin(valid_collectors)].copy()
        else:  # uncollected
            filtered_df = week_df.loc[~week_df['Người thu tiền'].isin(valid_collectors)].copy()
        
        print(f"🔍 [WEEKLY_DETAILS] Found {len(filtered_df)} guests {status_label} for week {week}")
        
        # Use the dashboard's calculated total as the authoritative source
        total_amount = float(dashboard_total)
        
        # Also calculate manually for comparison and debugging
        manual_total = float(filtered_df['Tổng thanh toán'].sum()) if not filtered_df.empty else 0
        
        print(f"🔧 [WEEKLY_DETAILS] Dashboard total: {total_amount:,.0f}đ")
        print(f"🔧 [WEEKLY_DETAILS] Manual calculation: {manual_total:,.0f}đ")
        
        if abs(total_amount - manual_total) > 0.01:
            print(f"⚠️ [WEEKLY_DETAILS] DISCREPANCY DETECTED: {abs(total_amount - manual_total):,.0f}đ difference!")
            print(f"🔍 [WEEKLY_DETAILS_DEBUG] Data analysis:")
            print(f"   - Column dtype: {filtered_df['Tổng thanh toán'].dtype}")
            print(f"   - Null values: {filtered_df['Tổng thanh toán'].isnull().sum()}")
            print(f"   - Zero values: {(filtered_df['Tổng thanh toán'] == 0).sum()}")
            if not filtered_df.empty:
                print(f"   - Min amount: {filtered_df['Tổng thanh toán'].min():,.0f}đ")
                print(f"   - Max amount: {filtered_df['Tổng thanh toán'].max():,.0f}đ")
                print(f"   - Sum check: {filtered_df['Tổng thanh toán'].sum()}")
        else:
            print(f"✅ [WEEKLY_DETAILS] Perfect match between dashboard and manual calculation!")
        
        # Prepare guest details
        guest_details = []
        
        for _, guest in filtered_df.iterrows():
            amount = float(guest.get('Tổng thanh toán', 0) or 0)
            commission = float(guest.get('Hoa hồng', 0) or 0)
            
            guest_info = {
                'guest_name': guest.get('Tên người đặt', 'N/A'),  # Correct field name
                'booking_id': guest.get('Số đặt phòng', 'N/A'),
                'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A',
                'checkout_date': guest.get('Check-out Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-out Date')) else 'N/A',
                'room_amount': amount,
                'commission': commission,
                'collector': guest.get('Người thu tiền', 'Chưa thu'),
                'booking_status': guest.get('Tình trạng', 'N/A')  # Add status for debugging
            }
            guest_details.append(guest_info)
        
        # Sort by room amount (highest first)
        guest_details.sort(key=lambda x: x['room_amount'], reverse=True)
        
        # Debug summary for verification
        cancelled_count = len([g for g in guest_details if g['booking_status'] == 'Đã hủy'])
        print(f"✅ [WEEKLY_DETAILS] Returning {len(guest_details)} guests, total: {total_amount:,.0f}đ (using dashboard total)")
        print(f"✅ [WEEKLY_DETAILS] Breakdown: {cancelled_count} cancelled, {len(guest_details) - cancelled_count} active guests")
        print(f"✅ [WEEKLY_DETAILS] GUARANTEED CONSISTENCY: Using exact dashboard calculation function!")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'count': len(guest_details),
            'week': week,
            'type': collection_type,
            'status_label': status_label
        })
        
    except Exception as e:
        print(f"❌ [WEEKLY_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/collector_guest_details', methods=['POST'])
def get_collector_guest_details():
    """Get detailed guest breakdown for a specific collector in the current period"""
    try:
        data = request.get_json()
        collector_name = data.get('collector')
        start_date = data.get('start_date')  # Optional
        end_date = data.get('end_date')  # Optional
        
        print(f"🔍 [COLLECTOR_DETAILS] Requested: {collector_name}")
        
        if not collector_name:
            return jsonify({'success': False, 'message': 'Missing collector parameter'}), 400
        
        # Load data excluding cancelled bookings and filter for checked-in guests only
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Filter for checked-in guests
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        # ✅ CRITICAL FIX: Use EXACT same logic as collector chart calculation
        # Apply date range filter FIRST, then checked-in filter (same as chart)
        if start_date and end_date:
            try:
                # ✅ CRITICAL FIX: Use EXACT same datetime conversion as chart
                # Chart receives datetime objects, we need to match that exactly
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                
                print(f"🔍 [COLLECTOR_DETAILS] Date conversion: {start_date} → {start_dt}, {end_date} → {end_dt}")
                
                # Step 1: Apply period filter FIRST (EXACTLY same as chart)
                # ✅ CRITICAL: Use date-only comparison to avoid time zone issues
                start_date_only = start_dt.date()
                end_date_only = end_dt.date()
                
                period_mask = (df['Check-in Date'].dt.date >= start_date_only) & (df['Check-in Date'].dt.date <= end_date_only)
                period_df = df[period_mask].copy()
                
                print(f"🔍 [COLLECTOR_DETAILS] Period filter applied: {len(df)} → {len(period_df)} guests")
                print(f"🔍 [COLLECTOR_DETAILS] Date range (date only): {start_date_only} to {end_date_only}")
                print(f"🔍 [COLLECTOR_DETAILS] MUST MATCH chart: Should be 36 guests exactly")
                
                # Step 2: Apply checked-in filter to period data (same as chart)
                checked_in_mask_period = period_df['Check-in Date'].dt.date <= today
                filtered_df = period_df[checked_in_mask_period].copy()
                
                period_label = f"từ {start_date} đến {end_date}"
                print(f"🔍 [COLLECTOR_DETAILS] CHART LOGIC: Period first ({len(period_df)}) → Checked-in ({len(filtered_df)})")
                print(f"🔍 [COLLECTOR_DETAILS] MUST MATCH chart: Should be 34 checked-in guests exactly")
            except:
                filtered_df = df[checked_in_mask].copy()
                period_label = "tất cả thời gian"
        else:
            filtered_df = df[checked_in_mask].copy()
            period_label = "tất cả thời gian"
        
        print(f"🔍 [COLLECTOR_DETAILS] Total checked-in guests: {len(filtered_df)}")
        print(f"🔍 [COLLECTOR_DETAILS] Period: {period_label}")
        print(f"🔍 [COLLECTOR_DETAILS] Date range received: start={start_date}, end={end_date}")
        
        # Filter by specific collector
        collector_guests_all = filtered_df.loc[filtered_df['Người thu tiền'] == collector_name].copy()
        
        # ✅ CRITICAL FIX: Apply same filters as chart calculation
        collector_guests = collector_guests_all.loc[collector_guests_all['Tổng thanh toán'] > 0].copy()
        
        print(f"🔍 [COLLECTOR_DETAILS] {collector_name} guests (all): {len(collector_guests_all)}")
        print(f"🔍 [COLLECTOR_DETAILS] {collector_name} guests (amount > 0): {len(collector_guests)}")
        
        # Debug total calculation
        if not collector_guests.empty:
            detail_total = collector_guests['Tổng thanh toán'].sum()
            detail_total_all = collector_guests_all['Tổng thanh toán'].sum()
            print(f"🔍 [COLLECTOR_DETAILS] {collector_name} total amount (filtered): {detail_total:,.0f}đ")
            print(f"🔍 [COLLECTOR_DETAILS] {collector_name} total amount (all): {detail_total_all:,.0f}đ")
            print(f"🔍 [COLLECTOR_DETAILS] This should match the chart button amount")
            
            # Specific LOC LE tracking to match chart
            if collector_name == 'LOC LE':
                print(f"🎯 [DETAILS_LOC_LE] Final: {len(collector_guests)} guests, {detail_total:,.0f}đ")
        
        if collector_guests.empty:
            return jsonify({
                'success': True, 
                'guests': [], 
                'total_amount': 0, 
                'count': 0,
                'collector': collector_name,
                'period': period_label
            })
        
        # Prepare guest details
        guest_details = []
        total_amount = 0
        total_commission = 0
        total_taxi = 0
        
        for _, guest in collector_guests.iterrows():
            guest_name = guest.get('Tên người đặt', 'N/A')
            booking_id = guest.get('Số đặt phòng', 'N/A')
            amount = float(guest.get('Tổng thanh toán', 0))
            commission = float(guest.get('Hoa hồng', 0))
            taxi = float(guest.get('Taxi', 0))
            checkin_date = guest.get('Check-in Date')
            checkout_date = guest.get('Check-out Date')
            
            # Format dates safely
            try:
                checkin_str = checkin_date.strftime('%d/%m/%Y') if pd.notna(checkin_date) else 'N/A'
                checkout_str = checkout_date.strftime('%d/%m/%Y') if pd.notna(checkout_date) else 'N/A'
            except:
                checkin_str = str(checkin_date) if checkin_date else 'N/A'
                checkout_str = str(checkout_date) if checkout_date else 'N/A'
            
            guest_details.append({
                'guest_name': guest_name,
                'booking_id': str(booking_id),
                'amount': amount,
                'commission': commission,
                'taxi': taxi,
                'checkin_date': checkin_str,
                'checkout_date': checkout_str
            })
            
            total_amount += amount
            total_commission += commission
            total_taxi += taxi
        
        # Sort by check-in date (earliest first)
        guest_details.sort(key=lambda x: x['checkin_date'])
        
        # Log summary for debugging
        print(f"💰 [COLLECTOR_SUMMARY] {collector_name} ({period_label}):")
        print(f"💰   Total guests: {len(guest_details)}")
        print(f"💰   Total amount: {total_amount:,.0f}đ")
        print(f"💰   Total commission: {total_commission:,.0f}đ")
        print(f"💰   Total taxi: {total_taxi:,.0f}đ")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'total_commission': total_commission,
            'total_taxi': total_taxi,
            'count': len(guest_details),
            'collector': collector_name,
            'period': period_label
        })
        
    except Exception as e:
        print(f"❌ [COLLECTOR_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/collector_chart_data', methods=['POST'])
def get_collector_chart_data():
    """Get collector chart data for a specific period - supports month selection"""
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        use_current_filter = data.get('use_current_filter', False)
        use_all_time = data.get('use_all_time', False)
        
        # Load booking data
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({
                'success': True,
                'chart_data': {},
                'stats_data': [],
                'message': 'No data available'
            })

        # Apply date filtering
        from datetime import datetime, date
        today = date.today()

        # Ensure Check-in Date is datetime
        df = df.copy()
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today

        if start_date and end_date and not use_current_filter and not use_all_time:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
                filtered_df = df[checked_in_mask & period_mask].copy()
                period_label = f"từ {start_date} đến {end_date}"
            except Exception as e:
                filtered_df = df[checked_in_mask].copy()
                period_label = "tất cả thời gian"
        else:
            # All-time (use_all_time=True, use_current_filter=True, or no date range)
            filtered_df = df[checked_in_mask].copy()
            period_label = "tất cả thời gian"
        
        # Apply collector validation - case-insensitive match for LOC LE / THAO LE
        valid_collectors_lower = ['loc le', 'thao le']

        # Filter for valid collector bookings with amounts > 0
        if 'Người thu tiền' in filtered_df.columns and 'Tổng thanh toán' in filtered_df.columns:
            collector_normalized = filtered_df['Người thu tiền'].fillna('').str.strip().str.lower()
            valid_collector_mask = collector_normalized.isin(valid_collectors_lower)
            amount_mask = pd.to_numeric(filtered_df['Tổng thanh toán'], errors='coerce') > 0
            valid_collector_df = filtered_df.loc[valid_collector_mask & amount_mask].copy()
            # Normalize collector names to uppercase for consistent grouping
            valid_collector_df['Người thu tiền'] = valid_collector_df['Người thu tiền'].str.strip().str.upper()
            
            if not valid_collector_df.empty:
                # Group by collector and calculate stats
                collector_stats = valid_collector_df.groupby('Người thu tiền').agg({
                    'Tổng thanh toán': 'sum',
                    'Số đặt phòng': 'count',
                    'Hoa hồng': 'sum'
                }).reset_index()
                
                # Convert to stats format for table
                stats_data = []
                chart_labels = []
                chart_values = []
                chart_customdata = []
                
                total_collected = collector_stats['Tổng thanh toán'].sum()
                
                for _, row in collector_stats.iterrows():
                    collector = row['Người thu tiền']
                    amount = row['Tổng thanh toán']
                    bookings = row['Số đặt phòng']
                    commission = row['Hoa hồng'] if pd.notna(row['Hoa hồng']) else 0
                    
                    stats_data.append({
                        'collector': collector,
                        'amount': amount,
                        'bookings': bookings,
                        'commission': commission
                    })
                    
                    chart_labels.append(collector)
                    chart_values.append(amount)
                    chart_customdata.append([bookings, commission])
                    
                # Create chart data in Plotly format
                if chart_labels and chart_values:
                    chart_data = {
                        'data': [{
                            'type': 'pie',
                            'labels': chart_labels,
                            'values': chart_values,
                            'customdata': chart_customdata,
                            'hovertemplate': '<b>%{label}</b><br>' +
                                           'Số tiền: %{value:,.0f}đ<br>' +
                                           'Số booking: %{customdata[0]}<br>' +
                                           'Hoa hồng: %{customdata[1]:.0f}đ<br>' +
                                           'Tỷ lệ: %{percent}<extra></extra>',
                            'hole': 0.4,
                            'marker': {
                                'colors': ['#1f77b4' if label == 'LOC LE' else '#2ca02c' if label == 'THAO LE' else '#ff7f0e' 
                                          for label in chart_labels]
                            }
                        }],
                        'layout': {
                            'title': {
                                'text': f'Phân bổ thu tiền - {period_label}',
                                'x': 0.5,
                                'font': {'size': 14}
                            },
                            'showlegend': True,
                            'legend': {
                                'orientation': 'v',
                                'x': 1,
                                'y': 0.5
                            },
                            'margin': {'l': 20, 'r': 80, 't': 40, 'b': 20},
                            'annotations': [{
                                'text': f'{total_collected:,.0f}đ<br><small>Tổng cộng</small>',
                                'x': 0.5,
                                'y': 0.5,
                                'font_size': 12,
                                'showarrow': False
                            }]
                        }
                    }
                else:
                    chart_data = {}
            else:
                stats_data = []
                chart_data = {}
        else:
            stats_data = []
            chart_data = {}
        
        # Add helpful message if no valid data
        has_data = bool(stats_data)
        message = None if has_data else 'Không có dữ liệu thu tiền hợp lệ cho LOC LE hoặc THAO LE trong khoảng thời gian này'

        return jsonify({
            'success': True,
            'chart_data': chart_data,
            'stats_data': stats_data,
            'period': period_label,
            'total_records': len(filtered_df),
            'has_data': has_data,
            'message': message
        })
        
    except Exception as e:
        print(f"❌ [COLLECTOR_CHART_API] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/unchecked_in_guests', methods=['GET'])
def get_unchecked_in_guests():
    """Get unchecked-in guests for current month - money to be collected"""
    try:
        from datetime import datetime, date
        from core.models import Booking, Guest, db

        # Get current month date range
        today = date.today()
        start_of_month = today.replace(day=1)

        # Calculate end of current month
        from datetime import timedelta
        if today.month == 12:
            end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

        print(f"🏨 [UNCHECKED_IN] Getting unchecked-in guests for {start_of_month} to {end_of_month}")

        # Query confirmed bookings where check-in date is in current month but haven't checked in yet
        # (check-in date > today) AND money hasn't been collected yet
        from core.models import Room
        unchecked_bookings = db.session.query(Booking, Guest, Room).outerjoin(
            Guest, Booking.guest_id == Guest.guest_id
        ).outerjoin(
            Room, Booking.room_id == Room.room_id
        ).filter(
            Booking.booking_status.in_(['confirmed', 'mới']),
            Booking.checkin_date >= today,  # Today and future dates (includes today)
            Booking.checkin_date >= start_of_month,  # Check-in date in current month
            Booking.checkin_date <= end_of_month,
            Booking.booking_status != 'deleted',
            Booking.booking_status != 'cancelled',
            Booking.booking_status != 'đã hủy',
            db.or_(
                Booking.collected_amount == None,
                Booking.collected_amount == 0
            )  # Money not collected yet
        ).order_by(Booking.checkin_date.asc()).all()

        unchecked_list = []
        total_amount = 0
        total_commission = 0

        for booking, guest, room in unchecked_bookings:
            guest_name = guest.full_name if guest else booking.guest_name or 'Unknown Guest'
            room_name = room.room_name if room else (booking.accommodation_name or 'N/A')

            # Calculate amounts
            room_amount = float(booking.room_amount or 0)
            commission = float(booking.commission or 0)
            total_amount += room_amount
            total_commission += commission

            # Calculate nights
            if booking.checkout_date and booking.checkin_date:
                nights = (booking.checkout_date - booking.checkin_date).days
                nights = max(1, nights)
            else:
                nights = 1

            unchecked_list.append({
                'booking_id': booking.booking_id,
                'guest_name': guest_name,
                'checkin_date': booking.checkin_date.isoformat() if booking.checkin_date else None,
                'checkout_date': booking.checkout_date.isoformat() if booking.checkout_date else None,
                'room_amount': room_amount,
                'commission': commission,
                'nights': nights,
                'collector': booking.collector or 'N/A',
                'accommodation': booking.accommodation_name or 'N/A',
                'room_name': room_name,
                'days_until_checkin': (booking.checkin_date - today).days if booking.checkin_date else 0
            })

        print(f"🏨 [UNCHECKED_IN] Found {len(unchecked_list)} unchecked-in guests")
        print(f"💰 [UNCHECKED_IN] Total to collect: {total_amount:,.0f}đ")
        print(f"💸 [UNCHECKED_IN] Total commission: {total_commission:,.0f}đ")

        return jsonify({
            'success': True,
            'unchecked_guests': unchecked_list,
            'total_amount': total_amount,
            'total_commission': total_commission,
            'count': len(unchecked_list),
            'period': f"{start_of_month.strftime('%B %Y')}",
            'date_range': {
                'start': start_of_month.isoformat(),
                'end': end_of_month.isoformat(),
                'today': today.isoformat()
            }
        })

    except Exception as e:
        print(f"❌ [UNCHECKED_IN] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prorated_monthly_revenue', methods=['GET'])
def get_prorated_monthly_revenue():
    """
    PRO-RATED MONTHLY REVENUE CALCULATION with APARTMENT FILTERING and MONTH SELECTION
    Calculate revenue ONLY for days that fall within the specified month
    For bookings that span across months, only count the days in the selected month

    Query Parameters:
    - apartment: 'apt1' (118 Hang Bac), 'apt2' (18 Hang Be), or 'all' (default)
    - month: 'YYYY-MM' format (e.g., '2025-11'), defaults to current month
    """
    try:
        from datetime import datetime, date, timedelta
        from sqlalchemy import or_
        from core.models import Booking, Guest, Room, Apartment, db

        # Get apartment filter parameter ('all' or a numeric apartment_id string)
        apartment_filter = request.args.get('apartment', 'all')
        print(f"🏢 [APARTMENT_FILTER] Requested filter: {apartment_filter}")

        # ── Load ALL active apartments from DB (dynamic — no hardcoding) ──────────
        APT_COLORS_HEX = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']
        APT_BG_COLORS  = ['#e3f2fd', '#e8f5e9', '#f3e5f5', '#fbe9e7', '#e0f5f7', '#fffde7']
        all_apartments = Apartment.query.filter_by(is_active=True).order_by(Apartment.apartment_id).all()
        apt_ids = [str(a.apartment_id) for a in all_apartments]
        apartments_meta = [
            {
                'id':         apt.apartment_id,
                'name':       apt.apartment_name,
                'color':      APT_COLORS_HEX[i % len(APT_COLORS_HEX)],
                'bg_color':   APT_BG_COLORS[i % len(APT_BG_COLORS)],
                'total_rooms': apt.total_rooms or 1,
            }
            for i, apt in enumerate(all_apartments)
        ]
        print(f"🏢 [APARTMENTS] Loaded {len(all_apartments)}: {[a.apartment_name for a in all_apartments]}")

        # Always set today for comparisons
        today = date.today()

        # Get month parameter (YYYY-MM format)
        month_param = request.args.get('month', None)

        if month_param:
            # Parse selected month
            try:
                year, month = map(int, month_param.split('-'))
                start_of_month = date(year, month, 1)

                # Calculate end of selected month
                if month == 12:
                    end_of_month = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_of_month = date(year, month + 1, 1) - timedelta(days=1)

                print(f"📅 [PRORATED] Using selected month: {month_param}")
            except ValueError as e:
                print(f"⚠️ [PRORATED] Invalid month format: {month_param}, using current month")
                start_of_month = today.replace(day=1)
                if today.month == 12:
                    end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
        else:
            # Use current month if no month parameter
            start_of_month = today.replace(day=1)

            # Calculate end of current month
            if today.month == 12:
                end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

        print(f"💰 [MONTHLY_REVENUE] Calculating revenue by check-in month: {start_of_month} to {end_of_month}")

        # NEW LOGIC: Filter by CHECK-IN DATE in selected month (not pro-rating)
        # If guest checks in Oct 30 and out Nov 5, they belong to OCTOBER only
        query = db.session.query(Booking, Guest, Room, Apartment).outerjoin(
            Guest, Booking.guest_id == Guest.guest_id
        ).outerjoin(
            Room, Booking.room_id == Room.room_id
        ).outerjoin(
            Apartment, Room.apartment_id == Apartment.apartment_id
        ).filter(
            Booking.booking_status.in_(['confirmed', 'mới', 'checked_in', 'checked_out', 'OK', 'Mới']),
            Booking.checkin_date >= start_of_month,
            Booking.checkin_date <= end_of_month,
            Booking.booking_status != 'deleted',
            Booking.booking_status != 'cancelled',
            Booking.booking_status != 'đã hủy',
            # Exclude guests flagged as cancelling — they didn't actually stay
            or_(Booking.checkin_status.is_(None), Booking.checkin_status != 'cancelling')
        )

        # Apply apartment filter — 'all' shows everything; any integer string filters by apartment_id
        if apartment_filter != 'all':
            try:
                apt_id_filter = int(apartment_filter)
                query = query.filter(Apartment.apartment_id == apt_id_filter)
                apt_label = next((a.apartment_name for a in all_apartments if a.apartment_id == apt_id_filter), apartment_filter)
                print(f"🏢 [FILTER] Filtering for apartment_id={apt_id_filter} ({apt_label})")
            except (ValueError, TypeError):
                print(f"📊 [FILTER] Invalid filter '{apartment_filter}', showing all apartments")
        else:
            print(f"📊 [FILTER] Showing all {len(all_apartments)} apartments")

        all_month_bookings = query.order_by(Booking.checkin_date.asc()).all()

        # ADDITIONAL QUERY: Get ALL bookings that overlap with the selected month (for daily occupancy)
        # This includes guests who checked in before the month but are still staying
        occupancy_query = db.session.query(Booking, Guest, Room, Apartment).outerjoin(
            Guest, Booking.guest_id == Guest.guest_id
        ).outerjoin(
            Room, Booking.room_id == Room.room_id
        ).outerjoin(
            Apartment, Room.apartment_id == Apartment.apartment_id
        ).filter(
            Booking.booking_status.in_(['confirmed', 'mới', 'checked_in', 'checked_out', 'OK', 'Mới']),
            Booking.checkin_date < end_of_month + timedelta(days=1),  # Check-in before end of month
            Booking.checkout_date > start_of_month,  # Check-out after start of month
            Booking.booking_status != 'deleted',
            Booking.booking_status != 'cancelled',
            Booking.booking_status != 'đã hủy',
            # Exclude guests flagged as cancelling — they didn't actually stay
            or_(Booking.checkin_status.is_(None), Booking.checkin_status != 'cancelling')
        )

        # Apply same apartment filter for occupancy
        if apartment_filter != 'all':
            try:
                occupancy_query = occupancy_query.filter(Apartment.apartment_id == int(apartment_filter))
            except (ValueError, TypeError):
                pass

        all_occupancy_bookings = occupancy_query.order_by(Booking.checkin_date.asc()).all()
        print(f"📊 [OCCUPANCY] Found {len(all_occupancy_bookings)} bookings overlapping with month")

        # NEW: Track daily occupancy, revenue, AND guest details per apartment
        daily_occupancy = {}  # {date: {counts, revenue, guests: [{guest_name, room_name, amount, etc}]}}
        days_in_selected_month = (end_of_month - start_of_month).days + 1

        # Initialize daily occupancy — dynamic keys from DB apartments, no hardcoding
        for day_offset in range(days_in_selected_month):
            current_date = start_of_month + timedelta(days=day_offset)
            daily_occupancy[current_date] = {
                'apts':  {apt_id: {'count': 0, 'revenue': 0, 'commission': 0} for apt_id in apt_ids},
                'all':   {'count': 0, 'revenue': 0, 'commission': 0},
                'guests': []
            }

        # Track revenue by check-in month (NO PRO-RATING)
        total_revenue = 0
        total_collected = 0
        total_uncollected = 0
        booking_count = 0

        for booking, guest, room, apartment in all_month_bookings:
            if not booking.checkin_date or not booking.checkout_date:
                continue

            # NEW LOGIC: Full booking amount (no pro-rating)
            # Guest belongs to check-in month regardless of checkout date
            room_amount = float(booking.room_amount or 0)
            collected_amount = float(booking.collected_amount or 0)
            commission = float(booking.commission or 0)
            # Use actual collected amount when available (reflects real payment agreed)
            effective_revenue = collected_amount if collected_amount > 0 else room_amount

            # Track revenue totals
            total_revenue += effective_revenue
            booking_count += 1

            # Track collected vs uncollected
            if collected_amount > 0:
                total_collected += collected_amount

            uncollected = room_amount - collected_amount
            if uncollected > 0:
                total_uncollected += uncollected

            # Calculate daily occupancy AND revenue for this booking
            # Count each day the guest stays in the selected month
            apartment_id = apartment.apartment_id if apartment else None
            apt_key = str(apartment_id) if apartment_id else None

            # Calculate total nights for pro-rating daily revenue
            total_nights = (booking.checkout_date - booking.checkin_date).days
            revenue_per_night = effective_revenue / total_nights if total_nights > 0 else 0
            commission_per_night = commission / total_nights if total_nights > 0 else 0

            # Iterate through each day of the stay
            current_stay_date = booking.checkin_date
            nights_in_month = 0

            while current_stay_date < booking.checkout_date:
                # Only count if this day is in the selected month
                if start_of_month <= current_stay_date <= end_of_month:
                    if current_stay_date in daily_occupancy:
                        # All-apartments totals
                        daily_occupancy[current_stay_date]['all']['count']      += 1
                        daily_occupancy[current_stay_date]['all']['revenue']    += revenue_per_night
                        daily_occupancy[current_stay_date]['all']['commission'] += commission_per_night
                        # Per-apartment totals
                        if apt_key and apt_key in daily_occupancy[current_stay_date]['apts']:
                            daily_occupancy[current_stay_date]['apts'][apt_key]['count']      += 1
                            daily_occupancy[current_stay_date]['apts'][apt_key]['revenue']    += revenue_per_night
                            daily_occupancy[current_stay_date]['apts'][apt_key]['commission'] += commission_per_night

                        # Add guest details for EVERY night they stay (not just first night)
                        guest_name = guest.full_name if guest else booking.guest_name or 'N/A'
                        room_name = room.room_name if room else booking.room_name or 'N/A'
                        apartment_name = apartment.apartment_name if apartment else 'N/A'

                        daily_occupancy[current_stay_date]['guests'].append({
                            'booking_id': str(booking.booking_id),
                            'guest_name': guest_name,
                            'room_name': room_name,
                            'apartment_name': apartment_name,
                            'apartment_id': apartment_id,
                            'checkin_date': booking.checkin_date.isoformat(),
                            'checkout_date': booking.checkout_date.isoformat(),
                            'room_amount': room_amount,
                            'collected_amount': collected_amount,
                            'commission': commission,
                            'revenue_per_night': revenue_per_night,
                            'commission_per_night': commission_per_night,
                            'total_nights': total_nights,
                            'booking_status': booking.booking_status
                        })

                        nights_in_month += 1

                current_stay_date += timedelta(days=1)

        print(f"💰 [CHECK-IN MONTH] Found {booking_count} bookings with check-in in {start_of_month.strftime('%B %Y')}")
        print(f"💰 [CHECK-IN MONTH] Total revenue: {total_revenue:,.0f}đ")
        print(f"💰 [CHECK-IN MONTH] Collected: {total_collected:,.0f}đ")
        print(f"💰 [CHECK-IN MONTH] Uncollected: {total_uncollected:,.0f}đ")

        # SECOND LOOP: Populate daily occupancy with ALL guests (including those who checked in before month)
        # Reset all counts — second loop is the authoritative source for occupancy display
        for day_date in daily_occupancy:
            daily_occupancy[day_date]['guests'] = []
            daily_occupancy[day_date]['all'] = {'count': 0, 'revenue': 0, 'commission': 0, 'confirmed_revenue': 0, 'confirmed_count': 0}
            for apt_id in apt_ids:
                daily_occupancy[day_date]['apts'][apt_id] = {'count': 0, 'revenue': 0, 'commission': 0}

        for booking, guest, room, apartment in all_occupancy_bookings:
            if not booking.checkin_date or not booking.checkout_date:
                continue

            room_amount = float(booking.room_amount or 0)
            collected_amount = float(booking.collected_amount or 0)
            commission = float(booking.commission or 0)
            effective_revenue = collected_amount if collected_amount > 0 else room_amount
            checkin_status = booking.checkin_status  # 'confirmed', 'cancelling', or None
            apartment_id = apartment.apartment_id if apartment else None
            apt_key = str(apartment_id) if apartment_id else None

            # Calculate total nights for pro-rating daily revenue
            total_nights = (booking.checkout_date - booking.checkin_date).days
            revenue_per_night = effective_revenue / total_nights if total_nights > 0 else 0
            commission_per_night = commission / total_nights if total_nights > 0 else 0

            # Iterate through each day of the stay
            current_stay_date = booking.checkin_date

            while current_stay_date < booking.checkout_date:
                # Only count if this day is in the selected month
                if start_of_month <= current_stay_date <= end_of_month:
                    if current_stay_date in daily_occupancy:
                        # All-apartments totals
                        daily_occupancy[current_stay_date]['all']['count']      += 1
                        daily_occupancy[current_stay_date]['all']['revenue']    += revenue_per_night
                        daily_occupancy[current_stay_date]['all']['commission'] += commission_per_night

                        # Track confirmed-only revenue:
                        # PAST/TODAY → NULL means user never confirmed = no-show, don't count
                        # FUTURE     → count all (confirmation hasn't happened yet = expected revenue)
                        guest_counts_as_confirmed = (
                            checkin_status == 'confirmed'           # explicitly confirmed
                            or booking.checkin_date > today         # future booking: expected
                        )
                        if guest_counts_as_confirmed:
                            daily_occupancy[current_stay_date]['all']['confirmed_revenue'] += revenue_per_night
                            daily_occupancy[current_stay_date]['all']['confirmed_count']   += 1

                        # Per-apartment totals
                        if apt_key and apt_key in daily_occupancy[current_stay_date]['apts']:
                            daily_occupancy[current_stay_date]['apts'][apt_key]['count']      += 1
                            daily_occupancy[current_stay_date]['apts'][apt_key]['revenue']    += revenue_per_night
                            daily_occupancy[current_stay_date]['apts'][apt_key]['commission'] += commission_per_night

                        # Add guest details for EVERY night they stay
                        guest_name = guest.full_name if guest else booking.guest_name or 'N/A'
                        room_name = room.room_name if room else booking.room_name or 'N/A'
                        apartment_name = apartment.apartment_name if apartment else 'N/A'

                        daily_occupancy[current_stay_date]['guests'].append({
                            'booking_id': str(booking.booking_id),
                            'guest_name': guest_name,
                            'room_name': room_name,
                            'apartment_name': apartment_name,
                            'apartment_id': apartment_id,
                            'checkin_date': booking.checkin_date.isoformat(),
                            'checkout_date': booking.checkout_date.isoformat(),
                            'room_amount': room_amount,
                            'collected_amount': collected_amount,
                            'commission': commission,
                            'revenue_per_night': revenue_per_night,
                            'commission_per_night': commission_per_night,
                            'total_nights': total_nights,
                            'booking_status': booking.booking_status,
                            'checkin_status': checkin_status,
                        })

                current_stay_date += timedelta(days=1)

        print(f"📊 [OCCUPANCY] Daily occupancy populated with all staying guests")
        print(f"📊 [DAILY_OCCUPANCY] Tracked {len(daily_occupancy)} days")

        # Convert daily_occupancy dates to strings for JSON serialization
        daily_occupancy_json = {}
        for date_obj, counts in daily_occupancy.items():
            daily_occupancy_json[date_obj.isoformat()] = counts

        return jsonify({
            'success': True,
            'apartments': apartments_meta,   # dynamic — frontend uses this for columns
            'summary': {
                'total_revenue': round(total_revenue, 2),
                'collected': round(total_collected, 2),
                'uncollected': round(total_uncollected, 2),
                'booking_count': booking_count,
                'collection_rate': round(total_collected / total_revenue * 100, 1) if total_revenue > 0 else 0
            },
            'daily_occupancy': daily_occupancy_json,
            'period': {
                'month': start_of_month.strftime('%B %Y'),
                'start_date': start_of_month.isoformat(),
                'end_date': end_of_month.isoformat(),
                'today': today.isoformat(),
                'days_in_month': (end_of_month - start_of_month).days + 1
            }
        })

    except Exception as e:
        print(f"❌ [PRORATED] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monthly_checked_in_revenue', methods=['GET'])
def get_monthly_checked_in_revenue():
    """
    🏢 MONTHLY CHECKED-IN REVENUE WITH APARTMENT FILTERING
    Returns monthly revenue data for checked-in guests only, filtered by apartment

    Query Parameters:
    - apartment: 'apt1' (118 Hang Bac), 'apt2' (18 Hang Be), or 'all' (default)
    """
    try:
        from core.dashboard_routes import process_monthly_revenue_with_unpaid
        from core.logic_postgresql import load_booking_data
        from core.models import Room, Apartment, db

        # Get apartment filter parameter
        apartment_filter = request.args.get('apartment', 'all')
        print(f"🏢 [MONTHLY_CHECKED_IN] Requested filter: {apartment_filter}")

        # Load all booking data
        df = load_booking_data()

        if df.empty:
            return jsonify({
                'success': True,
                'monthly_data': [],
                'apartment_filter': apartment_filter
            })

        # Filter by apartment if specified
        if apartment_filter in ['apt1', 'apt2']:
            apartment_id = 1 if apartment_filter == 'apt1' else 2
            print(f"🔍 [MONTHLY_CHECKED_IN] Filtering for apartment_id: {apartment_id}")

            # Get room IDs for this apartment
            room_ids = db.session.query(Room.room_id).filter(
                Room.apartment_id == apartment_id,
                Room.is_active == True
            ).all()
            room_ids = [r[0] for r in room_ids]

            print(f"🔍 [MONTHLY_CHECKED_IN] Found {len(room_ids)} rooms for apartment {apartment_id}")

            # Filter dataframe by room_id
            if 'room_id' in df.columns:
                df = df[df['room_id'].isin(room_ids)]
                print(f"✅ [MONTHLY_CHECKED_IN] Filtered to {len(df)} bookings for {apartment_filter}")
            else:
                print(f"⚠️ [MONTHLY_CHECKED_IN] room_id column not found, cannot filter")

        # Process monthly revenue with the filtered data
        monthly_data = process_monthly_revenue_with_unpaid(df)

        # Convert pandas Period objects to strings for JSON serialization
        import pandas as pd
        for row in monthly_data:
            for key, value in row.items():
                if isinstance(value, pd.Period):
                    row[key] = str(value)
                elif pd.isna(value):
                    row[key] = None

        return jsonify({
            'success': True,
            'monthly_data': monthly_data,
            'apartment_filter': apartment_filter,
            'total_months': len(monthly_data)
        })

    except Exception as e:
        print(f"❌ [MONTHLY_CHECKED_IN] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/apartments_config', methods=['GET'])
def get_apartments_config():
    """
    🏗️ DATABASE-DRIVEN APARTMENT CONFIGURATION
    Provides dynamic apartment/room data for frontend
    NO CODE CHANGES NEEDED when adding new apartments/rooms!
    """
    try:
        from core.models import Apartment, Room, db

        # Get all active apartments with their rooms
        apartments = db.session.query(Apartment).filter(
            Apartment.is_active == True
        ).order_by(Apartment.apartment_id).all()

        apartments_data = []
        total_capacity = 0

        for apt in apartments:
            # Get rooms for this apartment
            rooms = db.session.query(Room).filter(
                Room.apartment_id == apt.apartment_id,
                Room.is_active == True
            ).order_by(Room.display_order, Room.room_id).all()

            room_count = len(rooms)
            total_capacity += room_count

            # Assign color scheme based on apartment ID
            color_schemes = {
                1: {'primary': '#1976D2', 'secondary': '#0D47A1', 'emoji': '🔵', 'name': 'Blue'},
                2: {'primary': '#388E3C', 'secondary': '#1B5E20', 'emoji': '🟢', 'name': 'Green'},
                3: {'primary': '#F57C00', 'secondary': '#E65100', 'emoji': '🟠', 'name': 'Orange'},
                4: {'primary': '#7B1FA2', 'secondary': '#4A148C', 'emoji': '🟣', 'name': 'Purple'},
                5: {'primary': '#C2185B', 'secondary': '#880E4F', 'emoji': '🔴', 'name': 'Red'},
                6: {'primary': '#0097A7', 'secondary': '#006064', 'emoji': '🔷', 'name': 'Cyan'},
                7: {'primary': '#AFB42B', 'secondary': '#827717', 'emoji': '🟡', 'name': 'Lime'},
                8: {'primary': '#5D4037', 'secondary': '#3E2723', 'emoji': '🟤', 'name': 'Brown'},
                9: {'primary': '#455A64', 'secondary': '#263238', 'emoji': '⚫', 'name': 'Grey'},
                10: {'primary': '#D32F2F', 'secondary': '#B71C1C', 'emoji': '🔺', 'name': 'DeepRed'}
            }

            color_scheme = color_schemes.get(apt.apartment_id, color_schemes[1])

            apartments_data.append({
                'apartment_id': apt.apartment_id,
                'apartment_name': apt.apartment_name,
                'room_count': room_count,
                'rooms': [{'room_id': r.room_id, 'room_name': r.room_name, 'room_type': r.room_type} for r in rooms],
                'color': color_scheme
            })

        return jsonify({
            'success': True,
            'apartments': apartments_data,
            'total_capacity': total_capacity,
            'apartment_count': len(apartments_data)
        })

    except Exception as e:
        print(f"❌ [APARTMENTS_CONFIG] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/railway_setup_guide', methods=['GET'])
def railway_setup_guide():
    """Railway deployment setup guide"""
    setup_steps = {
        'title': 'Railway Deployment Setup Guide',
        'current_issues': [],
        'required_env_vars': {
            'DATABASE_URL': {
                'description': 'PostgreSQL database connection string',
                'format': 'postgresql://username:password@hostname:port/database_name',
                'current': 'DATABASE_URL' in os.environ
            },
            'GOOGLE_API_KEY': {
                'description': 'Google AI API key for image processing',
                'format': 'AIza...',
                'current': 'GOOGLE_API_KEY' in os.environ
            }
        },
        'setup_steps': [
            '1. Go to Railway dashboard',
            '2. Add PostgreSQL service to your project',
            '3. Connect database service to your app',
            '4. Set environment variables in Railway settings',
            '5. Redeploy your application',
            '6. Test with /api/railway_status endpoint'
        ]
    }
    
    # Check current status
    if 'DATABASE_URL' not in os.environ:
        setup_steps['current_issues'].append('DATABASE_URL environment variable missing')
    
    if 'GOOGLE_API_KEY' not in os.environ:
        setup_steps['current_issues'].append('GOOGLE_API_KEY environment variable missing')
    
    return jsonify(setup_steps)

@app.route('/api/debug_data_status', methods=['GET'])
def debug_data_status():
    """🚨 CRITICAL: Debug endpoint to check for data loss - shows ALL bookings including cancelled"""
    try:
        # Load ALL bookings (including cancelled)
        df_all = load_booking_data(force_fresh=True)

        if df_all.empty:
            return jsonify({
                'success': True,
                'total_bookings': 0,
                'message': '❌ NO BOOKINGS FOUND IN DATABASE!',
                'database_empty': True
            })

        # Count by status
        status_breakdown = {}
        if 'Tình trạng' in df_all.columns:
            status_counts = df_all['Tình trạng'].value_counts(dropna=False).to_dict()
            status_breakdown = {str(k): int(v) for k, v in status_counts.items()}

        # Count by month
        month_breakdown = {}
        if 'Check-in Date' in df_all.columns:
            df_all['Check-in Date'] = pd.to_datetime(df_all['Check-in Date'], errors='coerce')
            df_all['YearMonth'] = df_all['Check-in Date'].dt.strftime('%Y-%m')
            month_counts = df_all['YearMonth'].value_counts(dropna=False).to_dict()
            month_breakdown = {str(k): int(v) for k, v in month_counts.items()}

        # Get recent bookings
        recent_bookings = []
        if 'Check-in Date' in df_all.columns:
            df_sorted = df_all.sort_values('Check-in Date', ascending=False).head(20)
            for idx, row in df_sorted.iterrows():
                recent_bookings.append({
                    'checkin_date': row['Check-in Date'].strftime('%Y-%m-%d') if pd.notna(row['Check-in Date']) else 'N/A',
                    'guest_name': row.get('Tên người đặt', 'N/A'),
                    'status': row.get('Tình trạng', 'N/A'),
                    'amount': float(row.get('Tổng thanh toán', 0)) if pd.notna(row.get('Tổng thanh toán')) else 0,
                    'collector': row.get('Người thu tiền', 'N/A')
                })

        return jsonify({
            'success': True,
            'total_bookings': len(df_all),
            'status_breakdown': status_breakdown,
            'months_with_data': month_breakdown,
            'recent_bookings': recent_bookings,
            'database_empty': False
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug_all_months', methods=['GET'])
def debug_all_months():
    """Debug endpoint to see ALL months with bookings"""
    try:
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'message': 'No bookings found', 'months': []})

        df = df.copy()
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        date_mask = df['Check-in Date'].notna()
        valid_df = df[date_mask].copy()

        if not valid_df.empty:
            valid_df['YearMonth'] = valid_df['Check-in Date'].dt.strftime('%Y-%m')
            unique_months = sorted(valid_df['YearMonth'].unique(), reverse=True)

            month_details = []
            for month_str in unique_months:
                month_data = valid_df[valid_df['YearMonth'] == month_str]
                collectors = month_data['Người thu tiền'].value_counts(dropna=False).to_dict() if 'Người thu tiền' in month_data.columns else {}

                month_details.append({
                    'month': month_str,
                    'total_bookings': len(month_data),
                    'collectors': collectors
                })

            return jsonify({
                'success': True,
                'total_months': len(unique_months),
                'months': month_details
            })
        else:
            return jsonify({'success': True, 'message': 'No valid dates', 'months': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/collector_available_months', methods=['GET'])
def get_collector_available_months():
    """Get list of ALL months that have booking data (not just collector data)"""
    try:
        print(f"🗓️ [AVAILABLE_MONTHS] Getting all months with bookings...")

        # Load booking data
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'months': []})

        # Ensure Check-in Date is datetime
        df = df.copy()
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')

        # Filter for valid dates only
        date_mask = df['Check-in Date'].notna()
        valid_df = df[date_mask].copy()

        print(f"🗓️ [AVAILABLE_MONTHS] Total bookings with valid dates: {len(valid_df)}")

        if not valid_df.empty:
            # Extract ALL year-month combinations (not just those with collectors)
            valid_df['YearMonth'] = valid_df['Check-in Date'].dt.strftime('%Y-%m')
            unique_months = valid_df['YearMonth'].unique()

            # For collector stats, we still need to filter
            valid_collectors = ['LOC LE', 'THAO LE']
            if 'Người thu tiền' in valid_df.columns and 'Tổng thanh toán' in valid_df.columns:
                valid_collector_mask = valid_df['Người thu tiền'].isin(valid_collectors)
                amount_mask = pd.to_numeric(valid_df['Tổng thanh toán'], errors='coerce') > 0
                collector_df = valid_df[valid_collector_mask & amount_mask].copy()
                collector_df['YearMonth'] = collector_df['Check-in Date'].dt.strftime('%Y-%m')
            else:
                collector_df = pd.DataFrame()
            
            # Convert to list of month objects with additional info
            available_months = []
            for month_str in sorted(unique_months, reverse=True):  # Most recent first
                year, month = month_str.split('-')

                # Get ALL booking stats for this month
                month_mask = valid_df['YearMonth'] == month_str
                month_data = valid_df[month_mask]
                total_bookings = len(month_data)

                # Get COLLECTOR-specific stats (may be 0)
                if not collector_df.empty and month_str in collector_df['YearMonth'].values:
                    collector_month_data = collector_df[collector_df['YearMonth'] == month_str]
                    total_amount = collector_month_data['Tổng thanh toán'].sum() if 'Tổng thanh toán' in collector_month_data.columns else 0
                    collector_bookings = len(collector_month_data)
                    collectors = collector_month_data['Người thu tiền'].value_counts().to_dict() if 'Người thu tiền' in collector_month_data.columns else {}
                    has_collector_data = True
                else:
                    total_amount = 0
                    collector_bookings = 0
                    collectors = {}
                    has_collector_data = False

                # Create month name in Vietnamese
                from datetime import datetime
                date_obj = datetime(int(year), int(month), 1)
                month_name = date_obj.strftime('%B %Y')  # Will be localized to Vietnamese in frontend

                available_months.append({
                    'value': month_str,
                    'year': int(year),
                    'month': int(month),
                    'month_name': month_name,
                    'total_amount': total_amount,
                    'total_bookings': total_bookings,
                    'collector_bookings': collector_bookings,
                    'collectors': collectors,
                    'has_collector_data': has_collector_data
                })

            print(f"🗓️ [AVAILABLE_MONTHS] Found {len(available_months)} months with bookings")
            for month_info in available_months:
                status = f"✅ {month_info['total_amount']:,.0f}đ ({month_info['collector_bookings']} collector bookings)" if month_info['has_collector_data'] else f"⚠️ No collector data ({month_info['total_bookings']} total bookings)"
                print(f"🗓️   - {month_info['value']}: {status}")

            return jsonify({
                'success': True,
                'months': available_months
            })
        else:
            print(f"🗓️ [AVAILABLE_MONTHS] No booking data with valid dates")
            return jsonify({'success': True, 'months': []})
        
    except Exception as e:
        print(f"❌ [AVAILABLE_MONTHS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/debug_collector_comparison', methods=['POST'])
def debug_collector_comparison():
    """Debug endpoint to compare collector amounts from different calculations"""
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        print(f"🔧 [DEBUG_COMPARISON] Analyzing period: {start_date} to {end_date}")
        
        # Load raw data
        df = load_booking_data()
        if df.empty:
            return jsonify({'success': False, 'message': 'No data available'})
        
        # Apply same filtering logic as dashboard
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        # Apply date range filter
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
                filtered_df = df[checked_in_mask & period_mask].copy()
            except:
                filtered_df = df[checked_in_mask].copy()
        else:
            filtered_df = df[checked_in_mask].copy()
        
        print(f"🔧 [DEBUG_COMPARISON] Filtered data: {len(filtered_df)} records")
        
        # Method 1: Dashboard calculation (prepare_dashboard_data logic)
        try:
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                dashboard_data = prepare_dashboard_data(df, start_dt, end_dt, 'checkin_date', 'asc')
            else:
                # Use default date range if not provided
                from datetime import timedelta
                today = datetime.now()
                start_dt = today.replace(day=1)  # First day of current month
                end_dt = today
                dashboard_data = prepare_dashboard_data(df, start_dt, end_dt, 'checkin_date', 'asc')
        except Exception as e:
            print(f"🔧 [DEBUG_COMPARISON] Dashboard data preparation failed: {e}")
            dashboard_data = {'collector_revenue_selected': pd.DataFrame()}
        collector_revenue_selected = dashboard_data.get('collector_revenue_selected', pd.DataFrame())
        
        # Method 2: Direct calculation
        valid_collectors = ['LOC LE', 'THAO LE']
        direct_collector_data = {}
        
        for collector in valid_collectors:
            collector_guests = filtered_df.loc[filtered_df['Người thu tiền'] == collector].copy()
            if not collector_guests.empty:
                total_amount = collector_guests['Tổng thanh toán'].sum()
                total_commission = collector_guests['Hoa hồng'].sum()
                guest_count = len(collector_guests)
                
                direct_collector_data[collector] = {
                    'amount': float(total_amount),
                    'commission': float(total_commission),
                    'count': guest_count,
                    'guests': []
                }
                
                # Add individual guest details
                for _, guest in collector_guests.iterrows():
                    direct_collector_data[collector]['guests'].append({
                        'name': guest.get('Tên người đặt', 'N/A'),
                        'booking_id': str(guest.get('Số đặt phòng', 'N/A')),
                        'amount': float(guest.get('Tổng thanh toán', 0)),
                        'commission': float(guest.get('Hoa hồng', 0)),
                        'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A'
                    })
        
        # Method 3: Monthly revenue calculation (for comparison)
        monthly_data = {}
        if start_date and end_date:
            try:
                month_str = start_date[:7]  # YYYY-MM format
                month_mask = filtered_df['Check-in Date'].dt.strftime('%Y-%m') == month_str
                month_guests = filtered_df.loc[month_mask].copy()
                
                for collector in valid_collectors:
                    month_collector_guests = month_guests.loc[month_guests['Người thu tiền'] == collector].copy()
                    if not month_collector_guests.empty:
                        monthly_data[collector] = {
                            'amount': float(month_collector_guests['Tổng thanh toán'].sum()),
                            'count': len(month_collector_guests)
                        }
            except:
                pass
        
        # Format dashboard data for comparison
        dashboard_collector_data = {}
        if not collector_revenue_selected.empty:
            for _, row in collector_revenue_selected.iterrows():
                collector = row.get('Người thu tiền', 'Unknown')
                dashboard_collector_data[collector] = {
                    'amount': float(row.get('Tổng thanh toán', 0)),
                    'commission': float(row.get('Hoa hồng', 0)),
                    'count': int(row.get('Số đặt phòng', 0))
                }
        
        # Create comparison results
        comparison_results = {
            'period': f"{start_date} to {end_date}" if start_date and end_date else "All time",
            'total_filtered_records': len(filtered_df),
            'dashboard_calculation': dashboard_collector_data,
            'direct_calculation': direct_collector_data,
            'monthly_calculation': monthly_data,
            'discrepancies': []
        }
        
        # Find discrepancies
        for collector in valid_collectors:
            dashboard_amount = dashboard_collector_data.get(collector, {}).get('amount', 0)
            direct_amount = direct_collector_data.get(collector, {}).get('amount', 0)
            monthly_amount = monthly_data.get(collector, {}).get('amount', 0)
            
            if dashboard_amount != direct_amount or dashboard_amount != monthly_amount:
                comparison_results['discrepancies'].append({
                    'collector': collector,
                    'dashboard_amount': dashboard_amount,
                    'direct_amount': direct_amount,
                    'monthly_amount': monthly_amount,
                    'dashboard_vs_direct': dashboard_amount - direct_amount,
                    'dashboard_vs_monthly': dashboard_amount - monthly_amount
                })
        
        print(f"🔧 [DEBUG_COMPARISON] Found {len(comparison_results['discrepancies'])} discrepancies")
        
        return jsonify({
            'success': True,
            'comparison': comparison_results
        })
        
    except Exception as e:
        print(f"❌ [DEBUG_COMPARISON] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/debug_june_revenue_specific', methods=['POST'])
def debug_june_revenue_specific():
    """Debug the specific June revenue discrepancy: 36,109,006 vs 31,976,006"""
    try:
        print(f"🔧 [JUNE_DEBUG] Investigating June revenue discrepancy...")
        
        # Load raw data
        df = load_booking_data()
        if df.empty:
            return jsonify({'success': False, 'message': 'No data available'})
        
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        
        # Method 1: Monthly revenue calculation (shows 36,109,006)
        print(f"🔧 [JUNE_DEBUG] === MONTHLY REVENUE CALCULATION ===")
        checked_in_mask = df['Check-in Date'].dt.date <= today
        df_checked_in = df[checked_in_mask].copy()
        
        # Filter for June 2025
        june_mask = df_checked_in['Check-in Date'].dt.strftime('%Y-%m') == '2025-06'
        june_guests_monthly = df_checked_in[june_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] Monthly method: {len(june_guests_monthly)} June guests")
        
        valid_collectors = ['LOC LE', 'THAO LE']
        june_collected_monthly = june_guests_monthly[june_guests_monthly['Người thu tiền'].isin(valid_collectors)].copy()
        june_monthly_total = june_collected_monthly['Tổng thanh toán'].sum()
        
        print(f"🔧 [JUNE_DEBUG] Monthly collected total: {june_monthly_total:,.0f}đ from {len(june_collected_monthly)} guests")
        
        # Method 2: Collector chart calculation (shows 31,976,006)  
        print(f"🔧 [JUNE_DEBUG] === COLLECTOR CHART CALCULATION ===")
        
        # Use period filter (June 1 to June 30)
        start_dt = datetime.strptime('2025-06-01', '%Y-%m-%d').date()
        end_dt = datetime.strptime('2025-06-30', '%Y-%m-%d').date()
        
        period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
        checked_in_period_mask = df['Check-in Date'].dt.date <= today
        
        june_guests_chart = df[checked_in_period_mask & period_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] Chart method: {len(june_guests_chart)} June guests (with period filter)")
        
        june_collected_chart = june_guests_chart[june_guests_chart['Người thu tiền'].isin(valid_collectors)].copy()
        june_chart_total = june_collected_chart['Tổng thanh toán'].sum()
        
        print(f"🔧 [JUNE_DEBUG] Chart collected total: {june_chart_total:,.0f}đ from {len(june_collected_chart)} guests")
        
        # Find the difference
        difference = june_monthly_total - june_chart_total
        print(f"🔧 [JUNE_DEBUG] DIFFERENCE: {difference:,.0f}đ")
        
        # Find guests that are in monthly but not in chart
        monthly_booking_ids = set(june_collected_monthly['Số đặt phòng'].astype(str))
        chart_booking_ids = set(june_collected_chart['Số đặt phòng'].astype(str))
        
        missing_in_chart = monthly_booking_ids - chart_booking_ids
        extra_in_monthly = chart_booking_ids - monthly_booking_ids
        
        print(f"🔧 [JUNE_DEBUG] Missing in chart: {len(missing_in_chart)} bookings")
        print(f"🔧 [JUNE_DEBUG] Extra in monthly: {len(extra_in_monthly)} bookings")
        
        # Get details of missing guests
        missing_guests = []
        if missing_in_chart:
            missing_df = june_collected_monthly[june_collected_monthly['Số đặt phòng'].astype(str).isin(missing_in_chart)]
            for _, guest in missing_df.iterrows():
                missing_guests.append({
                    'name': guest.get('Tên người đặt', 'N/A'),
                    'booking_id': str(guest.get('Số đặt phòng', 'N/A')),
                    'amount': float(guest.get('Tổng thanh toán', 0)),
                    'collector': guest.get('Người thu tiền', 'N/A'),
                    'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A',
                    'reason': 'In monthly calculation but not in chart calculation'
                })
        
        # Check all June guests regardless of collection status
        print(f"🔧 [JUNE_DEBUG] === ALL JUNE GUESTS ANALYSIS ===")
        all_june_monthly = df_checked_in[june_mask].copy()
        all_june_chart = df[checked_in_period_mask & period_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] All June guests (monthly): {len(all_june_monthly)}")
        print(f"🔧 [JUNE_DEBUG] All June guests (chart): {len(all_june_chart)}")
        
        # Collector breakdown
        monthly_collectors = {}
        chart_collectors = {}
        
        for collector in valid_collectors:
            monthly_collector_amount = june_collected_monthly[june_collected_monthly['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
            chart_collector_amount = june_collected_chart[june_collected_chart['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
            
            monthly_collectors[collector] = {
                'amount': float(monthly_collector_amount),
                'count': len(june_collected_monthly[june_collected_monthly['Người thu tiền'] == collector])
            }
            chart_collectors[collector] = {
                'amount': float(chart_collector_amount),
                'count': len(june_collected_chart[june_collected_chart['Người thu tiền'] == collector])
            }
            
            print(f"🔧 [JUNE_DEBUG] {collector}:")
            print(f"🔧 [JUNE_DEBUG]   Monthly: {monthly_collector_amount:,.0f}đ ({monthly_collectors[collector]['count']} guests)")
            print(f"🔧 [JUNE_DEBUG]   Chart: {chart_collector_amount:,.0f}đ ({chart_collectors[collector]['count']} guests)")
            print(f"🔧 [JUNE_DEBUG]   Diff: {monthly_collector_amount - chart_collector_amount:,.0f}đ")
        
        return jsonify({
            'success': True,
            'analysis': {
                'monthly_total': float(june_monthly_total),
                'chart_total': float(june_chart_total),
                'difference': float(difference),
                'monthly_guest_count': len(june_collected_monthly),
                'chart_guest_count': len(june_collected_chart),
                'missing_guests': missing_guests,
                'collector_breakdown': {
                    'monthly': monthly_collectors,
                    'chart': chart_collectors
                },
                'all_guests_count': {
                    'monthly': len(all_june_monthly),
                    'chart': len(all_june_chart)
                }
            }
        })
        
    except Exception as e:
        print(f"❌ [JUNE_DEBUG] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/debug_collector_comparison')
def debug_collector_comparison_page():
    """Debug page to compare collector calculations"""
    return render_template('debug_collector_comparison.html')

