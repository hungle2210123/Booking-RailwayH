// 🧪 DELETE FUNCTIONALITY TEST SCRIPT
// Copy and paste this into your browser console to test delete functionality

console.log('🧪 TESTING DELETE FUNCTIONALITY');
console.log('='.repeat(60));

// Test 1: Check if expense delete function exists
console.log('🔍 Test 1: Function availability');
console.log('   deleteExpense function:', typeof deleteExpense !== 'undefined' ? '✅ Available' : '❌ Not found');

// Test 2: Check for expense delete buttons
console.log('\n🔍 Test 2: Expense delete buttons');
const expenseDeleteButtons = document.querySelectorAll('button[onclick*="deleteExpense"]');
console.log(`   Found ${expenseDeleteButtons.length} expense delete buttons`);

if (expenseDeleteButtons.length > 0) {
    console.log('   ✅ Delete buttons are present in the expense list');
    
    // Show details of first button
    const firstButton = expenseDeleteButtons[0];
    console.log('   Sample button details:');
    console.log(`     - onclick: ${firstButton.getAttribute('onclick')}`);
    console.log(`     - title: ${firstButton.getAttribute('title')}`);
    console.log(`     - expense description: ${firstButton.getAttribute('data-expense-description')}`);
    console.log(`     - expense date: ${firstButton.getAttribute('data-expense-date')}`);
} else {
    console.log('   ⚠️ No delete buttons found. Make sure expense list is loaded.');
}

// Test 3: Check template delete function (if on AI Assistant page)
console.log('\n🔍 Test 3: Template delete functionality');
if (typeof deleteTemplate !== 'undefined') {
    console.log('   deleteTemplate function: ✅ Available');
    
    const templateDeleteButtons = document.querySelectorAll('button[onclick*="deleteTemplate"]');
    console.log(`   Found ${templateDeleteButtons.length} template delete buttons`);
    
    if (templateDeleteButtons.length > 0) {
        console.log('   ✅ Template delete buttons are present');
        
        // Show details of first template button
        const firstTemplateButton = templateDeleteButtons[0];
        console.log('   Sample template button details:');
        console.log(`     - onclick: ${firstTemplateButton.getAttribute('onclick')}`);
        console.log(`     - template name: ${firstTemplateButton.getAttribute('data-template-name')}`);
    }
} else {
    console.log('   ℹ️ Template delete function not available (not on AI Assistant page)');
}

// Test 4: Check API endpoints
console.log('\n🔍 Test 4: API endpoint availability');

// Test expense API
console.log('   Testing expense delete API...');
const testExpenseId = 999999; // Non-existent ID for testing
fetch(`/api/expenses/${testExpenseId}`, { method: 'DELETE' })
    .then(response => {
        console.log(`   Expense API response status: ${response.status}`);
        if (response.status === 404) {
            console.log('   ✅ Expense delete API is working (404 expected for non-existent ID)');
        } else if (response.status === 500) {
            console.log('   ⚠️ Expense delete API has server error');
        } else {
            console.log('   ✅ Expense delete API is accessible');
        }
        return response.json();
    })
    .then(data => {
        console.log('   API response:', data);
    })
    .catch(error => {
        console.log('   ❌ Expense API error:', error.message);
    });

// Test template API
console.log('   Testing template delete API...');
const testTemplateId = 999999; // Non-existent ID for testing
fetch(`/api/templates/${testTemplateId}`, { method: 'DELETE' })
    .then(response => {
        console.log(`   Template API response status: ${response.status}`);
        if (response.status === 404) {
            console.log('   ✅ Template delete API is working (404 expected for non-existent ID)');
        } else if (response.status === 500) {
            console.log('   ⚠️ Template delete API has server error');
        } else {
            console.log('   ✅ Template delete API is accessible');
        }
        return response.json();
    })
    .then(data => {
        console.log('   API response:', data);
    })
    .catch(error => {
        console.log('   ❌ Template API error:', error.message);
    });

// Test 5: Simulate delete button click (safe test)
console.log('\n🔍 Test 5: Button click simulation');

window.testDeleteButtonClick = function() {
    console.log('🧪 Testing delete button click...');
    
    // Find a delete button
    const deleteButton = document.querySelector('button[onclick*="deleteExpense"]');
    if (!deleteButton) {
        console.log('❌ No expense delete button found for testing');
        return;
    }
    
    console.log('✅ Found delete button, testing click handler...');
    
    // Override confirm to prevent actual deletion
    const originalConfirm = window.confirm;
    window.confirm = function(message) {
        console.log('📋 Confirmation dialog would show:', message);
        console.log('✅ Delete function is properly calling confirmation');
        window.confirm = originalConfirm; // Restore original
        return false; // Cancel the deletion
    };
    
    // Simulate click
    try {
        deleteButton.click();
        console.log('✅ Button click handled successfully');
    } catch (error) {
        console.log('❌ Error in button click handler:', error.message);
    }
};

console.log('\n💡 MANUAL TESTING:');
console.log('1. Call testDeleteButtonClick() to safely test button clicks');
console.log('2. Look for delete buttons (trash icons) in expense lists');
console.log('3. Try clicking a delete button to see the confirmation dialog');
console.log('4. Check if the confirmation shows expense details');
console.log('\n🎯 Expected behavior:');
console.log('- Delete buttons should show detailed confirmation with expense name and date');
console.log('- Successful deletion should show toast notification');
console.log('- Failed deletion should show error message');
console.log('- UI should update immediately after deletion');

console.log('\n🚀 Run testDeleteButtonClick() to start safe testing!');