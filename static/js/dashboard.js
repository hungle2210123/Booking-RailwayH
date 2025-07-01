// dashboard.js - Optimized dashboard JavaScript functionality

// ==================== GLOBAL VARIABLES ====================
let currentBookingId = '';
let currentTotalAmount = 0;
let currentCommission = 0;

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded, initializing...');
    
    // Initialize charts
    initializeCharts();
});

function initializeCharts() {
    // Monthly Revenue Chart
    if (typeof monthlyRevenueChartData !== 'undefined' && monthlyRevenueChartData) {
        createMonthlyRevenueChart(monthlyRevenueChartData);
    }
    
    // Collector Chart
    if (typeof collectorChartData !== 'undefined' && collectorChartData) {
        createCollectorChart(collectorChartData);
    }
}

// ==================== CHART FUNCTIONS ====================
function createMonthlyRevenueChart(chartData) {
    if (chartData && typeof chartData === 'object' && 
        Object.keys(chartData).length > 0 && chartData.data && chartData.layout) {
        try {
            Plotly.newPlot('monthlyRevenueChart', chartData.data, chartData.layout, {
                responsive: true,
                displayModeBar: false
            });
            console.log('Monthly revenue chart rendered successfully');
        } catch (error) {
            console.error('Error rendering monthly revenue chart:', error);
            document.getElementById('monthlyRevenueChart').innerHTML = 
                '<div class="alert alert-danger">Lỗi hiển thị biểu đồ: ' + error.message + '</div>';
        }
    } else {
        console.log('No monthly revenue chart data available');
        document.getElementById('monthlyRevenueChart').innerHTML = 
            '<div class="text-center py-5"><i class="fas fa-chart-line fa-3x text-muted mb-3"></i><p class="text-muted">Không có dữ liệu để hiển thị biểu đồ</p></div>';
    }
}

function createCollectorChart(chartData) {
    // Check if month selector exists - if so, skip old chart rendering
    const monthSelect = document.getElementById('collectorMonthSelect');
    if (monthSelect) {
        console.log('📊 [OLD_DASHBOARD_JS] Month selector detected - skipping old collector chart rendering');
        return;
    }
    
    if (chartData && typeof chartData === 'object' && 
        Object.keys(chartData).length > 0 && chartData.data && 
        Array.isArray(chartData.data) && chartData.data.length > 0 &&
        chartData.data[0].values && Array.isArray(chartData.data[0].values) &&
        chartData.data[0].values.length > 0 && chartData.layout) {
        try {
            Plotly.newPlot('collectorChart', chartData.data, chartData.layout, {
                responsive: true,
                displayModeBar: false
            });
            console.log('Collector chart rendered successfully');
        } catch (error) {
            console.error('Error rendering collector chart:', error);
            document.getElementById('collectorChart').innerHTML = 
                '<div class="alert alert-danger">Lỗi hiển thị biểu đồ: ' + error.message + '</div>';
        }
    } else {
        console.log('📊 [OLD_DASHBOARD_JS] No collector chart data available or empty values - but month selector will handle this');
        // Don't show error message - let the month selector handle chart rendering
    }
}

// ==================== OVERDUE GUESTS FUNCTIONS ====================
function toggleMoreOverdue() {
    const moreOverdue = document.getElementById('moreOverdueGuests');
    const button = event.target;
    
    if (moreOverdue.style.display === 'none') {
        moreOverdue.style.display = 'block';
        button.innerHTML = '<i class="fas fa-chevron-up me-1"></i> Thu gọn';
    } else {
        moreOverdue.style.display = 'none';
        const overdueCount = document.querySelectorAll('[id^="overdue_guest_"]').length - 3;
        button.innerHTML = `<i class="fas fa-chevron-down me-1"></i> Xem thêm ${overdueCount} khách`;
    }
}

// ==================== OVERCROWDED DAYS FUNCTIONS ====================
function toggleOvercrowdedDetails() {
    const details = document.getElementById('overcrowdedDetails');
    const toggleText = document.getElementById('overcrowdToggleText');
    
    if (details.style.display === 'none' || details.style.display === '') {
        details.style.display = 'block';
        toggleText.textContent = 'Ẩn chi tiết';
    } else {
        details.style.display = 'none';
        toggleText.textContent = 'Chi tiết';
    }
}

function showDayDetails(date, guestCount, guestNames, bookingIds) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-warning text-dark">
                    <h5 class="modal-title">
                        <i class="fas fa-users me-2"></i>Chi tiết ngày quá tải: ${date}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-warning">
                        <strong>⚠️ Cảnh báo:</strong> Ngày này có ${guestCount} khách check-in (vượt quá giới hạn 4 phòng)
                    </div>
                    
                    <h6 class="mb-3">Danh sách ${guestCount} khách check-in:</h6>
                    <div class="row">
                        ${guestNames.map((name, index) => `
                            <div class="col-md-6 mb-2">
                                <div class="card border-left-warning">
                                    <div class="card-body py-2 px-3">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <div class="fw-bold">${name || 'N/A'}</div>
                                                <small class="text-muted">ID: ${bookingIds[index] || 'N/A'}</small>
                                            </div>
                                            <span class="badge bg-warning">#${index + 1}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    
                    <div class="mt-3 p-3 bg-light rounded">
                        <h6 class="text-primary mb-2">💡 Gợi ý xử lý:</h6>
                        <ul class="mb-0 small">
                            <li>Kiểm tra xem có thể sắp xếp lại lịch check-in không</li>
                            <li>Liên hệ một số khách để thảo luận về check-in sớm/muộn</li>
                            <li>Chuẩn bị thêm nhân viên và tiện nghi cho ngày này</li>
                            <li>Xem xét việc upgrade phòng hoặc hỗ trợ đặc biệt</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Đóng</button>
                    <button type="button" class="btn btn-primary" onclick="goToCalendar('${date}')">
                        <i class="fas fa-calendar me-1"></i>Xem trong lịch
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', function() {
        modal.remove();
    });
}

function goToCalendar(dateStr) {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    window.open(`/calendar/${year}/${month}`, '_blank');
}

// ==================== PAYMENT COLLECTION FUNCTIONS ====================
function openCollectModal(bookingId, guestName, totalAmount, commission = 0, roomFee = 0, taxiFee = 0, collectedAmount = 0, collector = '', paymentNote = '') {
    console.log('🔍 Opening payment info modal (display-only):', {bookingId, guestName, totalAmount, collectedAmount, collector});
    
    currentBookingId = bookingId;
    currentTotalAmount = totalAmount;
    currentCommission = commission || 0;
    
    document.getElementById('modalGuestName').textContent = guestName;
    document.getElementById('modalBookingId').textContent = bookingId;
    
    // 🔍 Check if collector is valid - if not, collected amount should be 0
    const validCollectors = ['LOC LE', 'THAO LE'];
    const isValidCollector = collector && collector.trim() !== '' && validCollectors.includes(collector.trim());
    
    // Only show collected amount if there's a valid collector
    const collected = isValidCollector ? (collectedAmount || 0) : 0;
    const remaining = Math.max(0, totalAmount - collected);
    
    console.log('💰 Collector validation:', {collector, isValidCollector, collectedAmount, adjustedCollected: collected});
    
    const modalOriginalAmount = document.getElementById('modalOriginalAmount');
    const modalCollectedAmount = document.getElementById('modalCollectedAmount');
    const modalRemainingAmount = document.getElementById('modalRemainingAmount');
    
    if (modalOriginalAmount) {
        modalOriginalAmount.textContent = totalAmount.toLocaleString('vi-VN') + 'đ';
    } else {
        console.error('[CollectModal] modalOriginalAmount element not found');
    }
    
    if (modalCollectedAmount) {
        modalCollectedAmount.textContent = collected.toLocaleString('vi-VN') + 'đ';
    } else {
        console.error('[CollectModal] modalCollectedAmount element not found');
    }
    
    if (modalRemainingAmount) {
        modalRemainingAmount.textContent = remaining.toLocaleString('vi-VN') + 'đ';
    } else {
        console.error('[CollectModal] modalRemainingAmount element not found');
    }
    
    // Show commission information
    const commissionElement = document.getElementById('modalCommissionAmount');
    if (commissionElement) {
        if (currentCommission > 0) {
            commissionElement.textContent = currentCommission.toLocaleString('vi-VN') + 'đ';
            commissionElement.className = 'fw-bold text-warning fs-6';
        } else {
            commissionElement.textContent = 'Chưa có thông tin';
            commissionElement.className = 'text-muted fs-6';
        }
    }
    
    // Show collector information
    const collectorElement = document.getElementById('modalCollectorName');
    if (collectorElement) {
        if (collector && collector.trim() !== '') {
            collectorElement.textContent = collector;
            collectorElement.className = 'fw-bold text-success fs-6';
        } else {
            collectorElement.textContent = 'Chưa có người thu';
            collectorElement.className = 'text-muted fs-6';
        }
    }
    
    // Show payment note
    const noteElement = document.getElementById('modalPaymentNote');
    if (noteElement) {
        if (paymentNote && paymentNote.trim() !== '') {
            noteElement.textContent = paymentNote;
            noteElement.className = 'text-dark';
        } else {
            noteElement.textContent = 'Không có ghi chú';
            noteElement.className = 'text-muted';
        }
    }
    
    const modal = new bootstrap.Modal(document.getElementById('collectPaymentModal'));
    modal.show();
}

// ==================== LEGACY FUNCTION (DISABLED FOR DISPLAY-ONLY MODAL) ====================
// This function is no longer used as the collectPaymentModal is now display-only
// For actual payment collection, use the "Edit Collected Amount" button instead
async function collectPayment() {
    console.log('⚠️ collectPayment() called but modal is now display-only');
    console.log('💡 Use the "Edit Collected Amount" button for actual payment updates');
    
    // Simply close the modal since it's display-only
    const modal = bootstrap.Modal.getInstance(document.getElementById('collectPaymentModal'));
    if (modal) {
        modal.hide();
    }
    
    alert('ℹ️ Modal này chỉ để xem thông tin. Vui lòng sử dụng nút "Sửa" để thực hiện thu tiền.');
}

// ==================== EDIT COLLECTED AMOUNT FUNCTIONS ====================
function openEditCollectedModal(bookingId, guestName, totalAmount, currentCollected = 0, collector = '') {
    console.log('🔍 Opening Edit Collected Amount Modal:', {bookingId, guestName, totalAmount, currentCollected, collector});
    
    // 🔍 Check if collector is valid - if not, reset collected amount to 0
    const validCollectors = ['LOC LE', 'THAO LE'];
    const isValidCollector = collector && collector.trim() !== '' && validCollectors.includes(collector.trim());
    
    // Reset collected amount to 0 if no valid collector
    const adjustedCollectedAmount = isValidCollector ? (currentCollected || 0) : 0;
    
    console.log('💰 Edit Modal - Collector validation:', {
        collector, 
        isValidCollector, 
        originalCollected: currentCollected, 
        adjustedCollected: adjustedCollectedAmount
    });
    
    // Store data for later use
    window.currentCollectedData = {
        bookingId: bookingId,
        guestName: guestName,
        totalAmount: totalAmount,
        currentCollected: adjustedCollectedAmount
    };
    
    // Populate modal fields
    document.getElementById('collectedModalGuestName').textContent = guestName;
    document.getElementById('collectedModalBookingId').textContent = bookingId;
    document.getElementById('collectedModalTotalAmount').textContent = totalAmount.toLocaleString('vi-VN') + 'đ';
    document.getElementById('collectedModalCurrentAmount').textContent = adjustedCollectedAmount.toLocaleString('vi-VN') + 'đ';
    
    // Set adjusted amount as default in input (0 if no valid collector)
    document.getElementById('newCollectedAmount').value = adjustedCollectedAmount;
    document.getElementById('collectedNote').value = '';
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('editCollectedAmountModal'));
    modal.show();
}

async function updateCollectedAmount() {
    const newAmount = parseFloat(document.getElementById('newCollectedAmount').value) || 0;
    const note = document.getElementById('collectedNote').value.trim();
    const collector = document.getElementById('collectedCollectorName').value;
    
    if (!window.currentCollectedData) {
        alert('❌ Dữ liệu không hợp lệ. Vui lòng thử lại.');
        return;
    }
    
    const { bookingId, guestName, totalAmount } = window.currentCollectedData;
    
    // Validate collector selection
    if (!collector) {
        alert('❌ Vui lòng chọn người thu tiền!');
        return;
    }
    
    const validCollectors = ['LOC LE', 'THAO LE'];
    if (!validCollectors.includes(collector)) {
        alert('❌ Chỉ LOC LE và THAO LE được phép thu tiền!');
        return;
    }
    
    if (newAmount < 0) {
        alert('❌ Số tiền không thể âm!');
        return;
    }
    
    if (newAmount > totalAmount * 1.5) {
        if (!confirm(`⚠️ Số tiền thu (${newAmount.toLocaleString('vi-VN')}đ) lớn hơn nhiều so với tổng cần thu (${totalAmount.toLocaleString('vi-VN')}đ). Bạn có chắc chắn?`)) {
            return;
        }
    }
    
    const confirmBtn = document.getElementById('confirmCollectedBtn');
    const originalText = confirmBtn.innerHTML;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang cập nhật...';
    confirmBtn.disabled = true;
    
    try {
        const response = await fetch('/api/update_collected_amount', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                booking_id: bookingId,
                collected_amount: newAmount,
                collector_name: collector,
                note: note
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('editCollectedAmountModal'));
            modal.hide();
            
            showSuccessAlert(`✅ Đã cập nhật! Số tiền đã thu: ${newAmount.toLocaleString('vi-VN')}đ cho ${guestName}`);
            
            // Refresh page to show updated data
            setTimeout(() => { 
                window.location.reload();
            }, 2000);
        } else {
            alert('❌ Lỗi: ' + (result.message || 'Không thể cập nhật'));
        }
    } catch (error) {
        console.error('Update collected amount error:', error);
        alert('❌ Lỗi kết nối. Vui lòng thử lại!');
    } finally {
        confirmBtn.innerHTML = originalText;
        confirmBtn.disabled = false;
    }
}

// ==================== UTILITY FUNCTIONS ====================
function showSuccessAlert(message) {
    const successAlert = document.createElement('div');
    successAlert.className = 'alert alert-success alert-dismissible fade show position-fixed';
    successAlert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    successAlert.innerHTML = `
        <strong>✅ ${message}</strong>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(successAlert);
    
    setTimeout(() => {
        if (successAlert.parentNode) {
            successAlert.remove();
        }
    }, 5000);
}

// ==================== DASHBOARD REFRESH FUNCTIONS ====================
function refreshDashboardData() {
    console.log('🔄 Refreshing dashboard overdue data...');
    
    // Show loading indicator
    const overdueSection = document.querySelector('[data-section="overdue"]') || 
                          document.querySelector('.overdue-guests') ||
                          document.querySelector('#overdue-section');
    
    if (overdueSection) {
        const originalContent = overdueSection.innerHTML;
        overdueSection.innerHTML = `
            <div class="text-center py-3">
                <i class="fas fa-spinner fa-spin fa-2x text-primary mb-2"></i>
                <p class="text-muted">Đang cập nhật dữ liệu overdue payment...</p>
            </div>
        `;
        
        // Reload the page with fresh data parameter
        setTimeout(() => {
            const url = new URL(window.location);
            url.searchParams.set('refresh', 'true');
            window.location.href = url.toString();
        }, 1500);
    } else {
        // Fallback: reload the page with fresh data
        const url = new URL(window.location);
        url.searchParams.set('refresh', 'true');
        window.location.href = url.toString();
    }
}

// Listen for custom events from other pages (like edit booking page)
window.addEventListener('bookingUpdated', function(event) {
    console.log('📢 Received booking update event:', event.detail);
    refreshDashboardData();
});

// Add refresh button functionality if exists
document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.querySelector('[data-action="refresh-dashboard"]');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            refreshDashboardData();
        });
    }
});
