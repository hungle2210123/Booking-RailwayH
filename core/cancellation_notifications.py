"""
Hotel Booking System - Guest Cancellation Notification System
Professional implementation for tracking cancellation requirements
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .logic_postgresql import execute_query

def _safe_date_format(date_value):
    """
    Safely format date values, handling NaT and various date types
    """
    if pd.isna(date_value):
        return ''
    
    try:
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y-%m-%d')
        elif hasattr(date_value, 'date'):
            return date_value.date().strftime('%Y-%m-%d')
        else:
            return str(date_value)
    except (AttributeError, TypeError, ValueError):
        return ''

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
    AND b.booking_id NOT IN (
        SELECT DISTINCT ca.booking_id 
        FROM cancellation_actions ca 
        WHERE ca.action_status = 'confirmed'
    )
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
    
    # 2. Zero Commission Alerts (Private bookings) - DISABLED per user request
    # User requested to NOT show alerts for 0 commission customers
    # These will be managed separately in the canceled customer management section
    pass
    
    # 3. Cancellation Status Alerts - DISABLED per user request  
    # User requested to NOT show alerts for canceled customers who haven't checked out
    # These will be managed separately in the canceled customer management section
    pass
    
    # Calculate summary - now only includes active alerts
    total_alerts = len(notifications['specific_guest_alerts'])
    
    notifications['summary'] = {
        'total_alerts': total_alerts,
        'high_priority': len(notifications['specific_guest_alerts']),
        'medium_priority': 0,  # No longer showing zero commission alerts
        'low_priority': 0,     # No longer showing cancellation status alerts
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': 'Only showing Le Thuong alerts - other categories moved to management section'
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


def get_confirmed_cancellations() -> List[Dict[str, Any]]:
    """
    Get history of confirmed cancellation actions
    Useful for tracking what has been processed
    """
    
    query = """
    SELECT 
        ca.action_id,
        ca.booking_id,
        ca.guest_name,
        ca.cancellation_type,
        ca.action_status,
        ca.confirmed_by,
        ca.confirmation_date,
        ca.notes,
        ca.created_at
    FROM cancellation_actions ca
    WHERE ca.action_status IN ('confirmed', 'ok')
    ORDER BY ca.confirmation_date DESC
    LIMIT 20
    """
    
    df = execute_query(query)
    
    if df.empty:
        return []
    
    confirmed_list = []
    for _, action in df.iterrows():
        confirmed_list.append({
            'action_id': action['action_id'] if pd.notna(action['action_id']) else None,
            'booking_id': action['booking_id'],
            'guest_name': action['guest_name'],
            'cancellation_type': action['cancellation_type'] if pd.notna(action['cancellation_type']) else None,
            'confirmed_by': action['confirmed_by'] if pd.notna(action['confirmed_by']) else None,
            'confirmation_date': _safe_date_format(action['confirmation_date']),
            'notes': action['notes'] if pd.notna(action['notes']) else None,
            'created_at': action['created_at'] if pd.notna(action['created_at']) else None
        })
    
    return confirmed_list


def get_all_canceled_customers_for_management() -> List[Dict[str, Any]]:
    """
    Get ALL canceled customers for re-classification management
    This shows everyone with canceled status regardless of checkout date
    Allows manual re-classification of cancellation confirmations
    """
    
    query = """
    SELECT DISTINCT ON (b.booking_id)
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
        b.created_at,
        ca.action_id,
        ca.action_status,
        ca.confirmation_date,
        ca.cancellation_type,
        ca.notes as cancellation_notes
    FROM bookings b
    JOIN guests g ON b.guest_id = g.guest_id
    LEFT JOIN cancellation_actions ca ON b.booking_id = ca.booking_id
    WHERE b.booking_status != 'deleted'
    AND (
        /* Include canceled customers */
        b.booking_status ILIKE '%cancel%' 
        OR b.booking_status ILIKE '%hủy%'
        OR b.booking_status = 'đã hủy'
        OR b.booking_status = 'cancelled'
        /* Include zero commission customers (potential private bookings) */
        OR b.commission = 0
    )
    /* CRITICAL FIX: Exclude customers with confirmed or OK status actions */
    AND (ca.action_status IS NULL OR (ca.action_status != 'confirmed' AND ca.action_status != 'ok'))
    ORDER BY 
        b.booking_id,
        /* Prioritize by cancellation status, then by check-in date (newest first) */
        CASE 
            WHEN ca.action_status = 'pending' THEN 1
            WHEN ca.action_status IS NULL THEN 2  
        END,
        b.checkin_date DESC
    """
    
    df = execute_query(query)
    
    if df.empty:
        print("🔍 [CANCELED_CUSTOMERS] No canceled customers found in database")
        return []
    
    # Debug: Check for duplicates by guest name
    guest_counts = df['guest_name'].value_counts()
    duplicates = guest_counts[guest_counts > 1]
    if not duplicates.empty:
        print("🔍 [DUPLICATE_DEBUG] Guests with multiple entries:")
        for guest_name, count in duplicates.items():
            print(f"   - {guest_name}: {count} entries")
            guest_bookings = df[df['guest_name'] == guest_name][['booking_id', 'action_status', 'booking_status']]
            for _, booking in guest_bookings.iterrows():
                print(f"     * Booking {booking['booking_id']}: status={booking['booking_status']}, action={booking['action_status']}")
    
    customers = []
    for _, customer in df.iterrows():
        # Determine customer category
        is_canceled = any(status in str(customer['booking_status']).lower() 
                         for status in ['cancel', 'hủy', 'cancelled'])
        is_zero_commission = float(customer['commission'] or 0) == 0
        
        # Safe date comparison to handle NaT values
        has_checked_out = False
        if pd.notna(customer['checkout_date']):
            try:
                checkout_date = customer['checkout_date']
                if hasattr(checkout_date, 'date'):
                    checkout_date = checkout_date.date()
                has_checked_out = checkout_date < pd.Timestamp.now().date()
            except (AttributeError, TypeError):
                has_checked_out = False
        
        # Determine current action status
        action_status = customer.get('action_status')
        needs_action = action_status != 'confirmed'
        
        # CRITICAL SAFETY CHECK: Skip any confirmed customers that might slip through
        if action_status == 'confirmed':
            print(f"🔍 [SAFETY_FILTER] Skipping confirmed customer: {customer['guest_name']} ({customer['booking_id']})")
            continue
        
        customer_data = {
            'booking_id': customer['booking_id'],
            'guest_name': customer['guest_name'],
            'checkin_date': _safe_date_format(customer['checkin_date']),
            'checkout_date': _safe_date_format(customer['checkout_date']),
            'room_amount': float(customer['room_amount']) if pd.notna(customer['room_amount']) else 0,
            'commission': float(customer['commission']) if pd.notna(customer['commission']) else 0,
            'booking_status': customer['booking_status'],
            'collected_amount': float(customer['collected_amount']) if pd.notna(customer['collected_amount']) else 0,
            'booking_notes': customer['booking_notes'] if pd.notna(customer['booking_notes']) else None,
            
            # Cancellation action info
            'action_id': customer.get('action_id') if pd.notna(customer.get('action_id')) else None,
            'action_status': action_status,
            'confirmation_date': _safe_date_format(customer.get('confirmation_date')),
            'cancellation_type': customer.get('cancellation_type') if pd.notna(customer.get('cancellation_type')) else None,
            'cancellation_notes': customer.get('cancellation_notes') if pd.notna(customer.get('cancellation_notes')) else None,
            
            # Classification helpers
            'is_canceled': is_canceled,
            'is_zero_commission': is_zero_commission,
            'has_checked_out': has_checked_out,
            'needs_action': needs_action,
            
            # Visual categorization
            'category': 'Canceled Customer' if is_canceled else 'Zero Commission',
            'priority': 'High' if (is_canceled and not has_checked_out) else 'Medium' if is_zero_commission else 'Low',
            'status_description': (
                'Confirmed' if action_status == 'confirmed' else
                'OK (Resolved)' if action_status == 'ok' else
                'Pending Review' if action_status == 'pending' else  
                'Needs Classification'
            )
        }
        
        customers.append(customer_data)
    
    
    return customers