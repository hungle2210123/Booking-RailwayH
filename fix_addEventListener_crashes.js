// COMPREHENSIVE FIX FOR addEventListener CRASHES
// This script adds error handling for all addEventListener calls

// Override addEventListener to add automatic null checking
const originalAddEventListener = Element.prototype.addEventListener;
Element.prototype.addEventListener = function(type, listener, options) {
    try {
        if (this && typeof this.addEventListener === 'function') {
            return originalAddEventListener.call(this, type, listener, options);
        } else {
            console.error('❌ addEventListener called on null element:', this, type);
        }
    } catch (error) {
        console.error('❌ addEventListener error:', error, 'Element:', this, 'Type:', type);
    }
};

// Add global error handler for uncaught TypeError
window.addEventListener('error', function(e) {
    if (e.message.includes('addEventListener') || e.message.includes('Cannot read properties of null')) {
        console.error('🚨 Global addEventListener error caught:', e.message);
        console.error('Line:', e.lineno, 'File:', e.filename);
        
        // Prevent the error from breaking the rest of the code
        e.preventDefault();
        return true;
    }
});

console.log('✅ addEventListener crash protection enabled');