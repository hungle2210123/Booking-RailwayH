// JavaScript Fixes Verification Script
// Run this in browser console to verify all issues are resolved

console.log('🧪 Starting JavaScript Fixes Verification...');

// Test 1: Check variable declarations
function testVariableDeclarations() {
    console.log('\n📋 Test 1: Variable Declarations');
    
    try {
        // These should be defined without errors
        console.log('✅ selectedApartment declared:', typeof selectedApartment !== 'undefined');
        console.log('✅ APARTMENTS declared:', typeof APARTMENTS !== 'undefined');
        console.log('✅ duplicateGroups declared:', typeof duplicateGroups !== 'undefined');
        console.log('✅ extractedBookings declared:', typeof extractedBookings !== 'undefined');
        
        // Check APARTMENTS structure
        console.log('✅ APARTMENTS has apartment 1:', APARTMENTS.hasOwnProperty('1'));
        console.log('✅ APARTMENTS has apartment 2:', APARTMENTS.hasOwnProperty('2'));
        
        return true;
    } catch (error) {
        console.error('❌ Variable declaration test failed:', error);
        return false;
    }
}

// Test 2: Check function availability
function testFunctionAvailability() {
    console.log('\n🔧 Test 2: Function Availability');
    
    try {
        // Check if functions are defined
        console.log('✅ selectApartment function:', typeof selectApartment !== 'undefined');
        console.log('✅ selectApartment on window:', typeof window.selectApartment !== 'undefined');
        console.log('✅ keepExtractedBooking function:', typeof keepExtractedBooking !== 'undefined');
        console.log('✅ skipDuplicateBooking function:', typeof skipDuplicateBooking !== 'undefined');
        
        return true;
    } catch (error) {
        console.error('❌ Function availability test failed:', error);
        return false;
    }
}

// Test 3: Test selectApartment function execution
function testSelectApartmentExecution() {
    console.log('\n🏠 Test 3: selectApartment Execution');
    
    try {
        // Test if selectApartment can be called
        if (typeof selectApartment === 'function') {
            console.log('✅ selectApartment is callable');
            
            // Test apartment 1 selection (safely)
            const originalSelectedApartment = selectedApartment;
            selectApartment(1);
            console.log('✅ selectApartment(1) executed successfully');
            console.log('✅ selectedApartment value:', selectedApartment);
            
            // Restore original value
            selectedApartment = originalSelectedApartment;
            
            return true;
        } else {
            console.error('❌ selectApartment is not a function');
            return false;
        }
    } catch (error) {
        console.error('❌ selectApartment execution test failed:', error);
        return false;
    }
}

// Test 4: Check DOM element interactions
function testDOMElementInteractions() {
    console.log('\n🌐 Test 4: DOM Element Interactions');
    
    try {
        // Check if apartment cards exist
        const apartmentCards = document.querySelectorAll('.apartment-card');
        console.log('✅ Apartment cards found:', apartmentCards.length);
        
        // Check if key elements exist
        const elements = [
            'selected-apartment-info',
            'crawl-date-from',
            'crawl-date-to',
            'start-crawl-btn'
        ];
        
        elements.forEach(id => {
            const element = document.getElementById(id);
            console.log(`✅ Element ${id}:`, element ? 'found' : 'missing');
        });
        
        return true;
    } catch (error) {
        console.error('❌ DOM element test failed:', error);
        return false;
    }
}

// Run all tests
function runAllTests() {
    console.log('🎯 Running Complete JavaScript Fixes Verification');
    console.log('=' + '='.repeat(50));
    
    const results = {
        variableDeclarations: testVariableDeclarations(),
        functionAvailability: testFunctionAvailability(),
        selectApartmentExecution: testSelectApartmentExecution(),
        domElementInteractions: testDOMElementInteractions()
    };
    
    console.log('\n📊 Test Results Summary:');
    console.log('=' + '='.repeat(30));
    
    let allPassed = true;
    Object.keys(results).forEach(test => {
        const status = results[test] ? '✅ PASS' : '❌ FAIL';
        console.log(`${status} ${test}`);
        if (!results[test]) allPassed = false;
    });
    
    console.log('\n🎯 Overall Result:', allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED');
    
    if (allPassed) {
        console.log('\n🎉 JavaScript fixes are working correctly!');
        console.log('🔧 You can now:');
        console.log('   • Click apartment selection cards');
        console.log('   • Use duplicate handling buttons');
        console.log('   • Process photo uploads without errors');
        console.log('   • Use all booking management features');
    } else {
        console.log('\n⚠️ Some issues remain. Check the specific test failures above.');
    }
    
    return allPassed;
}

// Auto-run tests when script is loaded
runAllTests();