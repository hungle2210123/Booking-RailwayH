// 🧪 FINAL TEST: Custom Date Picker Functionality
// Copy and paste this into your browser console (F12) on the dashboard

console.log('🧪 TESTING CUSTOM DATE PICKER FUNCTIONALITY');
console.log('='.repeat(60));

// Test 1: Check if function exists
console.log('🔍 Test 1: Function availability');
console.log('   setCollectorDateType:', typeof setCollectorDateType);
console.log('   updateCollectorChart:', typeof updateCollectorChart);

// Test 2: Check elements exist
console.log('\n🔍 Test 2: HTML elements');
const elements = {
    'Custom Date Button': document.getElementById('collectorDateCustom'),
    'Start Date Input': document.getElementById('collectorStartDate'),
    'End Date Input': document.getElementById('collectorEndDate'),
    'Custom Container': document.getElementById('collectorCustomDateContainer'),
    'Month Container': document.getElementById('collectorMonthContainer'),
    'Chart Div': document.getElementById('collectorChart')
};

Object.entries(elements).forEach(([name, element]) => {
    console.log(`   ${name}: ${element ? '✅ Found' : '❌ Missing'}`);
});

// Test 3: Switch to custom mode
console.log('\n🔍 Test 3: Switching to custom date mode');
try {
    setCollectorDateType('custom');
    
    setTimeout(() => {
        const customContainer = document.getElementById('collectorCustomDateContainer');
        const isVisible = customContainer && !customContainer.classList.contains('d-none');
        console.log('   Custom container visible:', isVisible ? '✅ YES' : '❌ NO');
        
        // Test 4: Set custom dates
        console.log('\n🔍 Test 4: Setting custom dates');
        const startInput = document.getElementById('collectorStartDate');
        const endInput = document.getElementById('collectorEndDate');
        
        if (startInput && endInput) {
            startInput.value = '2025-06-15';
            endInput.value = '2025-06-31';
            console.log('   Start date set to:', startInput.value);
            console.log('   End date set to:', endInput.value);
            
            // Test 5: Trigger chart update
            console.log('\n🔍 Test 5: Triggering chart update with custom dates');
            
            // Manually check what data will be sent
            setTimeout(() => {
                console.log('\n📊 Simulating API call...');
                const requestData = {
                    start_date: startInput.value,
                    end_date: endInput.value
                };
                console.log('   Request data would be:', requestData);
                
                // Actually trigger the update
                if (typeof updateCollectorChart === 'function') {
                    console.log('   🔄 Calling updateCollectorChart()...');
                    updateCollectorChart();
                } else {
                    console.log('   ❌ updateCollectorChart function not available');
                }
            }, 500);
            
        } else {
            console.log('   ❌ Date inputs not found');
        }
        
    }, 200);
    
} catch (error) {
    console.error('❌ Error in test:', error);
}

// Test 6: Monitor API calls
console.log('\n🔍 Test 6: Monitoring network activity');
console.log('   Check Network tab in DevTools for /api/collector_chart_data requests');
console.log('   Look for proper date format in request payload');

console.log('\n🎯 TEST COMPLETE!');
console.log('Expected behavior:');
console.log('   1. Green date picker box should appear');
console.log('   2. Dates should be set to June 15-31');
console.log('   3. Chart should update with filtered data');
console.log('   4. Console should show proper date format in API request');

// Helper function to verify current state
window.verifyCustomDateState = function() {
    const customContainer = document.getElementById('collectorCustomDateContainer');
    const startInput = document.getElementById('collectorStartDate');
    const endInput = document.getElementById('collectorEndDate');
    
    console.log('📊 Current Custom Date State:');
    console.log('   Container visible:', customContainer ? !customContainer.classList.contains('d-none') : false);
    console.log('   Start date value:', startInput ? startInput.value : 'not found');
    console.log('   End date value:', endInput ? endInput.value : 'not found');
    
    if (customContainer && !customContainer.classList.contains('d-none')) {
        console.log('✅ Custom date picker is ACTIVE and VISIBLE');
        if (startInput && endInput && startInput.value && endInput.value) {
            console.log('✅ Both date inputs have values - ready for API call');
            return true;
        } else {
            console.log('⚠️ Date inputs missing values');
            return false;
        }
    } else {
        console.log('❌ Custom date picker is NOT visible');
        return false;
    }
};

console.log('\n💡 Run verifyCustomDateState() to check current state anytime');