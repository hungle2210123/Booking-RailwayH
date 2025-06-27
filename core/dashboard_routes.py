# dashboard_routes.py - Dashboard logic module
from flask import render_template, request
from datetime import datetime, timedelta
import calendar
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import warnings

def safe_to_dict_records(df):
    """
    Safely convert DataFrame to dict records, handling duplicate columns
    """
    if df.empty:
        return []
    
    try:
        # Check for duplicate columns and clean if necessary
        if df.columns.duplicated().any():
            print("WARNING: DataFrame has duplicate columns, cleaning...")
            # Keep only the first occurrence of each column
            df = df.loc[:, ~df.columns.duplicated()]
            
        # Suppress the warning temporarily
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="DataFrame columns are not unique")
            return df.to_dict('records')
    except Exception as e:
        print(f"Error in safe_to_dict_records: {e}")
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
    monthly_revenue_with_unpaid = process_monthly_revenue_with_unpaid(df)
    
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
        
        # Add trend line
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
        
        # Enhanced layout for strategic management
        fig.update_layout(
            title={
                'text': f'📊 Phân tích Doanh thu Chiến lược theo Tháng<br>' +
                        f'<sub>TB: {avg_revenue:,.0f}đ | Cao nhất: {max_revenue:,.0f}đ | Thấp nhất: {min_revenue:,.0f}đ</sub>',
                'x': 0.5,
                'font': {'size': 16, 'family': 'Arial Black', 'color': '#2c3e50'}
            },
            xaxis=dict(
                title='Tháng',
                titlefont=dict(size=14, family='Arial Black'),
                tickfont=dict(size=12),
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.1)'
            ),
            yaxis=dict(
                title='Doanh thu (VND)',
                titlefont=dict(size=14, family='Arial Black'),
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
            return overdue_unpaid_guests, overdue_total_amount
            
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
        
        if not overdue_df.empty:
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


def process_monthly_revenue_with_unpaid(df, start_date=None, end_date=None):
    """Xử lý doanh thu theo tháng bao gồm khách chưa thu và hoa hồng - HIỂN THỊ TẤT CẢ THÁNG"""
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
        
        print(f"🏨 [CHECKED_IN_FILTER] Total bookings: {len(df_period)}, Checked-in only: {len(df_checked_in)}")
        print(f"🏨 [CHECKED_IN_FILTER] Excluded future arrivals: {len(df_period) - len(df_checked_in)} guests")
        
        # ✅ ENHANCED DEBUGGING: Analyze collector data before processing
        print(f"🔍 [COLLECTOR_DEBUG] Analyzing collector distribution in checked-in guests:")
        if 'Người thu tiền' in df_checked_in.columns:
            collector_counts = df_checked_in['Người thu tiền'].value_counts(dropna=False)
            collector_revenue = df_checked_in.groupby('Người thu tiền', dropna=False)['Tổng thanh toán'].sum()
            
            print(f"🔍 [COLLECTOR_DEBUG] All collectors found:")
            total_all_collectors = 0
            for collector, count in collector_counts.items():
                revenue = collector_revenue.get(collector, 0)
                total_all_collectors += revenue
                # Show exact string representation for debugging
                repr_collector = repr(collector)
                is_valid = collector in ['LOC LE', 'THAO LE']
                status = "✅" if is_valid else "❌"
                print(f"🔍   {repr_collector}: {count} guests, {revenue:,.0f}đ {status}")
            
            print(f"🔍 [COLLECTOR_DEBUG] Total revenue from ALL collectors: {total_all_collectors:,.0f}đ")
        
        # Tính doanh thu đã thu và chưa thu (ONLY for checked-in guests with EXACT validation)
        valid_collectors = ['LOC LE', 'THAO LE']
        
        # Use strict string matching with validation
        collected_mask = df_checked_in['Người thu tiền'].isin(valid_collectors)
        collected_df = df_checked_in[collected_mask].copy()
        uncollected_df = df_checked_in[~collected_mask].copy()
        
        print(f"💰 [COLLECTION_BREAKDOWN] LOC LE + THAO LE collected: {len(collected_df)} guests")
        print(f"💰 [COLLECTION_BREAKDOWN] Others/Uncollected: {len(uncollected_df)} guests")
        print(f"💰 [COLLECTION_BREAKDOWN] Collected revenue: {collected_df['Tổng thanh toán'].sum():,.0f}đ")
        print(f"💰 [COLLECTION_BREAKDOWN] Uncollected revenue: {uncollected_df['Tổng thanh toán'].sum():,.0f}đ")
        
        # ✅ CRITICAL DEBUG: Find the exact discrepancy
        print(f"🔍 [DISCREPANCY_DEBUG] Analyzing who is counted as 'collected'...")
        
        if not collected_df.empty:
            # Show all unique collectors in "collected" data
            unique_collectors_in_collected = collected_df['Người thu tiền'].value_counts()
            print(f"🔍 [DISCREPANCY_DEBUG] All collectors in 'collected' dataset:")
            
            total_in_collected = 0
            for collector, count in unique_collectors_in_collected.items():
                amount = collected_df[collected_df['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
                total_in_collected += amount
                is_valid = collector in ['LOC LE', 'THAO LE']
                status = "✅ VALID" if is_valid else "❌ INVALID - CAUSING DISCREPANCY"
                print(f"🔍   '{collector}': {count} guests, {amount:,.0f}đ {status}")
            
            print(f"🔍 [DISCREPANCY_DEBUG] Total found in 'collected': {total_in_collected:,.0f}đ")
            
            # Calculate only valid collectors
            loc_le_amount = collected_df[collected_df['Người thu tiền'] == 'LOC LE']['Tổng thanh toán'].sum()
            thao_le_amount = collected_df[collected_df['Người thu tiền'] == 'THAO LE']['Tổng thanh toán'].sum()
            valid_total = loc_le_amount + thao_le_amount
            discrepancy = total_in_collected - valid_total
            
            print(f"💰 [MONTHLY_BREAKDOWN] LOC LE: {loc_le_amount:,.0f}đ")
            print(f"💰 [MONTHLY_BREAKDOWN] THAO LE: {thao_le_amount:,.0f}đ")
            print(f"💰 [VALID_TOTAL] Valid collectors only: {valid_total:,.0f}đ")
            print(f"🚨 [DISCREPANCY] Extra amount from invalid collectors: {discrepancy:,.0f}đ")
            print(f"💰 [SHOULD_MATCH] Collector chart should show: {valid_total:,.0f}đ")
        
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
                    merged_data.at[idx, 'Tổng hoa hồng'] = round(total_commission, 0)  # ✅ FIXED: Use total commission, not average
                    
                    print(f"📊 [DETAILED_STATS] {month}: {total_guests} guests, {collected_guests} collected, avg {avg_spending:,.0f}đ/guest")
                    
                    # ✅ MONEY VERIFICATION: Show exact amounts for this specific month
                    month_collected_amount = month_guests[month_guests['Người thu tiền'].isin(['LOC LE', 'THAO LE'])]['Tổng thanh toán'].sum()
                    month_uncollected_amount = month_guests[~month_guests['Người thu tiền'].isin(['LOC LE', 'THAO LE'])]['Tổng thanh toán'].sum()
                    
                    month_loc_le = month_guests[month_guests['Người thu tiền'] == 'LOC LE']['Tổng thanh toán'].sum()
                    month_thao_le = month_guests[month_guests['Người thu tiền'] == 'THAO LE']['Tổng thanh toán'].sum()
                    
                    print(f"💰 [MONTH_VERIFICATION] {month}:")
                    print(f"💰   LOC LE: {month_loc_le:,.0f}đ")
                    print(f"💰   THAO LE: {month_thao_le:,.0f}đ")  
                    print(f"💰   Collected: {month_collected_amount:,.0f}đ")
                    print(f"💰   Uncollected: {month_uncollected_amount:,.0f}đ")
                    print(f"💰   Total: {month_collected_amount + month_uncollected_amount:,.0f}đ")
            
            merged_data = merged_data.sort_values('Tháng')
            monthly_revenue_with_unpaid = safe_to_dict_records(merged_data)
            
            # ✅ MONEY ACCURACY SUMMARY
            print(f"📋 [MONTHLY_SUMMARY] Generated table with {len(monthly_revenue_with_unpaid)} months")
            for row in monthly_revenue_with_unpaid:
                month = row.get('Tháng')
                collected = row.get('Đã thu', 0)
                uncollected = row.get('Chưa thu', 0)
                total = collected + uncollected
                print(f"📋   {month}: Collected={collected:,.0f}đ, Uncollected={uncollected:,.0f}đ, Total={total:,.0f}đ")
    
    except Exception as e:
        print(f"Process monthly revenue error: {e}")
        import traceback
        traceback.print_exc()
    
    return monthly_revenue_with_unpaid

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
    """Phát hiện ngày có quá 4 khách check-in"""
    overcrowded_days = []
    
    try:
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
        
        # Find overcrowded dates (>4 guests)
        overcrowded_dates = daily_checkins[daily_checkins['guest_count'] > 4]
        
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


def get_daily_revenue_by_stay(df):
    """Calculate daily revenue by dividing total booking amount by stay duration
    Returns both total revenue and revenue minus commission"""
    daily_revenue = {}
    
    try:
        if df.empty:
            return daily_revenue
            
        today = datetime.today()
        check_start = today - timedelta(days=30)  # 30 days ago
        check_end = today + timedelta(days=60)    # 60 days ahead
        
        df_clean = df.copy()
        
        # Parse dates
        df_clean['Check-in Date'] = pd.to_datetime(df_clean['Check-in Date'], errors='coerce', dayfirst=True)
        df_clean['Check-out Date'] = pd.to_datetime(df_clean['Check-out Date'], errors='coerce', dayfirst=True)
        
        # Filter valid bookings
        valid_bookings = df_clean[
            (df_clean['Check-in Date'].notna()) &
            (df_clean['Check-out Date'].notna()) &
            (df_clean['Check-in Date'] >= pd.Timestamp(check_start)) &
            (df_clean['Check-in Date'] <= pd.Timestamp(check_end)) &
            (df_clean['Tình trạng'] != 'Đã hủy') &
            (df_clean['Tổng thanh toán'].notna()) &
            (df_clean['Tổng thanh toán'] > 0)
        ].copy()
        
        if valid_bookings.empty:
            return daily_revenue
        
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
            'title': {'text': '💰 Doanh thu theo Người thu (Chi tiết)', 'x': 0.5, 'y': 0.95,
                     'font': {'size': 14, 'family': 'Arial Bold', 'color': '#2c3e50'}},
            'showlegend': True, 'height': 320,
            'legend': {'orientation': 'v', 'x': 1.05, 'y': 0.5,
                      'font': {'size': 11, 'family': 'Arial', 'color': '#2c3e50'}},
            'margin': {'l': 20, 'r': 140, 't': 50, 'b': 20},
            'plot_bgcolor': 'rgba(248,249,250,0.8)', 'paper_bgcolor': 'rgba(0,0,0,0)',
            'font': {'family': 'Arial, sans-serif', 'size': 11, 'color': '#2c3e50'},
            'annotations': [{
                'text': f'<b>Tổng thu</b><br>{total_amount:,.0f}đ<br><small>({len(valid_data)} người thu)</small>',
                'x': 0.5, 'y': 0.5,
                'font': {'size': 13, 'family': 'Arial Bold', 'color': '#2c3e50'},
                'showarrow': False
            }]
        }
    }


def process_arrival_notifications(df):
    """
    Xử lý thông báo khách đến - chỉ hiển thị khách đến hôm nay và ngày mai
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
                            'message': f'Khách {guest_name} sẽ đến vào ngày mai ({checkin_date.strftime("%d/%m/%Y")})'
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
                            'message': f'Khách {guest_name} đến HÔM NAY ({checkin_date.strftime("%d/%m/%Y")})'
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
                            'message': f'Khách {guest_name} sẽ đi vào ngày mai ({checkout_date.strftime("%d/%m/%Y")}) - Chuẩn bị taxi/dịch vụ'
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
                            'message': f'Khách {guest_name} đi HÔM NAY ({checkout_date.strftime("%d/%m/%Y")}) - Hỗ trợ taxi ngay'
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
