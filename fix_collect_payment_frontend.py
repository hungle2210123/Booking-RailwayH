#!/usr/bin/env python3
"""
Fix Collect Payment Frontend - Create working collection interface
"""

import os
from pathlib import Path

def create_working_collect_payment_script():
    """Create a bulletproof collectPayment JavaScript function"""
    
    script_content = '''
// BULLETPROOF COLLECT PAYMENT FUNCTION - FIXED VERSION
function collectPaymentFixed() {
    console.log('🔧 FIXED collectPayment function started');
    
    try {
        // Get all modal elements with strict null checking
        const elements = {
            taxiAmount: document.getElementById('taxiAmount'),
            hasTaxi: document.getElementById('hasTaxi'), 
            collectorName: document.getElementById('collectorName'),
            collectedAmount: document.getElementById('collectedAmount'),
            paymentNote: document.getElementById('paymentNote'),
            noCommission: document.getElementById('noCommission'),
            commissionAmountInput: document.getElementById('commissionAmountInput')
        };
        
        // Validate required elements
        if (!elements.collectorName) {
            alert('❌ Collector field not found! Please refresh the page.');
            return;
        }
        
        // Get values with fallbacks
        const collectorName = elements.collectorName.value;
        const paymentNote = elements.paymentNote ? elements.paymentNote.value.trim() : '';
        const noCommissionSelected = elements.noCommission ? elements.noCommission.checked : false;
        
        // FIXED TAXI DETECTION - Simple and reliable
        let taxiAmountValue = 0;
        let hasTaxiChecked = false;
        
        if (elements.taxiAmount && elements.taxiAmount.value) {
            taxiAmountValue = parseFloat(elements.taxiAmount.value) || 0;
        }
        
        if (elements.hasTaxi) {
            hasTaxiChecked = elements.hasTaxi.checked;
        }
        
        // Determine if this is a taxi payment
        const isTaxiPayment = hasTaxiChecked || (taxiAmountValue > 0);
        
        console.log('TAXI DETECTION:', {
            taxiAmount: taxiAmountValue,
            taxiChecked: hasTaxiChecked,
            isTaxiPayment: isTaxiPayment
        });
        
        // COMMISSION DETECTION - Simple and reliable
        let commissionAmount = 0;
        if (!noCommissionSelected && elements.commissionAmountInput) {
            commissionAmount = parseFloat(elements.commissionAmountInput.value) || 0;
        }
        
        console.log('COMMISSION DETECTION:', {
            amount: commissionAmount,
            noCommission: noCommissionSelected
        });
        
        // PAYMENT TYPE AND AMOUNT LOGIC
        let collectedAmount, finalNote, paymentType;
        
        if (isTaxiPayment && taxiAmountValue > 0) {
            // TAXI PAYMENT
            collectedAmount = taxiAmountValue;
            finalNote = paymentNote || 'Thu tiền taxi';
            paymentType = 'taxi';
            
            console.log('✅ TAXI PAYMENT MODE');
            alert(`🚕 TAXI PAYMENT DETECTED!\\nAmount: ${taxiAmountValue.toLocaleString()}đ\\nThis will save to database!`);
            
        } else if (isTaxiPayment && taxiAmountValue === 0) {
            alert('❌ Vui lòng nhập số tiền taxi!');
            return;
            
        } else {
            // ROOM PAYMENT (default)
            if (!elements.collectedAmount || !elements.collectedAmount.value) {
                alert('❌ Vui lòng nhập số tiền thu!');
                return;
            }
            
            collectedAmount = parseFloat(elements.collectedAmount.value) || 0;
            finalNote = paymentNote || 'Thu tiền phòng';
            paymentType = 'room';
            
            console.log('✅ ROOM PAYMENT MODE');
        }
        
        // VALIDATION
        if (!collectorName) {
            alert('❌ Vui lòng chọn người thu tiền!');
            return;
        }
        
        if (collectedAmount <= 0) {
            alert('❌ Số tiền thu không hợp lệ!');
            return;
        }
        
        if (!noCommissionSelected && commissionAmount <= 0) {
            alert('❌ Vui lòng nhập số tiền hoa hồng!');
            return;
        }
        
        // PREPARE REQUEST DATA
        const requestData = {
            booking_id: currentBookingData.bookingId,
            collected_amount: collectedAmount,
            collector_name: collectorName,
            payment_note: finalNote,
            payment_type: paymentType,  // This is the critical fix!
            commission_amount: commissionAmount,
            commission_type: noCommissionSelected ? 'none' : 'normal'
        };
        
        console.log('📤 SENDING REQUEST:', requestData);
        console.log(`🎯 PAYMENT TYPE: ${paymentType} (${paymentType === 'taxi' ? 'TAXI' : 'ROOM'})`);
        
        // Show confirmation alert
        if (paymentType === 'taxi') {
            const confirmMsg = `🚕 CONFIRM TAXI PAYMENT:
• Amount: ${collectedAmount.toLocaleString()}đ
• Commission: ${commissionAmount.toLocaleString()}đ
• Collector: ${collectorName}
• Note: ${finalNote}

This will save taxi amount to database!`;
            
            if (!confirm(confirmMsg)) {
                return;
            }
        }
        
        // DISABLE BUTTON
        const confirmBtn = document.getElementById('confirmCollectBtn');
        const originalText = confirmBtn.innerHTML;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';
        confirmBtn.disabled = true;
        
        // CALL API
        fetch('/api/collect_payment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Success message
                const successMsg = paymentType === 'taxi' 
                    ? `✅ Thu taxi thành công: ${collectedAmount.toLocaleString()}đ`
                    : `✅ ${data.message}`;
                    
                showDashboardToast(successMsg, 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('collectPaymentModal'));
                modal.hide();
                
                // Reload page to show updated data
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
                
            } else {
                throw new Error(data.message || 'Lỗi không xác định');
            }
        })
        .catch(error => {
            console.error('Collect payment error:', error);
            showDashboardToast(`❌ Lỗi: ${error.message}`, 'error');
        })
        .finally(() => {
            // Restore button
            confirmBtn.innerHTML = originalText;
            confirmBtn.disabled = false;
        });
        
    } catch (error) {
        console.error('🚨 collectPayment function error:', error);
        alert(`❌ Lỗi hệ thống: ${error.message}\\n\\nVui lòng thử lại hoặc refresh trang.`);
    }
}

// Replace the broken function
console.log('🔧 Loading fixed collectPayment function...');
window.collectPayment = collectPaymentFixed;
console.log('✅ Fixed collectPayment function loaded!');
'''
    
    return script_content

def inject_fixed_script_into_dashboard():
    """Inject the fixed script directly into dashboard.html"""
    
    dashboard_path = Path("/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized/templates/dashboard.html")
    
    if not dashboard_path.exists():
        print(f"❌ Dashboard file not found: {dashboard_path}")
        return False
    
    try:
        # Read current content
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if fix is already applied
        if 'collectPaymentFixed' in content:
            print("✅ Fixed script already present in dashboard.html")
            return True
        
        # Find the end of the script section
        script_end = content.rfind('</script>')
        if script_end == -1:
            print("❌ Could not find script section in dashboard.html")
            return False
        
        # Inject the fixed script before the closing script tag
        fixed_script = create_working_collect_payment_script()
        injection_point = script_end
        
        new_content = (
            content[:injection_point] + 
            '\n// === FIXED COLLECT PAYMENT FUNCTION ===\n' +
            fixed_script + 
            '\n// === END FIXED FUNCTION ===\n\n' +
            content[injection_point:]
        )
        
        # Write back to file
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Fixed collectPayment function injected into dashboard.html")
        return True
        
    except Exception as e:
        print(f"❌ Error injecting script: {e}")
        return False

def create_test_button_fix():
    """Create a simple button replacement fix"""
    
    button_fix = '''
<!-- FIXED COLLECT PAYMENT BUTTON -->
<button type="button" class="btn btn-success" id="confirmCollectBtnFixed" onclick="collectPaymentFixed();">
    <i class="fas fa-check me-1"></i>Thu tiền (FIXED)
</button>
'''
    
    return button_fix

def main():
    """Main function to apply the fix"""
    
    print("🔧 FIXING COLLECT PAYMENT FRONTEND")
    print("=" * 50)
    
    # Inject the fixed script
    if inject_fixed_script_into_dashboard():
        print("\n✅ SUCCESS! Fixed collect payment function added.")
        print("\n🎯 NEXT STEPS:")
        print("1. Restart your Flask server (Ctrl+C then restart)")
        print("2. Clear browser cache (Ctrl+Shift+Del)")
        print("3. Go to dashboard and test taxi payment")
        print("4. Look for 'Fixed collectPayment function loaded!' in console")
        print("5. The fixed function will replace the broken one automatically")
        
        print("\n🧪 TESTING:")
        print("- Check 'Có taxi' checkbox")
        print("- Enter taxi amount (e.g., 200000)")
        print("- Should see confirmation alert with taxi details")
        print("- Server logs should show 'payment_type: taxi'")
        
        return True
    else:
        print("\n❌ FAILED to inject fix")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)