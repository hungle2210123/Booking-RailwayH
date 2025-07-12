
// 🧪 BROWSER CONSOLE TEST COMMANDS
// Copy and paste these into your browser console (F12)

// Test 1: Show custom date picker
console.log('🧪 Test 1: Showing custom date picker...');
setCollectorDateType('custom');

// Test 2: Set example dates (June 15-31)
setTimeout(() => {
    console.log('🧪 Test 2: Setting example dates...');
    document.getElementById('collectorStartDate').value = '2025-06-15';
    document.getElementById('collectorEndDate').value = '2025-06-31';
    console.log('📅 Dates set! Chart should update automatically.');
}, 1000);

// Test 3: Verify elements exist
setTimeout(() => {
    console.log('🧪 Test 3: Verifying interface elements...');
    const elements = {
        'Custom Date Button': document.getElementById('collectorDateCustom'),
        'Start Date Input': document.getElementById('collectorStartDate'),
        'End Date Input': document.getElementById('collectorEndDate'),
        'Custom Container': document.getElementById('collectorCustomDateContainer')
    };
    
    Object.entries(elements).forEach(([name, element]) => {
        console.log(`   ${name}: ${element ? '✅ Found' : '❌ Missing'}`);
        if (element && name === 'Custom Container') {
            console.log(`   → Visible: ${!element.classList.contains('d-none')}`);
        }
    });
}, 2000);

console.log('🎯 All tests scheduled! Watch the console output.');
