#!/usr/bin/env python3
"""
Add manual booking entry route as ultimate fallback when all APIs fail
This ensures users can always add bookings even without working APIs
"""

import os
import sys

def add_manual_booking_route():
    """Add manual booking entry route to app.py"""
    
    # Read current app.py
    app_path = "app.py"
    if not os.path.exists(app_path):
        print("❌ app.py not found!")
        return False
    
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if manual booking route already exists
    if '@app.route(\'/api/manual_booking_entry\'' in content:
        print("✅ Manual booking entry route already exists")
        return True
    
    # Find a good place to insert the route (after other booking routes)
    booking_route_markers = [
        '@app.route(\'/api/ai_analysis\'',
        '@app.route(\'/api/add_booking\'',
        '@app.route(\'/api/bookings\''
    ]
    
    insert_position = -1
    for marker in booking_route_markers:
        pos = content.find(marker)
        if pos != -1:
            # Find the end of this route function
            lines = content[pos:].split('\\n')
            route_end = pos
            indent_level = 0
            for i, line in enumerate(lines):
                if i == 0:  # First line is the @app.route
                    continue
                if line.strip().startswith('def '):
                    indent_level = len(line) - len(line.lstrip())
                elif line.strip() and indent_level > 0:
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= indent_level and not line.strip().startswith(('@', 'def ', 'class ', '#')):
                        # This is likely the end of the function
                        route_end = pos + len('\\n'.join(lines[:i]))
                        break
            insert_position = max(insert_position, route_end)
    
    if insert_position == -1:
        print("❌ Could not find suitable insertion point")
        return False
    
    # Manual booking entry route
    manual_route = '''
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

@app.route('/api/booking_entry_options', methods=['GET'])
def get_booking_entry_options():
    """Get available booking entry methods and their status"""
    try:
        # Check API availability
        from core.logic_postgresql import extract_booking_info_from_image_content_multi_api
        
        # Test with minimal dummy data to check API status
        test_data = b'dummy'
        try:
            test_result = extract_booking_info_from_image_content_multi_api(test_data)
            ai_available = not ('exhausted' in str(test_result.get('error', '')))
        except:
            ai_available = False
        
        return jsonify({
            'success': True,
            'options': {
                'ai_extraction': {
                    'available': ai_available,
                    'description': 'Upload booking screenshot for automatic extraction',
                    'status': 'Working' if ai_available else 'APIs exhausted'
                },
                'manual_entry': {
                    'available': True,
                    'description': 'Manual form entry when AI fails',
                    'status': 'Always available'
                }
            },
            'recommendation': 'ai_extraction' if ai_available else 'manual_entry'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

'''
    
    # Insert the new route
    new_content = content[:insert_position] + manual_route + content[insert_position:]
    
    # Write back to file
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Manual booking entry routes added to app.py")
    return True

def update_ai_assistant_template():
    """Update AI assistant template to show manual entry option"""
    
    template_path = "templates/ai_assistant.html"
    if not os.path.exists(template_path):
        print("⚠️ ai_assistant.html not found, skipping template update")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if manual entry section already exists
    if 'id="manualBookingSection"' in content:
        print("✅ Manual booking section already exists in template")
        return True
    
    # Find insertion point (look for booking upload section)
    insertion_markers = [
        '<div class="image-upload-section">',
        '<div class="upload-section">',
        'id="imageUploadSection"'
    ]
    
    insert_position = -1
    for marker in insertion_markers:
        pos = content.find(marker)
        if pos != -1:
            # Find the end of this section
            section_end = content.find('</div>', pos)
            if section_end != -1:
                insert_position = section_end + 6  # After </div>
                break
    
    if insert_position == -1:
        print("⚠️ Could not find suitable insertion point in template")
        return False
    
    # Manual entry form HTML
    manual_form_html = '''
<!-- Manual Booking Entry Section (Fallback when AI fails) -->
<div id="manualBookingSection" class="manual-entry-section" style="display: none; margin-top: 20px; padding: 20px; border: 2px dashed #e74c3c; border-radius: 8px; background-color: #fdf2f2;">
    <h4 style="color: #e74c3c; margin-bottom: 15px;">
        🚨 Manual Booking Entry (AI APIs Exhausted)
    </h4>
    <p style="color: #666; margin-bottom: 20px;">
        All AI services are currently unavailable. Please enter booking details manually:
    </p>
    
    <form id="manualBookingForm" class="manual-booking-form">
        <div class="form-row">
            <div class="form-group">
                <label for="manualGuestName">Guest Name *</label>
                <input type="text" id="manualGuestName" name="guest_name" required 
                       placeholder="Full name (e.g., John Smith)">
            </div>
            <div class="form-group">
                <label for="manualGuestCount">Number of Guests</label>
                <input type="number" id="manualGuestCount" name="guest_count" 
                       value="1" min="1" max="10">
            </div>
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label for="manualCheckinDate">Check-in Date *</label>
                <input type="date" id="manualCheckinDate" name="checkin_date" required>
            </div>
            <div class="form-group">
                <label for="manualCheckoutDate">Check-out Date *</label>
                <input type="date" id="manualCheckoutDate" name="checkout_date" required>
            </div>
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label for="manualRoomAmount">Room Amount *</label>
                <input type="number" id="manualRoomAmount" name="room_amount" 
                       step="0.01" min="0" required placeholder="Total price (numbers only)">
            </div>
            <div class="form-group">
                <label for="manualBookingPlatform">Booking Platform</label>
                <select id="manualBookingPlatform" name="booking_platform">
                    <option value="Manual Entry">Manual Entry</option>
                    <option value="Booking.com">Booking.com</option>
                    <option value="Airbnb">Airbnb</option>
                    <option value="Agoda">Agoda</option>
                    <option value="Expedia">Expedia</option>
                    <option value="Hotels.com">Hotels.com</option>
                    <option value="Phone/Direct">Phone/Direct</option>
                    <option value="Other">Other</option>
                </select>
            </div>
        </div>
        
        <div class="form-row">
            <div class="form-group">
                <label for="manualAccommodation">Accommodation</label>
                <input type="text" id="manualAccommodation" name="accommodation_name" 
                       value="118 Hang Bac Hostel" placeholder="Hotel/hostel name">
            </div>
            <div class="form-group">
                <label for="manualRoomType">Room Type</label>
                <input type="text" id="manualRoomType" name="room_type" 
                       placeholder="e.g., Standard Room, Dorm Bed">
            </div>
        </div>
        
        <div class="form-actions" style="margin-top: 20px;">
            <button type="submit" class="btn btn-primary">
                ✅ Add Booking Manually
            </button>
            <button type="button" class="btn btn-secondary" onclick="hideManualEntry()">
                Cancel
            </button>
        </div>
    </form>
</div>

<script>
function showManualEntry() {
    document.getElementById('manualBookingSection').style.display = 'block';
    // Set default dates
    const today = new Date().toISOString().split('T')[0];
    const tomorrow = new Date(Date.now() + 24*60*60*1000).toISOString().split('T')[0];
    document.getElementById('manualCheckinDate').value = today;
    document.getElementById('manualCheckoutDate').value = tomorrow;
}

function hideManualEntry() {
    document.getElementById('manualBookingSection').style.display = 'none';
}

// Handle manual booking form submission
document.getElementById('manualBookingForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const bookingData = Object.fromEntries(formData.entries());
    
    // Validate dates
    const checkinDate = new Date(bookingData.checkin_date);
    const checkoutDate = new Date(bookingData.checkout_date);
    
    if (checkoutDate <= checkinDate) {
        alert('Check-out date must be after check-in date');
        return;
    }
    
    // Submit manual booking
    fetch('/api/manual_booking_entry', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(bookingData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('✅ Booking added successfully via manual entry!', 'success');
            hideManualEntry();
            this.reset();
            
            // Refresh booking list if available
            if (typeof loadBookings === 'function') {
                loadBookings();
            }
        } else {
            showToast('❌ Manual booking failed: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Manual booking error:', error);
        showToast('❌ Network error during manual booking', 'error');
    });
});
</script>

<style>
.manual-entry-section .form-row {
    display: flex;
    gap: 15px;
    margin-bottom: 15px;
}

.manual-entry-section .form-group {
    flex: 1;
}

.manual-entry-section label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
    color: #333;
}

.manual-entry-section input,
.manual-entry-section select {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
}

.manual-entry-section input:focus,
.manual-entry-section select:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}

.manual-entry-section .form-actions {
    display: flex;
    gap: 10px;
}

.manual-entry-section .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.manual-entry-section .btn-primary {
    background-color: #007bff;
    color: white;
}

.manual-entry-section .btn-secondary {
    background-color: #6c757d;
    color: white;
}
</style>

'''
    
    # Insert the manual form HTML
    new_content = content[:insert_position] + manual_form_html + content[insert_position:]
    
    # Write back to file
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Manual booking entry form added to AI assistant template")
    return True

if __name__ == "__main__":
    print("🔧 Adding manual booking entry fallback system...")
    print("=" * 60)
    
    success1 = add_manual_booking_route()
    success2 = update_ai_assistant_template()
    
    if success1 and success2:
        print("\n✅ Manual booking entry system added successfully!")
        print("\n🎯 BENEFITS:")
        print("   ✅ Users can always add bookings even when all APIs fail")
        print("   ✅ Clean form interface for manual data entry")
        print("   ✅ Automatic validation and error handling")
        print("   ✅ Integrates with existing booking management system")
        print("\n🔧 NEXT STEPS:")
        print("   1. Test the new manual entry system")
        print("   2. Deploy to Railway")
        print("   3. Get new working API keys when possible")
    else:
        print("\n❌ Some components failed to install")
        print("   Manual review and fixes may be needed")
    
    print("=" * 60)