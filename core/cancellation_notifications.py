"""
Hotel Booking System - Guest Cancellation Notification System
Professional implementation for tracking cancellation requirements
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .logic_postgresql import execute_query

def get_cancellation_notifications() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all guests requiring cancellation notifications
    Only shows guests who haven't reached checkout date yet
    Returns categorized cancellation alerts
    """
    
    query = """
    SELECT 
        b.booking_id,
        g.full_name as guest_name,
        b.checkin_date,
        b.checkout_date,
        b.room_amount,
        b.commission,
        b.booking_status,
        b.collector,
        COALESCE(b.collected_amount, 0) as collected_amount,
        b.booking_notes,
        b.created_at
    FROM bookings b
    JOIN guests g ON b.guest_id = g.guest_id
    WHERE b.booking_status != 'deleted'
    AND b.checkout_date >= CURRENT_DATE
    ORDER BY b.checkout_date ASC
    """
    
    df = execute_query(query)
    
    if df.empty:
        return {
            'specific_guest_alerts': [],
            'zero_commission_alerts': [],
            'cancellation_status_alerts': [],
            'summary': {'total_alerts': 0}
        }
    
    # Initialize notification categories
    notifications = {
        'specific_guest_alerts': [],
        'zero_commission_alerts': [],
        'cancellation_status_alerts': [],
        'summary': {'total_alerts': 0}
    }
    
    # 1. Specific Guest Alert: Le Thuong
    le_thuong_bookings = df[df['guest_name'].str.contains('Le Thuong', case=False, na=False)]
    for _, booking in le_thuong_bookings.iterrows():
        if booking['booking_status'].lower() not in ['cancelled', 'đã hủy']:
            notifications['specific_guest_alerts'].append({
                'type': 'specific_guest',
                'guest_name': booking['guest_name'],
                'booking_id': booking['booking_id'],
                'checkin_date': booking['checkin_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkin_date']) else '',
                'checkout_date': booking['checkout_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkout_date']) else '',
                'room_amount': float(booking['room_amount']) if pd.notna(booking['room_amount']) else 0,
                'status': booking['booking_status'],
                'message': f'🚨 CRITICAL: Guest "Le Thuong" needs cancellation on booking platform',
                'priority': 'high',
                'action_required': 'Cancel on booking app but guest may still stay'
            })
    
    # 2. Zero Commission Alerts (Private bookings)
    zero_commission_bookings = df[
        (df['commission'] == 0) & 
        (~df['booking_status'].str.lower().isin(['cancelled', 'đã hủy']))
    ]
    for _, booking in zero_commission_bookings.iterrows():
        notifications['zero_commission_alerts'].append({
            'type': 'zero_commission',
            'guest_name': booking['guest_name'],
            'booking_id': booking['booking_id'],
            'checkin_date': booking['checkin_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkin_date']) else '',
            'checkout_date': booking['checkout_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkout_date']) else '',
            'room_amount': float(booking['room_amount']) if pd.notna(booking['room_amount']) else 0,
            'commission': 0,
            'message': f'💼 Private Booking: Guest "{booking["guest_name"]}" - Zero commission indicates private booking',
            'priority': 'medium',
            'action_required': 'Cancel on booking app but guest still stays (private booking)'
        })
    
    # 3. Cancellation Status Alerts (Not staying) - Show ALL cancelled guests
    cancelled_bookings = df[df['booking_status'].str.lower().isin(['cancelled', 'đã hủy', 'cancel', 'hủy'])]
    for _, booking in cancelled_bookings.iterrows():
        notifications['cancellation_status_alerts'].append({
            'type': 'cancellation_status',
            'guest_name': booking['guest_name'],
            'booking_id': booking['booking_id'],
            'checkin_date': booking['checkin_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkin_date']) else '',
            'checkout_date': booking['checkout_date'].strftime('%Y-%m-%d') if pd.notna(booking['checkout_date']) else '',
            'room_amount': float(booking['room_amount']) if pd.notna(booking['room_amount']) else 0,
            'commission': float(booking['commission']) if pd.notna(booking['commission']) else 0,
            'status': booking['booking_status'],
            'message': f'❌ Cancelled: Guest "{booking["guest_name"]}" - Not staying',
            'priority': 'low',
            'action_required': 'Verify cancellation on booking platform (guest not staying)'
        })
    
    # Calculate summary
    total_alerts = (
        len(notifications['specific_guest_alerts']) +
        len(notifications['zero_commission_alerts']) +
        len(notifications['cancellation_status_alerts'])
    )
    
    notifications['summary'] = {
        'total_alerts': total_alerts,
        'high_priority': len(notifications['specific_guest_alerts']),
        'medium_priority': len(notifications['zero_commission_alerts']),
        'low_priority': len(notifications['cancellation_status_alerts']),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return notifications

def get_notification_badge_count() -> int:
    """Get total count for notification badge"""
    notifications = get_cancellation_notifications()
    return notifications['summary']['total_alerts']

def mark_notification_seen(booking_id: str, notification_type: str) -> bool:
    """Mark a specific notification as seen (for future enhancement)"""
    # TODO: Implement notification tracking table
    # For now, just return True
    return True

def get_urgent_cancellation_alerts() -> List[Dict[str, Any]]:
    """Get only urgent cancellation alerts for top-level dashboard display"""
    notifications = get_cancellation_notifications()
    
    urgent_alerts = []
    
    # High priority: Le Thuong alerts
    urgent_alerts.extend(notifications['specific_guest_alerts'])
    
    # Medium priority: Recent zero commission (limit to 3 most recent)
    recent_zero_commission = sorted(
        notifications['zero_commission_alerts'],
        key=lambda x: x['checkin_date'],
        reverse=True
    )[:3]
    urgent_alerts.extend(recent_zero_commission)
    
    return urgent_alerts

def debug_guest_data() -> Dict[str, Any]:
    """Debug function to check guest data and booking statuses"""
    query = """
    SELECT 
        b.booking_id,
        g.full_name as guest_name,
        b.checkin_date,
        b.checkout_date,
        b.room_amount,
        b.commission,
        b.booking_status,
        b.created_at
    FROM bookings b
    JOIN guests g ON b.guest_id = g.guest_id
    WHERE b.booking_status != 'deleted'
    ORDER BY b.created_at DESC
    LIMIT 20
    """
    
    df = execute_query(query)
    
    debug_info = {
        'total_bookings': len(df),
        'booking_statuses': df['booking_status'].value_counts().to_dict() if not df.empty else {},
        'sample_guests': df[['guest_name', 'booking_status', 'commission']].to_dict('records') if not df.empty else [],
        'le_thuong_bookings': df[df['guest_name'].str.contains('Le Thuong', case=False, na=False)].to_dict('records') if not df.empty else [],
        'zero_commission_count': len(df[df['commission'] == 0]) if not df.empty else 0,
        'cancelled_count': len(df[df['booking_status'].str.lower().isin(['cancelled', 'đã hủy', 'cancel', 'hủy'])]) if not df.empty else 0
    }
    
    return debug_info