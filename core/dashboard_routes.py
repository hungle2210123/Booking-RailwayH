# dashboard_routes.py - Dashboard logic module
from flask import render_template, request
from datetime import datetime, timedelta, date
import calendar
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import warnings

def safe_to_dict_records(df):
    """
    Safely convert DataFrame to dict records, handling duplicate columns and undefined values
    """
    if df.empty:
        return []
    
    try:
        # Check for duplicate columns and clean if necessary
        if df.columns.duplicated().any():
            print("WARNING: DataFrame has duplicate columns, cleaning...")
            # Keep only the first occurrence of each column
            df = df.loc[:, ~df.columns.duplicated()]
        
        # Clean DataFrame to prevent JSON serialization errors
        df_clean = df.copy()
        
        # Replace NaN, None, and other problematic values
        df_clean = df_clean.fillna('')  # Replace NaN with empty string
        
        # Handle any remaining undefined/problematic values
        for col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(lambda x: x if x is not None and str(x) != 'nan' and str(x) != 'NaT' else '')
        
        # Convert any remaining complex objects to strings
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                df_clean[col] = df_clean[col].astype(str).replace('nan', '').replace('None', '')
            
        # Suppress the warning temporarily
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="DataFrame columns are not unique")
            return df_clean.to_dict('records')
    except Exception as e:
        print(f"Error in safe_to_dict_records: {e}")
        import traceback
        traceback.print_exc()
        return []


def process_dashboard_data(df, start_date, end_date, sort_by, sort_order, dashboard_data):
    """
    Xử lý dữ liệu dashboard phức tạp
    """
    # Chuẩn bị dữ liệu cho template
    monthly_revenue_list = safe_to_dict_records(dashboard_data.get('monthly_revenue_all_time', pd.DataFrame()))
    genius_stats_list = safe_to_dict_records(dashboard_data.get('genius_stats', pd.DataFrame()))
    monthly_guests_list = safe_to_dict_records(dashboard_data.get('monthly_guests_all_time', pd.DataFrame()))
    weekly_guests_list = safe_to_dict_records(dashboard_data.get('weekly_guests_all_time', pd.DataFrame()))
    monthly_collected_revenue_list = safe_to_dict_records(dashboard_data.get('monthly_collected_revenue', pd.DataFrame()))

    # Tạo biểu đồ doanh thu hàng tháng
    monthly_revenue_chart_json = create_revenue_chart(monthly_revenue_list)
    
    # Xử lý khách chưa thu tiền quá hạn
    overdue_unpaid_guests, overdue_total_amount = process_overdue_guests(df)
    
    # ✅ CORRECTED: Monthly revenue shows ALL months (each with accurate per-month amounts)
    # Collector chart uses date filter for period-specific view
    # ⚡ ULTRA PERFORMANCE: Use ONLY traditional method (faster, still accurate)
    monthly_revenue_with_unpaid = process_monthly_revenue_with_unpaid(df)

    # ⚡ PERFORMANCE: Disabled dual-method calculation (saves 50% processing time)
    monthly_revenue_daily_distribution = []  # Disabled for performance

    # ⚡ PERFORMANCE: Weekly revenue calculated on-demand only (not needed for dashboard)
    weekly_revenue_with_unpaid = []  # Disabled for performance
    
    # Xử lý doanh thu theo tuần (4 tuần gần nhất)
    weekly_revenue_analysis = process_weekly_revenue_analysis(df, weeks_back=4)
    
    # Phát hiện ngày có quá nhiều khách
    overcrowded_days = detect_overcrowded_days(df)
    
    # Tính tổng doanh thu theo ngày cho calendar (chia theo số đêm ở)
    daily_revenue_by_stay = get_daily_revenue_by_stay(df)
    
    # Convert to daily_totals format for compatibility
    daily_totals = []
    for date, data in daily_revenue_by_stay.items():
        today = datetime.today().date()
        days_from_today = (date - today).days
        
        daily_totals.append({
            'date': date,
            'guest_count': data['guest_count'],
            'daily_total': data['daily_total'],
            'bookings': data['bookings'],
            'days_from_today': days_from_today,
            'is_today': days_from_today == 0,
            'is_future': days_from_today > 0
        })
    
    # Tạo biểu đồ pie chart cho người thu tiền
    collector_chart_data = create_collector_chart(dashboard_data)
    
    # Xử lý thông báo khách đến và khách đi
    arrival_notifications = process_arrival_notifications(df)
    departure_notifications = process_departure_notifications(df)
    
    return {
        'monthly_revenue_list': monthly_revenue_list,
        'genius_stats_list': genius_stats_list,
        'monthly_guests_list': monthly_guests_list,
        'weekly_guests_list': weekly_guests_list,
        'monthly_collected_revenue_list': monthly_collected_revenue_list,
        'monthly_revenue_chart_json': monthly_revenue_chart_json,
        'monthly_revenue_with_unpaid': monthly_revenue_with_unpaid,
        'monthly_revenue_daily_distribution': monthly_revenue_daily_distribution,
        'weekly_revenue_with_unpaid': weekly_revenue_with_unpaid,
        'weekly_revenue_analysis': weekly_revenue_analysis,
        'overdue_unpaid_guests': overdue_unpaid_guests,
        'overdue_total_amount': overdue_total_amount,
        'overcrowded_days': overcrowded_days,
        'daily_totals': daily_totals,
        'collector_chart_json': collector_chart_data,
        'arrival_notifications': arrival_notifications,
        'departure_notifications': departure_notifications
    }


def create_revenue_chart(monthly_revenue_list):
    """Tạo biểu đồ doanh thu hàng tháng với phân tích chi tiết cho quản lý chiến lược"""
    monthly_revenue_df = pd.DataFrame(monthly_revenue_list)
    
    if monthly_revenue_df.empty:
        return {}
    
    try:
        # Sắp xếp lại theo tháng
        monthly_revenue_df_sorted = monthly_revenue_df.sort_values('Tháng')
        
        # Determine revenue column
        y_column = 'Tổng thanh toán' if 'Tổng thanh toán' in monthly_revenue_df_sorted.columns else 'Doanh thu'
        
        # Calculate performance metrics for strategic analysis
        revenues = monthly_revenue_df_sorted[y_column].astype(float)
        avg_revenue = revenues.mean()
        max_revenue = revenues.max()
        min_revenue = revenues.min()
        
        # Create performance categories
        def get_performance_category(value):
            if value >= avg_revenue * 1.2:  # 20% above average
                return 'Cao'
            elif value <= avg_revenue * 0.8:  # 20% below average
                return 'Thấp'
            else:
                return 'Trung bình'
        
        # Add performance analysis
        monthly_revenue_df_sorted['performance'] = revenues.apply(get_performance_category)
        monthly_revenue_df_sorted['vs_avg'] = ((revenues - avg_revenue) / avg_revenue * 100).round(1)
        
        # Create color mapping for strategic management
        color_map = {
            'Cao': '#27ae60',      # Green for high performance
            'Thấp': '#e74c3c',     # Red for low performance  
            'Trung bình': '#f39c12' # Orange for average
        }
        
        # Create detailed bar chart with performance indicators
        fig = go.Figure()
        
        # Add main revenue bars with performance colors
        for category in ['Cao', 'Trung bình', 'Thấp']:
            category_data = monthly_revenue_df_sorted[monthly_revenue_df_sorted['performance'] == category]
            if not category_data.empty:
                fig.add_trace(go.Bar(
                    x=category_data['Tháng'],
                    y=category_data[y_column],
                    name=f'Tháng {category}',
                    marker_color=color_map[category],
                    text=[f'{val:,.0f}đ<br>({vs_avg:+.1f}%)' for val, vs_avg in zip(category_data[y_column], category_data['vs_avg'])],
                    textposition='outside',
                    textfont=dict(size=10, color='black', family='Arial Black'),
                    hovertemplate='<b>%{x}</b><br>' +
                                  'Doanh thu: %{y:,.0f}đ<br>' +
                                  'So với TB: %{customdata:+.1f}%<br>' +
                                  'Hiệu suất: ' + category + '<extra></extra>',
                    customdata=category_data['vs_avg']
                ))
        
        # Add average line for reference
        fig.add_hline(
            y=avg_revenue,
            line_dash="dash",
            line_color="rgba(52, 73, 94, 0.8)",
            line_width=2,
            annotation_text=f"Trung bình: {avg_revenue:,.0f}đ",
            annotation_position="top left",
            annotation_font=dict(size=12, color="rgba(52, 73, 94, 1)")
        )
        
        # Add trend line (optional - requires scipy)
        try:
            from scipy import stats
            if len(monthly_revenue_df_sorted) > 1:
                x_numeric = range(len(monthly_revenue_df_sorted))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x_numeric, revenues)
                trend_line = [slope * x + intercept for x in x_numeric]
                
                trend_color = '#27ae60' if slope > 0 else '#e74c3c'
                trend_direction = '📈 Tăng' if slope > 0 else '📉 Giảm'
                
                fig.add_trace(go.Scatter(
                    x=monthly_revenue_df_sorted['Tháng'],
                    y=trend_line,
                    mode='lines',
                    name=f'Xu hướng {trend_direction}',
                    line=dict(color=trend_color, width=3, dash='dot'),
                    hovertemplate='Xu hướng: ' + trend_direction + '<extra></extra>'
                ))
        except ImportError:
            print("ℹ️ scipy not available - skipping trend line analysis")
        
        # Enhanced layout for strategic management - FIXED titlefont → title_font
        fig.update_layout(
            title={
                'text': f'📊 Phân tích Doanh thu Chiến lược theo Tháng<br>' +
                        f'<sub>TB: {avg_revenue:,.0f}đ | Cao nhất: {max_revenue:,.0f}đ | Thấp nhất: {min_revenue:,.0f}đ</sub>',
                'x': 0.5,
                'font': {'size': 16, 'family': 'Arial Black', 'color': '#2c3e50'}
            },
            xaxis=dict(
                title='Tháng',
                title_font=dict(size=14, family='Arial Black'),  # FIXED: titlefont → title_font
                tickfont=dict(size=12),
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.1)'
            ),
            yaxis=dict(
                title='Doanh thu (VND)',
                title_font=dict(size=14, family='Arial Black'),  # FIXED: titlefont → title_font
                tickfont=dict(size=12),
                tickformat=',.0f',
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.1)'
            ),
            hovermode='x unified',
            plot_bgcolor='rgba(248, 249, 250, 0.8)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=500,
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.1)',
                borderwidth=1
            ),
            font={'family': 'Arial', 'size': 12},
            margin=dict(l=80, r=30, t=100, b=80),
            # Add performance summary annotation
            annotations=[
                dict(
                    x=0.98,
                    y=0.02,
                    xref='paper',
                    yref='paper',
                    text=f'🎯 Hiệu suất:<br>' +
                         f'• Cao: {len(monthly_revenue_df_sorted[monthly_revenue_df_sorted["performance"] == "Cao"])} tháng<br>' +
                         f'• TB: {len(monthly_revenue_df_sorted[monthly_revenue_df_sorted["performance"] == "Trung bình"])} tháng<br>' +
                         f'• Thấp: {len(monthly_revenue_df_sorted[monthly_revenue_df_sorted["performance"] == "Thấp"])} tháng',
                    showarrow=False,
                    font=dict(size=10, family='Arial'),
                    bgcolor='rgba(255,255,255,0.9)',
                    bordercolor='rgba(0,0,0,0.1)',
                    borderwidth=1,
                    xanchor='right',
                    yanchor='bottom'
                )
            ]
        )
        
        return json.loads(fig.to_json())
    
    except Exception as e:
        print(f"Enhanced chart creation error: {e}")
        import traceback
        traceback.print_exc()
        return {}


def process_overdue_guests(df):
    """Xử lý logic khách chưa thu tiền quá hạn"""
    overdue_unpaid_guests = []
    overdue_total_amount = 0
    
    try:
        if df.empty or 'Check-in Date' not in df.columns:
            print("🔍 [OVERDUE] DataFrame is empty or missing Check-in Date column")
            return overdue_unpaid_guests, overdue_total_amount
            
        print(f"🔍 [OVERDUE] Starting with {len(df)} total bookings (including ALL duplicates)")
            
        today = datetime.today().date()
        df_work = df.copy()
        
        # Convert dates
        df_work['Check-in Date'] = pd.to_datetime(df_work['Check-in Date'], errors='coerce', dayfirst=True)
        valid_dates_mask = df_work['Check-in Date'].notna()
        
        if not valid_dates_mask.any():
            return overdue_unpaid_guests, overdue_total_amount
            
        df_valid = df_work[valid_dates_mask].copy()
        
        # Create filters
        past_checkin = df_valid['Check-in Date'].dt.date <= today
        collected_values = ['LOC LE', 'THAO LE']
        collector_series = df_valid['Người thu tiền'].fillna('').astype(str)
        not_collected = ~collector_series.isin(collected_values)
        not_cancelled = df_valid['Tình trạng'] != 'Đã hủy'
        
        overdue_mask = past_checkin & not_collected & not_cancelled
        overdue_df = df_valid[overdue_mask].copy()
        
        print(f"🔍 [OVERDUE] Filtering results:")
        print(f"  - Past check-in: {past_checkin.sum()} bookings")
        print(f"  - Not collected: {not_collected.sum()} bookings") 
        print(f"  - Not cancelled: {not_cancelled.sum()} bookings")
        print(f"  - Final overdue (ALL filters): {len(overdue_df)} bookings")
        
        if not overdue_df.empty:
            # Debug: Show some guest names to verify duplicates are included
            guest_names = overdue_df['Tên người đặt'].tolist()[:10]  # First 10 names
            print(f"🔍 [OVERDUE] Sample guest names: {guest_names}")
            
            # Check for duplicates in overdue list
            duplicate_names = overdue_df['Tên người đặt'].value_counts()
            duplicates_found = duplicate_names[duplicate_names > 1]
            if not duplicates_found.empty:
                print(f"🔍 [OVERDUE] Found {len(duplicates_found)} guests with multiple overdue bookings:")
                for name, count in duplicates_found.head().items():
                    print(f"  - {name}: {count} overdue bookings")
            else:
                print("🔍 [OVERDUE] No duplicate guests found in overdue list")
            # Calculate overdue days
            checkin_dates = overdue_df['Check-in Date'].dt.date
            days_overdue_list = [(today - date).days if date else 0 for date in checkin_dates]
            overdue_df['days_overdue'] = [max(0, days) for days in days_overdue_list]
            
            # Calculate total amount including taxi fees
            overdue_df = overdue_df.sort_values('days_overdue', ascending=False)
            
            # Calculate room fees
            room_total = 0
            if 'Tổng thanh toán' in overdue_df.columns:
                room_total = pd.to_numeric(overdue_df['Tổng thanh toán'], errors='coerce').fillna(0).sum()
            
            # Calculate taxi fees
            taxi_total = 0
            if 'Taxi' in overdue_df.columns:
                # Extract numeric values from taxi column (handles formats like "50,000đ", "50000", etc.)
                taxi_series = overdue_df['Taxi'].fillna('').astype(str)
                for taxi_value in taxi_series:
                    if taxi_value and taxi_value.strip():
                        # Remove currency symbols and commas, extract numbers
                        import re
                        numeric_match = re.search(r'[\d,]+', taxi_value.replace('.', ''))
                        if numeric_match:
                            try:
                                taxi_amount = float(numeric_match.group().replace(',', ''))
                                taxi_total += taxi_amount
                            except ValueError:
                                pass
            
            # Total amount = room fees + taxi fees
            overdue_total_amount = room_total + taxi_total
            
            # Add calculated totals to DataFrame BEFORE converting to records
            calculated_room_fees = []
            calculated_taxi_fees = []
            calculated_total_amounts = []
            calculated_commissions = []
            
            for idx, (_, guest_row) in enumerate(overdue_df.iterrows()):
                # Fix: Better room fee calculation
                guest_room_payment = guest_row.get('Tổng thanh toán', 0)
                if guest_room_payment is not None and guest_room_payment != '':
                    try:
                        guest_room_fee = float(guest_room_payment)
                    except (ValueError, TypeError):
                        guest_room_fee = 0
                else:
                    guest_room_fee = 0
                
                guest_taxi_fee = 0
                
                # Fix: Better taxi fee extraction for this guest
                taxi_value = guest_row.get('Taxi', '')
                if taxi_value and str(taxi_value).strip() and str(taxi_value).strip() not in ['nan', 'None', 'N/A', '0', '']:
                    import re
                    # More robust regex to handle various formats (including decimals)
                    taxi_str = str(taxi_value).replace(' ', '').replace('đ', '').replace('VND', '').replace('vnd', '')
                    # Handle both comma and period as thousand separators
                    if ',' in taxi_str and '.' in taxi_str:
                        # Format like 1,234.56 - period is decimal separator
                        taxi_str = taxi_str.replace(',', '')
                    elif taxi_str.count(',') == 1 and len(taxi_str.split(',')[1]) <= 2:
                        # Format like 1234,56 - comma is decimal separator
                        taxi_str = taxi_str.replace(',', '.')
                    else:
                        # Format like 1,234 or 1,234,567 - comma is thousand separator
                        taxi_str = taxi_str.replace(',', '')
                    
                    # Extract number with optional decimal
                    numeric_match = re.search(r'(\d+(?:\.\d+)?)', taxi_str)
                    if numeric_match:
                        try:
                            guest_taxi_fee = float(numeric_match.group())
                            # Validate reasonable taxi fee range (10,000 to 500,000 VND)
                            if guest_taxi_fee < 10000 or guest_taxi_fee > 500000:
                                print(f"WARNING: Unusual taxi fee {guest_taxi_fee} for guest {guest_row.get('Tên người đặt', 'Unknown')}")
                        except ValueError:
                            guest_taxi_fee = 0
                            print(f"ERROR: Could not parse taxi fee '{taxi_value}' for guest {guest_row.get('Tên người đặt', 'Unknown')}")
                else:
                    # Log when no taxi fee is found for debugging
                    print(f"DEBUG: No taxi fee for guest {guest_row.get('Tên người đặt', 'Unknown')}: '{taxi_value}'")
                
                # Calculate commission
                guest_commission = 0
                commission_value = guest_row.get('Hoa hồng', 0)
                if commission_value is not None and commission_value != '':
                    try:
                        guest_commission = float(commission_value)
                    except (ValueError, TypeError):
                        guest_commission = 0
                
                calculated_room_fees.append(guest_room_fee)
                calculated_taxi_fees.append(guest_taxi_fee)  
                calculated_total_amounts.append(guest_room_fee + guest_taxi_fee)
                calculated_commissions.append(guest_commission)
            
            # Add calculated columns to DataFrame
            overdue_df['calculated_room_fee'] = calculated_room_fees
            overdue_df['calculated_taxi_fee'] = calculated_taxi_fees
            overdue_df['calculated_total_amount'] = calculated_total_amounts
            overdue_df['calculated_commission'] = calculated_commissions
            
            overdue_unpaid_guests = overdue_df.to_dict('records')
            
            # Debug output for taxi fees
            print(f"✅ Processed {len(overdue_unpaid_guests)} overdue guests with taxi fees:")
            for guest in overdue_unpaid_guests[:3]:  # Show first 3 guests
                guest_name = guest.get('Tên người đặt', 'Unknown')
                room_fee = guest.get('calculated_room_fee', 0)
                taxi_fee = guest.get('calculated_taxi_fee', 0)
                total_fee = guest.get('calculated_total_amount', 0)
                print(f"  - {guest_name}: Room={room_fee:,.0f}đ, Taxi={taxi_fee:,.0f}đ, Total={total_fee:,.0f}đ")
    
    except Exception as e:
        print(f"Process overdue guests error: {e}")
        import traceback
        traceback.print_exc()
    
    return overdue_unpaid_guests, overdue_total_amount


def process_monthly_revenue_with_unpaid_enhanced(df, start_date=None, end_date=None, use_daily_distribution=False):
    """
    ENHANCED: Dual-method monthly revenue processing with optimization
    
    Parameters:
    - use_daily_distribution: If True, uses the new daily distribution method
                             If False, uses traditional method (backward compatible)
    """
    if use_daily_distribution:
        print("📅 [ENHANCED] Using daily distribution method for monthly revenue...")
        
        # Use the new dual method and extract daily distribution results
        dual_results = calculate_revenue_optimized_dual_method(df)
        monthly_data = dual_results.get('daily_distribution_method', {}).get('monthly_summary', [])
        
        # Convert to traditional format for compatibility
        monthly_revenue_with_unpaid = []
        for month_data in monthly_data:
            monthly_revenue_with_unpaid.append({
                'Tháng': month_data['month'],
                'Đã thu': month_data['collected_amount'],
                'Chưa thu': month_data['uncollected_amount'],
                'Tổng cộng': month_data['total_amount'],
                'Hoa hồng đã thu': month_data['commission'] * (month_data['collected_amount'] / month_data['total_amount']) if month_data['total_amount'] > 0 else 0,
                'Hoa hồng chưa thu': month_data['commission'] * (month_data['uncollected_amount'] / month_data['total_amount']) if month_data['total_amount'] > 0 else 0,
                'Tổng hoa hồng': month_data['commission'],
                'Số khách đã thu': round(month_data['collected_guest_nights']),
                'Số khách chưa thu': round(month_data['uncollected_guest_nights']),
                'Tổng số khách': round(month_data['guest_nights']),
                'Tỷ lệ thu': (month_data['collected_amount'] / month_data['total_amount'] * 100) if month_data['total_amount'] > 0 else 0,
                'Method': 'Daily Distribution'
            })
        
        # Sort by month
        monthly_revenue_with_unpaid.sort(key=lambda x: x['Tháng'])
        
        print(f"✅ [ENHANCED] Daily distribution method completed. {len(monthly_revenue_with_unpaid)} months processed")
        return monthly_revenue_with_unpaid
    else:
        print("💰 [ENHANCED] Using traditional method for monthly revenue...")
        # Use original traditional method
        return process_monthly_revenue_with_unpaid_original(df, start_date, end_date)

def process_monthly_revenue_with_unpaid_original(df, start_date=None, end_date=None):
    """Xử lý doanh thu theo tháng bao gồm khách chưa thu và hoa hồng - HIỂN THỊ TẤT CẢ THÁNG (TRADITIONAL METHOD)"""
    monthly_revenue_with_unpaid = []
    
    try:
        if df.empty or 'Check-in Date' not in df.columns:
            return monthly_revenue_with_unpaid
            
        # ✅ CORRECTED: Monthly revenue should show ALL months, but each month calculated accurately
        # This is different from collector chart which shows filtered period only
        df_period = df[df['Check-in Date'].notna()].copy()
        print(f"🔍 [MONTHLY_REVENUE] Processing {len(df_period)} total bookings (ALL MONTHS for table)")
        print(f"🔍 [MONTHLY_REVENUE] Each month will show accurate LOC LE/THAO LE amounts for that specific month")
        
        if df_period.empty:
            return monthly_revenue_with_unpaid
            
        # Ensure commission column exists
        if 'Hoa hồng' not in df_period.columns:
            df_period['Hoa hồng'] = 0
            
        # ✅ CRITICAL FIX: Only include checked-in guests in calculations
        from datetime import date
        today = date.today()
        
        # Filter for checked-in guests only (exclude future arrivals)
        checked_in_mask = df_period['Check-in Date'].dt.date <= today
        df_checked_in = df_period[checked_in_mask].copy()
        
        # ✅ CRITICAL: Exclude cancelled bookings from revenue calculations
        if 'Tình trạng' in df_checked_in.columns:
            initial_count = len(df_checked_in)
            df_checked_in = df_checked_in[df_checked_in['Tình trạng'] != 'Đã hủy'].copy()
            excluded_cancelled = initial_count - len(df_checked_in)
            print(f"🚫 [CANCELLED_FILTER] Excluded {excluded_cancelled} cancelled bookings from revenue calculations")
        else:
            print(f"⚠️ [CANCELLED_FILTER] 'Tình trạng' column not found, cannot filter cancelled bookings")
        
        print(f"🏨 [CHECKED_IN_FILTER] Total bookings: {len(df_period)}, Checked-in only: {len(df_checked_in)}")
        print(f"🏨 [CHECKED_IN_FILTER] Excluded future arrivals: {len(df_period) - len(df_checked_in)} guests")
        
        # Tính doanh thu đã thu và chưa thu (ONLY for checked-in guests with EXACT validation)
        valid_collectors = ['LOC LE', 'THAO LE']

        # Use strict string matching with validation
        collected_mask = df_checked_in['Người thu tiền'].isin(valid_collectors)
        collected_df = df_checked_in[collected_mask].copy()
        uncollected_df = df_checked_in[~collected_mask].copy()
        
        # Process collected revenue with commission
        if not collected_df.empty:
            collected_df['Month_Period'] = collected_df['Check-in Date'].dt.to_period('M')
            collected_monthly = collected_df.groupby('Month_Period').agg({
                'Tổng thanh toán': 'sum',
                'Hoa hồng': 'sum'
            }).reset_index()
            collected_monthly['Tháng'] = collected_monthly['Month_Period'].dt.strftime('%Y-%m')
        else:
            collected_monthly = pd.DataFrame(columns=['Tháng', 'Tổng thanh toán', 'Hoa hồng'])
        
        # Process uncollected revenue with commission
        if not uncollected_df.empty:
            uncollected_df['Month_Period'] = uncollected_df['Check-in Date'].dt.to_period('M')
            uncollected_monthly = uncollected_df.groupby('Month_Period').agg({
                'Tổng thanh toán': 'sum', 
                'Hoa hồng': 'sum',
                'Số đặt phòng': 'count'
            }).reset_index()
            uncollected_monthly['Tháng'] = uncollected_monthly['Month_Period'].dt.strftime('%Y-%m')
            uncollected_monthly = uncollected_monthly.rename(columns={'Số đặt phòng': 'Số khách chưa thu'})
        else:
            uncollected_monthly = pd.DataFrame(columns=['Tháng', 'Tổng thanh toán', 'Hoa hồng', 'Số khách chưa thu'])
        
        # Merge data with commission
        if not collected_monthly.empty and not uncollected_monthly.empty:
            merged_data = pd.merge(
                collected_monthly[['Tháng', 'Tổng thanh toán', 'Hoa hồng']].rename(columns={
                    'Tổng thanh toán': 'Đã thu',
                    'Hoa hồng': 'Hoa hồng_collected'
                }),
                uncollected_monthly[['Tháng', 'Tổng thanh toán', 'Hoa hồng', 'Số khách chưa thu']].rename(columns={
                    'Tổng thanh toán': 'Chưa thu',
                    'Hoa hồng': 'Hoa hồng_uncollected'
                }),
                on='Tháng', how='outer'
            ).fillna(0)
            # Combine commission from both collected and uncollected
            merged_data['Hoa hồng'] = merged_data['Hoa hồng_collected'] + merged_data['Hoa hồng_uncollected']
            merged_data = merged_data.drop(columns=['Hoa hồng_collected', 'Hoa hồng_uncollected'])
        elif not collected_monthly.empty:
            merged_data = collected_monthly.rename(columns={'Tổng thanh toán': 'Đã thu'})
            merged_data[['Chưa thu', 'Số khách chưa thu']] = 0
        elif not uncollected_monthly.empty:
            merged_data = uncollected_monthly.rename(columns={'Tổng thanh toán': 'Chưa thu'})
            merged_data['Đã thu'] = 0
        else:
            merged_data = pd.DataFrame(columns=['Tháng', 'Đã thu', 'Chưa thu', 'Hoa hồng', 'Số khách chưa thu'])
        
        if not merged_data.empty:
            # ✅ ADD DETAILED SPENDING STATISTICS for checked-in guests
            merged_data['Tổng cộng'] = merged_data['Đã thu'] + merged_data['Chưa thu']
            merged_data['Tỷ lệ thu'] = (merged_data['Đã thu'] / merged_data['Tổng cộng'] * 100).round(1)
            merged_data['Tỷ lệ thu'] = merged_data['Tỷ lệ thu'].fillna(0)
            
            # Add detailed guest spending breakdown
            for idx, row in merged_data.iterrows():
                month = row['Tháng']
                month_mask = df_checked_in['Check-in Date'].dt.strftime('%Y-%m') == month
                month_guests = df_checked_in[month_mask]
                
                if not month_guests.empty:
                    # Calculate detailed statistics for this month
                    total_guests = len(month_guests)
                    collected_guests = len(month_guests[month_guests['Người thu tiền'].isin(['LOC LE', 'THAO LE'])])
                    uncollected_guests = total_guests - collected_guests
                    
                    # Average spending per guest
                    avg_spending = month_guests['Tổng thanh toán'].mean() if 'Tổng thanh toán' in month_guests.columns else 0
                    
                    # Commission statistics
                    total_commission = month_guests['Hoa hồng'].sum() if 'Hoa hồng' in month_guests.columns else 0
                    avg_commission = month_guests['Hoa hồng'].mean() if 'Hoa hồng' in month_guests.columns else 0
                    
                    # Add detailed statistics to the row
                    merged_data.at[idx, 'Tổng khách'] = total_guests
                    merged_data.at[idx, 'Khách đã thu'] = collected_guests
                    merged_data.at[idx, 'Chi tiêu TB/khách'] = round(avg_spending, 0)
                    merged_data.at[idx, 'Tổng hoa hồng'] = round(total_commission, 0)
            
            merged_data = merged_data.sort_values('Tháng')
            monthly_revenue_with_unpaid = safe_to_dict_records(merged_data)
    
    except Exception as e:
        print(f"Process monthly revenue error: {e}")
        import traceback
        traceback.print_exc()
    
    return monthly_revenue_with_unpaid

# Backward compatibility alias - existing code can continue using the original function name
def process_monthly_revenue_with_unpaid(df, start_date=None, end_date=None):
    """
    BACKWARD COMPATIBILITY: Wrapper for existing code
    
    By default, uses the traditional method to maintain existing behavior.
    To use the new daily distribution method, call process_monthly_revenue_with_unpaid_enhanced() directly.
    """
    return process_monthly_revenue_with_unpaid_enhanced(df, start_date, end_date, use_daily_distribution=False)

def process_weekly_revenue_with_unpaid(df, start_date=None, end_date=None):
    """Xử lý doanh thu theo tuần bao gồm khách chưa thu và hoa hồng - HIỂN THỊ CHỈ 8 TUẦN RECENT"""
    weekly_revenue_with_unpaid = []
    
    try:
        if df.empty or 'Check-in Date' not in df.columns:
            return weekly_revenue_with_unpaid
            
        # Filter for recent 8 weeks only
        from datetime import date, timedelta
        today = date.today()
        eight_weeks_ago = today - timedelta(weeks=8)
        
        df_period = df[df['Check-in Date'].notna()].copy()
        recent_mask = df_period['Check-in Date'].dt.date >= eight_weeks_ago
        df_recent = df_period[recent_mask].copy()
        
        print(f"🔍 [WEEKLY_REVENUE] Processing {len(df_recent)} recent bookings (LAST 8 WEEKS)")
        
        if df_recent.empty:
            return weekly_revenue_with_unpaid
            
        # Ensure commission column exists
        if 'Hoa hồng' not in df_recent.columns:
            df_recent['Hoa hồng'] = 0
            
        # Filter for checked-in guests only (exclude future arrivals)
        checked_in_mask = df_recent['Check-in Date'].dt.date <= today
        df_checked_in = df_recent[checked_in_mask].copy()
        
        # ✅ CRITICAL: Exclude cancelled bookings from revenue calculations
        if 'Tình trạng' in df_checked_in.columns:
            initial_count = len(df_checked_in)
            df_checked_in = df_checked_in[df_checked_in['Tình trạng'] != 'Đã hủy'].copy()
            excluded_cancelled = initial_count - len(df_checked_in)
            print(f"🚫 [WEEKLY_CANCELLED_FILTER] Excluded {excluded_cancelled} cancelled bookings from weekly revenue calculations")
        else:
            print(f"⚠️ [WEEKLY_CANCELLED_FILTER] 'Tình trạng' column not found, cannot filter cancelled bookings")
        
        print(f"🏨 [WEEKLY_CHECKED_IN] Total recent: {len(df_recent)}, Checked-in only: {len(df_checked_in)}")
        
        if df_checked_in.empty:
            return weekly_revenue_with_unpaid
        
        # Add week calculation
        df_checked_in['Week_Start'] = df_checked_in['Check-in Date'].dt.to_period('W').dt.start_time
        df_checked_in['Week_Label'] = df_checked_in['Week_Start'].dt.strftime('%Y-W%U (%m/%d)')
        
        # Split collected vs uncollected
        valid_collectors = ['LOC LE', 'THAO LE']
        collected_mask = df_checked_in['Người thu tiền'].isin(valid_collectors)
        collected_df = df_checked_in[collected_mask].copy()
        uncollected_df = df_checked_in[~collected_mask].copy()
        
        # Process collected revenue by week
        if not collected_df.empty:
            collected_weekly = collected_df.groupby('Week_Label').agg({
                'Tổng thanh toán': 'sum',
                'Hoa hồng': 'sum',
                'Week_Start': 'first'
            }).reset_index()
        else:
            collected_weekly = pd.DataFrame(columns=['Week_Label', 'Tổng thanh toán', 'Hoa hồng', 'Week_Start'])
        
        # Process uncollected revenue by week
        if not uncollected_df.empty:
            uncollected_weekly = uncollected_df.groupby('Week_Label').agg({
                'Tổng thanh toán': 'sum', 
                'Hoa hồng': 'sum',
                'Số đặt phòng': 'count',
                'Week_Start': 'first'
            }).reset_index()
            uncollected_weekly = uncollected_weekly.rename(columns={'Số đặt phòng': 'Số khách chưa thu'})
        else:
            uncollected_weekly = pd.DataFrame(columns=['Week_Label', 'Tổng thanh toán', 'Hoa hồng', 'Số khách chưa thu', 'Week_Start'])
        
        # Merge data
        if not collected_weekly.empty and not uncollected_weekly.empty:
            merged_data = pd.merge(
                collected_weekly[['Week_Label', 'Tổng thanh toán', 'Hoa hồng', 'Week_Start']].rename(columns={
                    'Tổng thanh toán': 'Đã thu',
                    'Hoa hồng': 'Hoa hồng_collected'
                }),
                uncollected_weekly[['Week_Label', 'Tổng thanh toán', 'Hoa hồng', 'Số khách chưa thu', 'Week_Start']].rename(columns={
                    'Tổng thanh toán': 'Chưa thu',
                    'Hoa hồng': 'Hoa hồng_uncollected',
                    'Week_Start': 'Week_Start_uncollected'
                }),
                on='Week_Label', how='outer'
            ).fillna(0)
            
            # Fill missing Week_Start values using the uncollected Week_Start
            merged_data['Week_Start'] = merged_data['Week_Start'].fillna(merged_data['Week_Start_uncollected'])
            merged_data = merged_data.drop(columns=['Week_Start_uncollected'])
            
            merged_data['Hoa hồng'] = merged_data['Hoa hồng_collected'] + merged_data['Hoa hồng_uncollected']
            merged_data = merged_data.drop(columns=['Hoa hồng_collected', 'Hoa hồng_uncollected'])
        elif not collected_weekly.empty:
            merged_data = collected_weekly.rename(columns={'Tổng thanh toán': 'Đã thu'})
            merged_data[['Chưa thu', 'Số khách chưa thu']] = 0
        elif not uncollected_weekly.empty:
            merged_data = uncollected_weekly.rename(columns={'Tổng thanh toán': 'Chưa thu'})
            merged_data['Đã thu'] = 0
        else:
            merged_data = pd.DataFrame(columns=['Week_Label', 'Đã thu', 'Chưa thu', 'Hoa hồng', 'Số khách chưa thu', 'Week_Start'])
        
        if not merged_data.empty:
            # Add calculations
            merged_data['Tổng cộng'] = merged_data['Đã thu'] + merged_data['Chưa thu']
            merged_data['Tỷ lệ thu'] = (merged_data['Đã thu'] / merged_data['Tổng cộng'] * 100).round(1)
            
            # Add guest counts
            if not df_checked_in.empty:
                guest_counts = df_checked_in.groupby('Week_Label').size().reset_index(name='Tổng khách')
                collected_counts = collected_df.groupby('Week_Label').size().reset_index(name='Khách đã thu') if not collected_df.empty else pd.DataFrame(columns=['Week_Label', 'Khách đã thu'])
                
                merged_data = pd.merge(merged_data, guest_counts, on='Week_Label', how='left')
                merged_data = pd.merge(merged_data, collected_counts, on='Week_Label', how='left')
                merged_data['Khách đã thu'] = merged_data['Khách đã thu'].fillna(0)
                
                # Calculate average per guest
                merged_data['TB/khách'] = (merged_data['Tổng cộng'] / merged_data['Tổng khách']).round(0)
            
            # Sort by week start date (most recent first)
            if 'Week_Start' in merged_data.columns:
                try:
                    # Ensure Week_Start column has consistent datetime types
                    merged_data['Week_Start'] = pd.to_datetime(merged_data['Week_Start'])
                    merged_data = merged_data.sort_values('Week_Start', ascending=False)
                except Exception as e:
                    print(f"⚠️ [WEEKLY_REVENUE_SORT] Could not sort by Week_Start: {e}")
                    # Fallback: sort by Week_Label if Week_Start sorting fails
                    if 'Week_Label' in merged_data.columns:
                        merged_data = merged_data.sort_values('Week_Label', ascending=False)
            
            # Rename Week_Label to Tuần for display
            merged_data = merged_data.rename(columns={'Week_Label': 'Tuần'})
            
            # Convert to records and handle NaN values
            def safe_to_dict_records(df):
                try:
                    records = df.to_dict('records')
                    for record in records:
                        for key, value in record.items():
                            if pd.isna(value) or value == float('inf') or value == float('-inf'):
                                record[key] = 0
                    return records
                except Exception as e:
                    print(f"Error converting to dict: {e}")
                    return []
            
            weekly_revenue_with_unpaid = safe_to_dict_records(merged_data)
            
            print(f"📋 [WEEKLY_SUMMARY] Generated table with {len(weekly_revenue_with_unpaid)} weeks")
            for row in weekly_revenue_with_unpaid:
                week = row.get('Tuần', 'N/A')
                collected = row.get('Đã thu', 0)
                uncollected = row.get('Chưa thu', 0)
                total = row.get('Tổng cộng', 0)
                print(f"📋   {week}: Collected={collected:,.0f}đ, Uncollected={uncollected:,.0f}đ, Total={total:,.0f}đ")
    
    except Exception as e:
        import traceback
        print(f"❌ [WEEKLY_REVENUE_ERROR] {e}")
        traceback.print_exc()
        return []
    
    return weekly_revenue_with_unpaid

def process_weekly_revenue_analysis(df, weeks_back=4):
    """Tạo phân tích doanh thu theo tuần cho 4 tuần gần nhất"""
    weekly_revenue_analysis = []
    
    try:
        if df.empty or 'Check-in Date' not in df.columns:
            return weekly_revenue_analysis
            
        # Convert dates
        df = df.copy()
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        
        # Get current date and calculate week boundaries
        current_date = pd.Timestamp.now()
        
        # Process last N weeks
        for week_offset in range(weeks_back):
            week_start = current_date - pd.Timedelta(weeks=week_offset+1)
            week_end = current_date - pd.Timedelta(weeks=week_offset)
            
            # Filter data for this week
            week_df = df[
                (df['Check-in Date'] >= week_start) & 
                (df['Check-in Date'] < week_end) &
                (df['Check-in Date'].notna()) &
                (df['Người thu tiền'].isin(['LOC LE', 'THAO LE']))  # Only collected payments
            ].copy()
            
            if not week_df.empty:
                # Calculate week metrics
                total_collected = week_df['Tổng thanh toán'].sum() if 'Tổng thanh toán' in week_df.columns else 0
                total_commission = week_df['Hoa hồng'].sum() if 'Hoa hồng' in week_df.columns else 0
                customer_count = len(week_df)
                
                # Format week period
                week_label = f"Tuần {week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}"
                
                weekly_revenue_analysis.append({
                    'Tuần': week_label,
                    'Đã thu': total_collected,
                    'Hoa hồng': total_commission,
                    'Số khách': customer_count,
                    'week_start': week_start.strftime('%Y-%m-%d'),
                    'week_end': week_end.strftime('%Y-%m-%d')
                })
            else:
                # Add empty week data
                week_label = f"Tuần {week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}"
                weekly_revenue_analysis.append({
                    'Tuần': week_label,
                    'Đã thu': 0,
                    'Hoa hồng': 0,
                    'Số khách': 0,
                    'week_start': week_start.strftime('%Y-%m-%d'),
                    'week_end': week_end.strftime('%Y-%m-%d')
                })
        
        # Reverse to show most recent week first
        weekly_revenue_analysis.reverse()
        
    except Exception as e:
        print(f"Process weekly revenue error: {e}")
        import traceback
        traceback.print_exc()
    
    return weekly_revenue_analysis


def detect_overcrowded_days(df):
    """Phát hiện ngày có khách check-in vượt quá số phòng khả dụng"""
    overcrowded_days = []

    try:
        # Get total available rooms from database
        from core.models import Apartment, Room, db

        total_available_rooms = 0
        try:
            # Count total rooms across all active apartments
            total_available_rooms = db.session.query(db.func.count(Room.room_id)).join(
                Apartment, Room.apartment_id == Apartment.apartment_id
            ).filter(
                Apartment.is_active == True
            ).scalar() or 0

            print(f"📊 [OVERLOAD_CHECK] Total available rooms in system: {total_available_rooms}")
        except Exception as e:
            print(f"⚠️ [OVERLOAD_CHECK] Could not get room count from database, using default: {e}")
            total_available_rooms = 6  # Default fallback

        if df.empty or 'Check-in Date' not in df.columns:
            return overcrowded_days

        today = datetime.today()
        check_start = today - timedelta(days=30)
        check_end = today + timedelta(days=30)

        df_check = df.copy()
        df_check['Check-in Date'] = pd.to_datetime(df_check['Check-in Date'], errors='coerce', dayfirst=True)

        valid_checkins = df_check[
            (df_check['Check-in Date'].notna()) &
            (df_check['Check-in Date'] >= pd.Timestamp(check_start)) &
            (df_check['Check-in Date'] <= pd.Timestamp(check_end)) &
            (df_check['Tình trạng'] != 'Đã hủy')
        ].copy()

        if valid_checkins.empty:
            return overcrowded_days

        # Group by date and count guests + calculate daily totals
        daily_checkins = valid_checkins.groupby(valid_checkins['Check-in Date'].dt.date).agg({
            'Số đặt phòng': ['count', lambda x: list(x)],
            'Tên người đặt': lambda x: list(x),
            'Tổng thanh toán': ['sum', lambda x: list(x)]
        })
        daily_checkins.columns = ['guest_count', 'booking_ids', 'guest_names', 'daily_total', 'individual_amounts']

        # Find overcrowded dates (guests > available rooms)
        overcrowded_dates = daily_checkins[daily_checkins['guest_count'] > total_available_rooms]

        if not overcrowded_dates.empty:
            print(f"⚠️ [OVERLOAD_DETECTED] Found {len(overcrowded_dates)} overcrowded dates (threshold: {total_available_rooms} rooms)")
        
        for date, row in overcrowded_dates.iterrows():
            days_from_today = (date - today.date()).days
            
            # Classify alert level
            if days_from_today < 0:
                alert_level, alert_color = 'past', 'secondary'
            elif days_from_today <= 3:
                alert_level, alert_color = 'urgent', 'danger'
            elif days_from_today <= 7:
                alert_level, alert_color = 'warning', 'warning'
            else:
                alert_level, alert_color = 'info', 'info'
            
            overcrowded_days.append({
                'date': date, 'guest_count': row['guest_count'],
                'booking_ids': row['booking_ids'], 'guest_names': row['guest_names'],
                'daily_total': row['daily_total'], 'individual_amounts': row['individual_amounts'],
                'days_from_today': days_from_today, 'alert_level': alert_level,
                'alert_color': alert_color, 'is_today': days_from_today == 0,
                'is_future': days_from_today > 0
            })
        
        # Sort by proximity to today
        overcrowded_days.sort(key=lambda x: abs(x['days_from_today']))
    
    except Exception as e:
        print(f"Detect overcrowded days error: {e}")
    
    return overcrowded_days


def get_daily_totals(df):
    """Tính tổng doanh thu theo ngày cho calendar"""
    daily_totals = []
    
    try:
        if df.empty or 'Check-in Date' not in df.columns:
            return daily_totals
            
        today = datetime.today()
        check_start = today - timedelta(days=7)  # 7 days ago
        check_end = today + timedelta(days=14)   # 14 days ahead
        
        df_check = df.copy()
        df_check['Check-in Date'] = pd.to_datetime(df_check['Check-in Date'], errors='coerce', dayfirst=True)
        
        valid_checkins = df_check[
            (df_check['Check-in Date'].notna()) &
            (df_check['Check-in Date'] >= pd.Timestamp(check_start)) &
            (df_check['Check-in Date'] <= pd.Timestamp(check_end)) &
            (df_check['Tình trạng'] != 'Đã hủy')
        ].copy()
        
        if valid_checkins.empty:
            return daily_totals
            
        # Group by date and calculate totals
        daily_checkins = valid_checkins.groupby(valid_checkins['Check-in Date'].dt.date).agg({
            'Số đặt phòng': ['count', lambda x: list(x)],
            'Tên người đặt': lambda x: list(x),
            'Tổng thanh toán': ['sum', lambda x: list(x)]
        })
        daily_checkins.columns = ['guest_count', 'booking_ids', 'guest_names', 'daily_total', 'individual_amounts']
        
        for date, row in daily_checkins.iterrows():
            days_from_today = (date - today.date()).days
            
            daily_totals.append({
                'date': date,
                'guest_count': row['guest_count'],
                'booking_ids': row['booking_ids'],
                'guest_names': row['guest_names'],
                'daily_total': row['daily_total'],
                'individual_amounts': row['individual_amounts'],
                'days_from_today': days_from_today,
                'is_today': days_from_today == 0,
                'is_future': days_from_today > 0
            })
        
        # Sort by date
        daily_totals.sort(key=lambda x: x['date'])
    
    except Exception as e:
        print(f"Get daily totals error: {e}")
    
    return daily_totals


def calculate_revenue_optimized_dual_method(df):
    """
    OPTIMIZED REVENUE CALCULATION - DUAL METHOD
    
    Method 1: Traditional calculation (kept as is)
    - Based on original booking amounts and collected amounts
    - Used for existing payment tracking and collection status
    
    Method 2: Daily distribution calculation (new - like calendar)
    - Divides amounts across each night of stay
    - More accurate for monthly revenue totals
    - Better represents actual daily occupancy value
    
    Returns both methods for comparison and optimization
    """
    result = {
        'traditional_method': {},
        'daily_distribution_method': {},
        'comparison_summary': {}
    }
    
    try:
        if df.empty:
            return result
            
        # ==================== METHOD 1: TRADITIONAL (KEPT AS IS) ====================
        print("💰 [DUAL_METHOD] Calculating traditional method (existing)...")
        
        # Traditional: Group by check-in month (current method)
        df_traditional = df[df['Check-in Date'].notna()].copy()
        
        # Separate collected vs uncollected (existing logic)
        valid_collectors = ['LOC LE', 'THAO LE']
        collected_traditional = df_traditional[df_traditional['Người thu tiền'].isin(valid_collectors)]
        uncollected_traditional = df_traditional[~df_traditional['Người thu tiền'].isin(valid_collectors)]
        
        # Group by month (traditional way)
        if not collected_traditional.empty:
            collected_traditional = collected_traditional.copy()  # Fix pandas warning
            collected_traditional['Month'] = collected_traditional['Check-in Date'].dt.to_period('M')
            traditional_collected = collected_traditional.groupby('Month').agg({
                'Tổng thanh toán': 'sum',
                'Số tiền đã thu': 'sum',
                'Hoa hồng': 'sum',
                'Số đặt phòng': 'count'
            }).reset_index()
            traditional_collected['Tháng'] = traditional_collected['Month'].dt.strftime('%Y-%m')
        else:
            traditional_collected = pd.DataFrame()
            
        if not uncollected_traditional.empty:
            uncollected_traditional = uncollected_traditional.copy()
            uncollected_traditional.loc[:, 'Month'] = uncollected_traditional['Check-in Date'].dt.to_period('M')
            traditional_uncollected = uncollected_traditional.groupby('Month').agg({
                'Tổng thanh toán': 'sum',
                'Số tiền đã thu': 'sum',
                'Hoa hồng': 'sum',
                'Số đặt phòng': 'count'
            }).reset_index()
            traditional_uncollected['Tháng'] = traditional_uncollected['Month'].dt.strftime('%Y-%m')
        else:
            traditional_uncollected = pd.DataFrame()
        
        result['traditional_method'] = {
            'collected': traditional_collected.to_dict('records') if not traditional_collected.empty else [],
            'uncollected': traditional_uncollected.to_dict('records') if not traditional_uncollected.empty else []
        }
        
        # ==================== METHOD 2: DAILY DISTRIBUTION (NEW) ====================
        print("📅 [DUAL_METHOD] Calculating daily distribution method (new)...")
        
        daily_revenue_data = {}
        monthly_summary = {}
        
        # Process each booking and distribute across stay duration
        df_valid = df[
            (df['Check-in Date'].notna()) &
            (df['Check-out Date'].notna()) &
            (df['Tổng thanh toán'].notna()) &
            (df['Tổng thanh toán'] > 0) &
            (df['Tình trạng'] != 'Đã hủy')
        ].copy()
        
        for _, booking in df_valid.iterrows():
            checkin_date = booking['Check-in Date'].date()
            checkout_date = booking['Check-out Date'].date()
            total_amount = float(booking['Tổng thanh toán'])
            collected_amount = float(booking.get('Số tiền đã thu', 0))
            commission = float(booking.get('Hoa hồng', 0))
            collector = booking.get('Người thu tiền', '')
            
            # Calculate nights and daily rates
            nights = (checkout_date - checkin_date).days
            if nights <= 0:
                nights = 1
                
            daily_total = total_amount / nights
            daily_collected = collected_amount / nights
            daily_commission = commission / nights
            
            # Determine if this is collected or uncollected
            is_collected = collector in valid_collectors
            
            # Distribute across each day of stay
            current_date = checkin_date
            while current_date < checkout_date:
                date_str = current_date.strftime('%Y-%m-%d')
                month_str = current_date.strftime('%Y-%m')
                
                # Initialize daily data
                if date_str not in daily_revenue_data:
                    daily_revenue_data[date_str] = {
                        'date': date_str,
                        'month': month_str,
                        'total_amount': 0,
                        'collected_amount': 0,
                        'uncollected_amount': 0,
                        'commission': 0,
                        'guest_count': 0,
                        'collected_guest_count': 0,
                        'uncollected_guest_count': 0
                    }
                
                # Add daily amounts
                daily_revenue_data[date_str]['total_amount'] += daily_total
                daily_revenue_data[date_str]['commission'] += daily_commission
                daily_revenue_data[date_str]['guest_count'] += 1/nights  # Fractional guest per night
                
                if is_collected:
                    daily_revenue_data[date_str]['collected_amount'] += daily_total
                    daily_revenue_data[date_str]['collected_guest_count'] += 1/nights
                else:
                    daily_revenue_data[date_str]['uncollected_amount'] += daily_total
                    daily_revenue_data[date_str]['uncollected_guest_count'] += 1/nights
                
                current_date += timedelta(days=1)
        
        # Aggregate daily data to monthly
        for date_str, day_data in daily_revenue_data.items():
            month = day_data['month']
            
            if month not in monthly_summary:
                monthly_summary[month] = {
                    'month': month,
                    'total_amount': 0,
                    'collected_amount': 0,
                    'uncollected_amount': 0,
                    'commission': 0,
                    'guest_nights': 0,
                    'collected_guest_nights': 0,
                    'uncollected_guest_nights': 0
                }
            
            monthly_summary[month]['total_amount'] += day_data['total_amount']
            monthly_summary[month]['collected_amount'] += day_data['collected_amount']
            monthly_summary[month]['uncollected_amount'] += day_data['uncollected_amount']
            monthly_summary[month]['commission'] += day_data['commission']
            monthly_summary[month]['guest_nights'] += day_data['guest_count']
            monthly_summary[month]['collected_guest_nights'] += day_data['collected_guest_count']
            monthly_summary[month]['uncollected_guest_nights'] += day_data['uncollected_guest_count']
        
        result['daily_distribution_method'] = {
            'daily_data': daily_revenue_data,
            'monthly_summary': list(monthly_summary.values())
        }
        
        # ==================== COMPARISON SUMMARY ====================
        print("🔍 [DUAL_METHOD] Creating comparison summary...")
        
        comparison = {
            'total_bookings_processed': len(df_valid),
            'method_differences': [],
            'recommended_usage': {
                'traditional': 'Use for payment collection tracking, current dashboard displays',
                'daily_distribution': 'Use for accurate monthly revenue reports, calendar integration'
            }
        }
        
        # Compare monthly totals between methods
        traditional_months = set()
        if not traditional_collected.empty:
            traditional_months.update(traditional_collected['Tháng'].tolist())
        if not traditional_uncollected.empty:
            traditional_months.update(traditional_uncollected['Tháng'].tolist())
        
        daily_months = set([m['month'] for m in monthly_summary.values()])
        
        for month in traditional_months.union(daily_months):
            # Get traditional method total
            trad_collected = traditional_collected[traditional_collected['Tháng'] == month]['Tổng thanh toán'].sum() if not traditional_collected.empty else 0
            trad_uncollected = traditional_uncollected[traditional_uncollected['Tháng'] == month]['Tổng thanh toán'].sum() if not traditional_uncollected.empty else 0
            trad_total = trad_collected + trad_uncollected
            
            # Get daily distribution total
            daily_total = monthly_summary.get(month, {}).get('total_amount', 0)
            
            difference = abs(trad_total - daily_total)
            difference_percent = (difference / max(trad_total, daily_total) * 100) if max(trad_total, daily_total) > 0 else 0
            
            comparison['method_differences'].append({
                'month': month,
                'traditional_total': trad_total,
                'daily_distribution_total': daily_total,
                'difference_amount': difference,
                'difference_percent': difference_percent
            })
        
        result['comparison_summary'] = comparison
        
        print(f"✅ [DUAL_METHOD] Complete. Processed {len(df_valid)} bookings")
        print(f"📊 [DUAL_METHOD] Traditional months: {len(traditional_months)}, Daily distribution months: {len(daily_months)}")
        
        return result
        
    except Exception as e:
        print(f"❌ [DUAL_METHOD] Error: {e}")
        return result

def get_daily_revenue_by_stay(df):
    """Calculate daily revenue by dividing total booking amount by stay duration
    Returns both total revenue and revenue minus commission"""
    daily_revenue = {}
    
    try:
        if df.empty:
            print("🚨 [REVENUE_DEBUG] DataFrame is empty!")
            return daily_revenue
        
        print(f"🔍 [REVENUE_DEBUG] Processing {len(df)} bookings for daily revenue")
            
        today = datetime.today()
        check_start = today - timedelta(days=30)  # 30 days ago
        check_end = today + timedelta(days=60)    # 60 days ahead
        
        df_clean = df.copy()
        
        # Parse dates
        df_clean['Check-in Date'] = pd.to_datetime(df_clean['Check-in Date'], errors='coerce', dayfirst=True)
        df_clean['Check-out Date'] = pd.to_datetime(df_clean['Check-out Date'], errors='coerce', dayfirst=True)
        
        # Filter valid bookings - FIXED: Include bookings that overlap with our date range
        valid_bookings = df_clean[
            (df_clean['Check-in Date'].notna()) &
            (df_clean['Check-out Date'].notna()) &
            (df_clean['Check-in Date'] <= pd.Timestamp(check_end)) &  # Check-in before end date
            (df_clean['Check-out Date'] >= pd.Timestamp(check_start)) &  # Check-out after start date  
            (df_clean['Tình trạng'] != 'Đã hủy') &
            (df_clean['Tổng thanh toán'].notna()) &
            (df_clean['Tổng thanh toán'] > 0)
        ].copy()
        
        print(f"🔧 [REVENUE_FIX] Date range: {check_start.date()} to {check_end.date()}")
        print(f"🔧 [REVENUE_FIX] Previous filter would exclude long-stay guests!")
        print(f"🔧 [REVENUE_FIX] New logic: Include bookings that OVERLAP with date range")
        
        if valid_bookings.empty:
            print("🚨 [REVENUE_DEBUG] No valid bookings found after filtering!")
            return daily_revenue
        
        print(f"🎯 [REVENUE_DEBUG] Found {len(valid_bookings)} valid bookings to process")
        
        # Debug: Show sample bookings for July 1-7 to understand the data
        july_early_bookings = valid_bookings[
            (valid_bookings['Check-in Date'] <= pd.Timestamp('2025-07-07')) &
            (valid_bookings['Check-out Date'] >= pd.Timestamp('2025-07-01'))
        ]
        print(f"📅 [JULY_1_7_DEBUG] Found {len(july_early_bookings)} bookings overlapping July 1-7:")
        for idx, booking in july_early_bookings.head(10).iterrows():
            guest_name = booking.get('Tên người đặt', 'N/A')
            checkin = booking['Check-in Date'].date()
            checkout = booking['Check-out Date'].date()  
            total = booking.get('Tổng thanh toán', 0)
            commission = booking.get('Hoa hồng', 0)
            print(f"  - {guest_name}: {checkin} to {checkout}, {total:,.0f}đ (commission: {commission:,.0f}đ)")
        
        for _, booking in valid_bookings.iterrows():
            checkin_date = booking['Check-in Date'].date()
            checkout_date = booking['Check-out Date'].date()
            total_amount = float(booking['Tổng thanh toán'])
            
            # Get commission amount - enhanced validation for imported data
            commission_amount = 0
            try:
                commission_raw = booking.get('Hoa hồng', 0)
                if commission_raw is not None:
                    commission_str = str(commission_raw).strip().lower()
                    if commission_str not in ['', 'nan', 'none', 'null', 'n/a', '0', '0.0']:
                        commission_amount = float(commission_raw)
                        if commission_amount < 0:  # Ensure non-negative commission
                            commission_amount = 0
            except (ValueError, TypeError):
                commission_amount = 0
            
            # Calculate revenue minus commission
            revenue_minus_commission = total_amount - commission_amount
            
            # Calculate number of nights
            nights = (checkout_date - checkin_date).days
            if nights <= 0:
                nights = 1  # Minimum 1 night
            
            # Calculate daily rates
            daily_rate_total = total_amount / nights
            daily_rate_minus_commission = revenue_minus_commission / nights
            
            # Add daily rate to each date in the stay
            current_date = checkin_date
            while current_date < checkout_date:
                if current_date not in daily_revenue:
                    daily_revenue[current_date] = {
                        'daily_total': 0,
                        'daily_total_minus_commission': 0,
                        'total_commission': 0,
                        'guest_count': 0,
                        'bookings': []
                    }
                
                # Add to daily totals
                daily_revenue[current_date]['daily_total'] += daily_rate_total
                daily_revenue[current_date]['daily_total_minus_commission'] += daily_rate_minus_commission
                daily_revenue[current_date]['total_commission'] += commission_amount / nights
                daily_revenue[current_date]['guest_count'] += 1
                daily_revenue[current_date]['bookings'].append({
                    'guest_name': booking.get('Tên người đặt', 'N/A'),
                    'booking_id': booking.get('Số đặt phòng', 'N/A'),
                    'daily_amount': daily_rate_total,
                    'daily_amount_minus_commission': daily_rate_minus_commission,
                    'commission_amount': commission_amount,
                    'total_amount': total_amount,
                    'nights': nights,
                    'checkin': checkin_date,
                    'checkout': checkout_date
                })
                
                current_date += timedelta(days=1)
        
        # Performance and accuracy metrics
        total_revenue_calculated = sum([day['daily_total'] for day in daily_revenue.values()])
        total_commission_calculated = sum([day['total_commission'] for day in daily_revenue.values()])
        total_days_with_revenue = len([day for day in daily_revenue.values() if day['daily_total'] > 0])
        
        print(f"✅ OPTIMIZED DAILY REVENUE CALCULATION COMPLETE:")
        print(f"   📅 Total dates processed: {len(daily_revenue)}")
        print(f"   💰 Total revenue distributed: {total_revenue_calculated:,.0f}đ")
        print(f"   🏷️ Total commission distributed: {total_commission_calculated:,.0f}đ")
        print(f"   📊 Days with revenue: {total_days_with_revenue}")
        print(f"   🎯 Per-night distribution: ACTIVE (fixes arrival-only revenue bug)")
        
        # Debug specific dates mentioned by user
        july_1 = datetime(2025, 7, 1).date()
        july_5 = datetime(2025, 7, 5).date()
        july_7 = datetime(2025, 7, 7).date()
        july_10 = datetime(2025, 7, 10).date()
        july_15 = datetime(2025, 7, 15).date()
        
        for debug_date in [july_1, july_5, july_7, july_10, july_15]:
            if debug_date in daily_revenue:
                guest_count = daily_revenue[debug_date]['guest_count']
                total_revenue = daily_revenue[debug_date]['daily_total']
                print(f"🎯 [DATE_DEBUG] {debug_date}: {guest_count} guests, {total_revenue:,.0f}đ")
                
                # Show individual bookings for problem dates
                if debug_date in [july_1, july_5, july_7]:
                    bookings = daily_revenue[debug_date]['bookings']
                    print(f"  📋 [BOOKING_LIST] {len(bookings)} bookings on {debug_date}:")
                    for booking in bookings[:5]:  # Show first 5
                        print(f"    - {booking['guest_name']}: {booking['daily_amount']:,.0f}đ")
            else:
                print(f"❌ [DATE_DEBUG] {debug_date}: NO DATA")
        
    except Exception as e:
        print(f"Error calculating daily revenue by stay: {e}")
        import traceback
        traceback.print_exc()
    
    return daily_revenue


def create_collector_chart(dashboard_data):
    """✅ ENHANCED: Tạo biểu đồ donut chart cho người thu tiền với validation chi tiết"""
    collector_revenue_data = safe_to_dict_records(dashboard_data.get('collector_revenue_selected', pd.DataFrame()))
    
    # Enhanced validation and logging
    print(f"📊 [COLLECTOR_CHART] Processing {len(collector_revenue_data)} collector records")
    print(f"📊 [COLLECTOR_CHART] NOTE: This chart shows FILTERED PERIOD data only")
    print(f"📊 [COLLECTOR_CHART] Monthly table shows ALL months with per-month accuracy")
    
    # Debug the actual data received
    if collector_revenue_data:
        total_chart_revenue = sum(record.get('Tổng thanh toán', 0) for record in collector_revenue_data)
        print(f"📊 [COLLECTOR_CHART_DEBUG] Total revenue in collector data: {total_chart_revenue:,.0f}đ")
        for record in collector_revenue_data:
            collector = record.get('Người thu tiền', 'Unknown')
            amount = record.get('Tổng thanh toán', 0)
            count = record.get('Số đặt phòng', 0)
            print(f"📊 [COLLECTOR_CHART_DEBUG]   {collector}: {amount:,.0f}đ ({count} bookings)")
    
    if not collector_revenue_data:
        print(f"⚠️ [COLLECTOR_CHART] No collector data found - showing empty chart")
        return {
            'data': [],
            'layout': {
                'title': {'text': '💰 Không có dữ liệu người thu', 'x': 0.5, 'y': 0.5,
                         'font': {'size': 16, 'family': 'Arial Bold', 'color': '#e74c3c'}},
                'showlegend': False, 'height': 300,
                'annotations': [{
                    'text': '<b>Không có dữ liệu</b><br>cho khoảng thời gian này',
                    'x': 0.5, 'y': 0.5,
                    'font': {'size': 14, 'family': 'Arial Bold', 'color': '#e74c3c'},
                    'showarrow': False
                }]
            }
        }
    
    # Process and validate data
    valid_data = []
    total_amount = 0
    
    for row in collector_revenue_data:
        collector_name = row.get('Người thu tiền', 'Unknown')
        amount = float(row.get('Tổng thanh toán', 0))
        bookings = int(row.get('Số đặt phòng', 0))
        commission = float(row.get('Hoa hồng', 0))
        percentage = float(row.get('Tỷ lệ %', 0))
        
        if amount > 0:  # Only include collectors with actual revenue
            valid_data.append({
                'name': collector_name,
                'amount': amount,
                'bookings': bookings,
                'commission': commission,
                'percentage': percentage
            })
            total_amount += amount
            print(f"📊 [COLLECTOR_CHART] {collector_name}: {amount:,.0f}đ ({bookings} bookings, {percentage}%)")
    
    if not valid_data:
        print(f"⚠️ [COLLECTOR_CHART] No valid collector amounts found")
        return {'data': [], 'layout': {'title': {'text': '💰 Không có dữ liệu hợp lệ'}}}
    
    # Debug: Log what we're sending to frontend
    chart_total = sum(item['amount'] for item in valid_data)
    print(f"📊 [COLLECTOR_CHART_FRONTEND] Sending to frontend: {chart_total:,.0f}đ")
    for item in valid_data:
        print(f"📊 [COLLECTOR_CHART_FRONTEND]   {item['name']}: {item['amount']:,.0f}đ")
    
    # Enhanced chart with detailed hover information
    return {
        'data': [{
            'type': 'pie',
            'labels': [item['name'] for item in valid_data],
            'values': [item['amount'] for item in valid_data],
            'textinfo': 'label+value', 'textposition': 'auto',
            'hovertemplate': '<b>%{label}</b><br>' +
                           'Doanh thu: %{value:,.0f}đ<br>' +
                           'Tỷ lệ: %{percent}<br>' +
                           f'Số đặt phòng: %{{customdata[0]}}<br>' +
                           f'Hoa hồng: %{{customdata[1]:,.0f}}đ<br>' +
                           '<extra></extra>',
            'customdata': [[item['bookings'], item['commission']] for item in valid_data],
            'texttemplate': '%{label}<br>%{value:,.0f}đ<br>%{percent}',
            'marker': {
                'colors': ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c'],
                'line': {'color': '#ffffff', 'width': 3}
            },
            'hole': 0.4,
            'textfont': {'size': 11, 'family': 'Arial Bold', 'color': '#2c3e50'},
            'pull': [0.05 if i == 0 else 0 for i in range(len(valid_data))]
        }],
        'layout': {
            'title': {'text': '💰 Revenue by Collector (Details)', 'x': 0.5, 'y': 0.95,
                     'font': {'size': 14, 'family': 'Arial Bold', 'color': '#2c3e50'}},
            'showlegend': True, 'height': 320,
            'legend': {'orientation': 'v', 'x': 1.05, 'y': 0.5,
                      'font': {'size': 11, 'family': 'Arial', 'color': '#2c3e50'}},
            'margin': {'l': 20, 'r': 140, 't': 50, 'b': 20},
            'plot_bgcolor': 'rgba(248,249,250,0.8)', 'paper_bgcolor': 'rgba(0,0,0,0)',
            'font': {'family': 'Arial, sans-serif', 'size': 11, 'color': '#2c3e50'},
            'annotations': [{
                'text': f'<b>Total revenue</b><br>{total_amount:,.0f}đ<br><small>({len(valid_data)} collectors)</small>',
                'x': 0.5, 'y': 0.5,
                'font': {'size': 13, 'family': 'Arial Bold', 'color': '#2c3e50'},
                'showarrow': False
            }]
        }
    }


def process_arrival_notifications(df):
    """
    Xử lý thông báo khách đến - chỉ hiển thị khách đến hôm nay và ngày mai
    UPDATED: Exclude cancelled guests from notifications completely
    """
    try:
        if df.empty:
            return []
        
        # Ngày hôm nay và ngày mai
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        notifications = []
        
        # Lọc khách check-in - chỉ xử lý khách đến từ hôm nay trở đi
        for index, row in df.iterrows():
            try:
                # CRITICAL FIX: Skip cancelled guests completely
                booking_status = row.get('Tình trạng', 'OK')
                if booking_status == 'Đã hủy':
                    continue  # Skip cancelled guests entirely
                
                checkin_date = row.get('Check-in Date')
                if checkin_date:
                    # Xử lý nhiều định dạng ngày
                    if isinstance(checkin_date, str):
                        try:
                            checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                checkin_date = datetime.strptime(checkin_date, '%d/%m/%Y').date()
                            except ValueError:
                                continue
                    elif hasattr(checkin_date, 'date'):
                        checkin_date = checkin_date.date()
                    
                    # Bỏ qua khách đã check-in trước hôm nay
                    if checkin_date < today:
                        continue
                    
                    # Khách đến ngày mai
                    if checkin_date == tomorrow:
                        guest_name = row.get('Tên người đặt', 'Không có tên')
                        booking_id = row.get('Số đặt phòng', 'N/A')
                        total_amount = row.get('Tổng thanh toán', 0)
                        
                        # Enhanced commission processing
                        hoa_hong = 0
                        try:
                            commission_raw = row.get('Hoa hồng', 0)
                            if commission_raw is not None and str(commission_raw).strip() not in ['', 'nan', 'None', 'N/A']:
                                hoa_hong = float(commission_raw)
                        except (ValueError, TypeError):
                            hoa_hong = 0
                        
                        # Determine commission level and priority
                        commission_level = 'none'
                        commission_priority = 'high'
                        if hoa_hong > 150000:
                            commission_level = 'high'
                            commission_priority = 'critical'
                        elif hoa_hong > 0:
                            commission_level = 'normal'
                            commission_priority = 'high'
                        
                        # Check arrival confirmation status from database
                        arrival_confirmed = False
                        try:
                            from core.models import Booking
                            booking = Booking.query.get(booking_id)
                            if booking:
                                arrival_confirmed = booking.arrival_confirmed or False
                        except:
                            arrival_confirmed = False
                        
                        # Build message (no cancellation status needed since cancelled guests are excluded)
                        message = f'Khách {guest_name} sẽ đến vào ngày mai ({checkin_date.strftime("%d/%m/%Y")})'
                        
                        notifications.append({
                            'type': 'arrival',
                            'priority': commission_priority,
                            'guest_name': guest_name,
                            'booking_id': booking_id,
                            'checkin_date': checkin_date.strftime('%d/%m/%Y'),
                            'total_amount': total_amount,
                            'Hoa hồng': hoa_hong,
                            'commission_level': commission_level,
                            'days_until': 1,
                            'arrival_confirmed': arrival_confirmed,
                            'is_cancelled': False,  # Always false since cancelled guests are excluded
                            'booking_status': booking_status,
                            'message': message
                        })
                    
                    # Khách đến hôm nay
                    elif checkin_date == today:
                        guest_name = row.get('Tên người đặt', 'Không có tên')
                        booking_id = row.get('Số đặt phòng', 'N/A')
                        total_amount = row.get('Tổng thanh toán', 0)
                        
                        # Enhanced commission processing
                        hoa_hong = 0
                        try:
                            commission_raw = row.get('Hoa hồng', 0)
                            if commission_raw is not None and str(commission_raw).strip() not in ['', 'nan', 'None', 'N/A']:
                                hoa_hong = float(commission_raw)
                        except (ValueError, TypeError):
                            hoa_hong = 0
                        
                        # Determine commission level and priority
                        commission_level = 'none'
                        commission_priority = 'urgent'
                        if hoa_hong > 150000:
                            commission_level = 'high'
                            commission_priority = 'critical'
                        elif hoa_hong > 0:
                            commission_level = 'normal'
                            commission_priority = 'urgent'
                        
                        # Check arrival confirmation status from database
                        arrival_confirmed = False
                        try:
                            from core.models import Booking
                            booking = Booking.query.get(booking_id)
                            if booking:
                                arrival_confirmed = booking.arrival_confirmed or False
                        except:
                            arrival_confirmed = False
                        
                        # Build message (no cancellation status needed since cancelled guests are excluded)
                        message = f'Khách {guest_name} đến HÔM NAY ({checkin_date.strftime("%d/%m/%Y")})'
                        
                        notifications.append({
                            'type': 'arrival',
                            'priority': commission_priority,
                            'guest_name': guest_name,
                            'booking_id': booking_id,
                            'checkin_date': checkin_date.strftime('%d/%m/%Y'),
                            'total_amount': total_amount,
                            'Hoa hồng': hoa_hong,
                            'commission_level': commission_level,
                            'days_until': 0,
                            'arrival_confirmed': arrival_confirmed,
                            'is_cancelled': False,  # Always false since cancelled guests are excluded
                            'booking_status': booking_status,
                            'message': message
                        })
                        
            except Exception as e:
                print(f"Error processing arrival for row {index}: {e}")
                continue
        
        # Enhanced sorting: Critical commission guests first, then by days_until, then by commission amount
        def sort_priority(notification):
            priority_order = {'critical': 0, 'urgent': 1, 'high': 2}
            commission_order = {'high': 0, 'normal': 1, 'none': 2}
            return (
                priority_order.get(notification['priority'], 3),
                notification['days_until'],
                commission_order.get(notification['commission_level'], 3),
                -notification.get('Hoa hồng', 0),  # Negative for descending order
                notification['guest_name']
            )
        
        notifications.sort(key=sort_priority)
        
        return notifications
        
    except Exception as e:
        print(f"Error in process_arrival_notifications: {e}")
        return []


def process_departure_notifications(df):
    """
    Xử lý thông báo khách đi - hiển thị 1 ngày trước để chuẩn bị taxi/dịch vụ
    UPDATED: Exclude cancelled guests from notifications completely
    """
    try:
        if df.empty:
            return []
        
        # Ngày hôm nay và ngày mai
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        notifications = []
        
        # Lọc khách check-out ngày mai (để chuẩn bị dịch vụ)
        for index, row in df.iterrows():
            try:
                # CRITICAL FIX: Skip cancelled guests completely
                booking_status = row.get('Tình trạng', 'OK')
                if booking_status == 'Đã hủy':
                    continue  # Skip cancelled guests entirely
                
                checkout_date = row.get('Check-out Date')
                if checkout_date:
                    # Xử lý nhiều định dạng ngày
                    if isinstance(checkout_date, str):
                        try:
                            checkout_date = datetime.strptime(checkout_date, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                checkout_date = datetime.strptime(checkout_date, '%d/%m/%Y').date()
                            except ValueError:
                                continue
                    elif hasattr(checkout_date, 'date'):
                        checkout_date = checkout_date.date()
                    
                    # Khách đi ngày mai
                    if checkout_date == tomorrow:
                        guest_name = row.get('Tên người đặt', 'Không có tên')
                        booking_id = row.get('Số đặt phòng', 'N/A')
                        total_amount = row.get('Tổng thanh toán', 0)
                        
                        # Enhanced commission processing
                        hoa_hong = 0
                        try:
                            commission_raw = row.get('Hoa hồng', 0)
                            if commission_raw is not None and str(commission_raw).strip() not in ['', 'nan', 'None', 'N/A']:
                                hoa_hong = float(commission_raw)
                        except (ValueError, TypeError):
                            hoa_hong = 0
                        
                        # Determine commission level
                        commission_level = 'none'
                        if hoa_hong > 150000:
                            commission_level = 'high'
                        elif hoa_hong > 0:
                            commission_level = 'normal'
                        
                        # Build message (no cancellation status needed since cancelled guests are excluded)
                        message = f'Khách {guest_name} sẽ đi vào ngày mai ({checkout_date.strftime("%d/%m/%Y")}) - Chuẩn bị taxi/dịch vụ'
                        
                        notifications.append({
                            'type': 'departure',
                            'priority': 'high',
                            'guest_name': guest_name,
                            'booking_id': booking_id,
                            'checkout_date': checkout_date.strftime('%d/%m/%Y'),
                            'total_amount': total_amount,
                            'Hoa hồng': hoa_hong,
                            'commission_level': commission_level,
                            'days_until': 1,
                            'is_cancelled': False,  # Always false since cancelled guests are excluded
                            'booking_status': booking_status,
                            'message': message
                        })
                    
                    # Khách đi hôm nay
                    elif checkout_date == today:
                        guest_name = row.get('Tên người đặt', 'Không có tên')
                        booking_id = row.get('Số đặt phòng', 'N/A')
                        total_amount = row.get('Tổng thanh toán', 0)
                        
                        # Enhanced commission processing
                        hoa_hong = 0
                        try:
                            commission_raw = row.get('Hoa hồng', 0)
                            if commission_raw is not None and str(commission_raw).strip() not in ['', 'nan', 'None', 'N/A']:
                                hoa_hong = float(commission_raw)
                        except (ValueError, TypeError):
                            hoa_hong = 0
                        
                        # Determine commission level
                        commission_level = 'none'
                        if hoa_hong > 150000:
                            commission_level = 'high'
                        elif hoa_hong > 0:
                            commission_level = 'normal'
                        
                        # Build message (no cancellation status needed since cancelled guests are excluded)
                        message = f'Khách {guest_name} đi HÔM NAY ({checkout_date.strftime("%d/%m/%Y")}) - Hỗ trợ taxi ngay'
                        
                        notifications.append({
                            'type': 'departure',
                            'priority': 'urgent',
                            'guest_name': guest_name,
                            'booking_id': booking_id,
                            'checkout_date': checkout_date.strftime('%d/%m/%Y'),
                            'total_amount': total_amount,
                            'Hoa hồng': hoa_hong,
                            'commission_level': commission_level,
                            'days_until': 0,
                            'is_cancelled': False,  # Always false since cancelled guests are excluded
                            'booking_status': booking_status,
                            'message': message
                        })
                        
            except Exception as e:
                print(f"Error processing departure for row {index}: {e}")
                continue
        
        # Sắp xếp theo độ ưu tiên
        notifications.sort(key=lambda x: (x['days_until'], x['guest_name']))
        
        return notifications
        
    except Exception as e:
        print(f"Error in process_departure_notifications: {e}")
        return []
