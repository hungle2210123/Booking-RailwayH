"""
Performance Dashboard for Railway Crawling
Real-time monitoring and optimization tracking
"""

from flask import Blueprint, jsonify, render_template_string
from core.optimized_railway_crawler import optimized_crawler
import json
from datetime import datetime, timedelta

performance_bp = Blueprint('performance', __name__)

@performance_bp.route('/api/crawl_performance', methods=['GET'])
def get_crawl_performance():
    """Get real-time crawling performance metrics"""
    try:
        report = optimized_crawler.get_performance_report()
        
        # Add current status
        rate_limiter = optimized_crawler.rate_limiter
        circuit_breaker = optimized_crawler.circuit_breaker
        
        current_status = {
            'budget_used_usd': rate_limiter.daily_cost,
            'budget_limit_usd': rate_limiter.cost_budget,
            'budget_remaining_usd': rate_limiter.cost_budget - rate_limiter.daily_cost,
            'budget_usage_percent': (rate_limiter.daily_cost / rate_limiter.cost_budget) * 100,
            'services_status': {}
        }
        
        # Service status
        for service in ['firecrawl', 'scrapfly', 'scraperapi', 'direct_http']:
            today = datetime.now().strftime('%Y-%m-%d')
            usage_key = f'{service}_{today}'
            daily_usage = rate_limiter.usage_tracker.get(usage_key, 0)
            daily_quota = rate_limiter.rate_limits[service]['daily_quota']
            
            current_status['services_status'][service] = {
                'daily_usage': daily_usage,
                'daily_quota': daily_quota if daily_quota != float('inf') else 'Unlimited',
                'quota_usage_percent': (daily_usage / daily_quota) * 100 if daily_quota != float('inf') else 0,
                'circuit_state': circuit_breaker.circuit_states.get(service, 'closed'),
                'failure_count': circuit_breaker.failure_counts.get(service, 0),
                'api_key_configured': service == 'direct_http' or bool(optimized_crawler.services[service].get('api_key_env') and 
                                                                      optimized_crawler.services[service]['api_key_env'] in ['FIRECRAWL_API_KEY', 'SCRAPFLY_API_KEY', 'SCRAPERAPI_KEY'])
            }
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'performance_report': report,
            'current_status': current_status,
            'optimization_recommendations': _get_optimization_recommendations(report, current_status)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_bp.route('/performance_dashboard')
def performance_dashboard():
    """HTML dashboard for performance monitoring"""
    dashboard_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Railway Crawling Performance Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
            .metric { text-align: center; padding: 15px; background: #f8f9fa; border-radius: 5px; }
            .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
            .metric-label { color: #6c757d; margin-top: 5px; }
            .status-good { color: #28a745; }
            .status-warning { color: #ffc107; }
            .status-danger { color: #dc3545; }
            .service-status { display: flex; justify-content: space-between; align-items: center; padding: 10px; margin: 5px 0; border-radius: 5px; }
            .service-available { background: #d4edda; border-left: 4px solid #28a745; }
            .service-limited { background: #fff3cd; border-left: 4px solid #ffc107; }
            .service-unavailable { background: #f8d7da; border-left: 4px solid #dc3545; }
            .chart-container { position: relative; height: 300px; margin: 20px 0; }
            .recommendations { background: #e7f3ff; border-left: 4px solid #007bff; padding: 15px; }
            .refresh-btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            .refresh-btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚂 Railway Crawling Performance Dashboard</h1>
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>
            
            <div id="loading" style="text-align: center; padding: 20px;">
                <p>Loading performance data...</p>
            </div>
            
            <div id="dashboard" style="display: none;">
                <!-- Metrics Overview -->
                <div class="card">
                    <h2>📊 Performance Metrics</h2>
                    <div class="metrics-grid" id="metricsGrid"></div>
                </div>
                
                <!-- Budget & Cost Tracking -->
                <div class="card">
                    <h2>💰 Cost Management</h2>
                    <div id="budgetInfo"></div>
                    <div class="chart-container">
                        <canvas id="costChart"></canvas>
                    </div>
                </div>
                
                <!-- Service Status -->
                <div class="card">
                    <h2>🛠️ Service Status</h2>
                    <div id="serviceStatus"></div>
                </div>
                
                <!-- Performance Chart -->
                <div class="card">
                    <h2>⚡ Performance by Method</h2>
                    <div class="chart-container">
                        <canvas id="performanceChart"></canvas>
                    </div>
                </div>
                
                <!-- Recommendations -->
                <div class="card">
                    <h2>🎯 Optimization Recommendations</h2>
                    <div id="recommendations" class="recommendations"></div>
                </div>
            </div>
        </div>
        
        <script>
            let performanceData = null;
            let costChart = null;
            let performanceChart = null;
            
            async function refreshData() {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('dashboard').style.display = 'none';
                
                try {
                    const response = await fetch('/api/crawl_performance');
                    const data = await response.json();
                    
                    if (data.success) {
                        performanceData = data;
                        updateDashboard();
                        document.getElementById('loading').style.display = 'none';
                        document.getElementById('dashboard').style.display = 'block';
                    } else {
                        alert('Error loading data: ' + data.error);
                    }
                } catch (error) {
                    alert('Network error: ' + error.message);
                    document.getElementById('loading').innerHTML = '<p style="color: red;">Error loading data. Please check your connection.</p>';
                }
            }
            
            function updateDashboard() {
                updateMetrics();
                updateBudgetInfo();
                updateServiceStatus();
                updateCharts();
                updateRecommendations();
            }
            
            function updateMetrics() {
                const report = performanceData.performance_report;
                const summary = report.summary || {};
                
                const metricsGrid = document.getElementById('metricsGrid');
                metricsGrid.innerHTML = `
                    <div class="metric">
                        <div class="metric-value">${summary.total_operations || 0}</div>
                        <div class="metric-label">Total Operations</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value ${getSuccessRateClass(summary.success_rate)}">${(summary.success_rate || 0).toFixed(1)}%</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${(summary.average_duration || 0).toFixed(2)}s</div>
                        <div class="metric-label">Avg Duration</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">$${(summary.total_cost_usd || 0).toFixed(4)}</div>
                        <div class="metric-label">Total Cost</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${formatBytes(summary.total_data_processed_bytes || 0)}</div>
                        <div class="metric-label">Data Processed</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${formatBytes(summary.average_throughput_bps || 0)}/s</div>
                        <div class="metric-label">Avg Throughput</div>
                    </div>
                `;
            }
            
            function updateBudgetInfo() {
                const status = performanceData.current_status;
                const budgetPercent = status.budget_usage_percent || 0;
                const budgetClass = budgetPercent > 80 ? 'status-danger' : budgetPercent > 60 ? 'status-warning' : 'status-good';
                
                document.getElementById('budgetInfo').innerHTML = `
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <span>Budget Used:</span>
                        <span class="${budgetClass}">$${status.budget_used_usd.toFixed(4)} / $${status.budget_limit_usd}</span>
                    </div>
                    <div style="background: #e9ecef; border-radius: 5px; overflow: hidden;">
                        <div style="width: ${budgetPercent}%; height: 20px; background: ${budgetPercent > 80 ? '#dc3545' : budgetPercent > 60 ? '#ffc107' : '#28a745'}; transition: width 0.3s;"></div>
                    </div>
                    <small style="color: #6c757d;">Remaining: $${status.budget_remaining_usd.toFixed(4)} (${(100 - budgetPercent).toFixed(1)}%)</small>
                `;
            }
            
            function updateServiceStatus() {
                const services = performanceData.current_status.services_status;
                const serviceStatus = document.getElementById('serviceStatus');
                
                let html = '';
                for (const [service, status] of Object.entries(services)) {
                    const statusClass = getServiceStatusClass(status);
                    const quotaText = status.daily_quota === 'Unlimited' ? 'Unlimited' : `${status.daily_usage}/${status.daily_quota}`;
                    
                    html += `
                        <div class="service-status ${statusClass}">
                            <div>
                                <strong>${service.toUpperCase()}</strong>
                                <span style="margin-left: 10px; font-size: 0.9em;">
                                    Circuit: ${status.circuit_state} | 
                                    API Key: ${status.api_key_configured ? '✅' : '❌'} |
                                    Usage: ${quotaText}
                                </span>
                            </div>
                            <div>
                                ${status.quota_usage_percent > 0 ? status.quota_usage_percent.toFixed(1) + '%' : '0%'}
                            </div>
                        </div>
                    `;
                }
                serviceStatus.innerHTML = html;
            }
            
            function updateCharts() {
                // Update cost chart
                const costData = performanceData.performance_report.cost_breakdown || {};
                updateCostChart(costData);
                
                // Update performance chart
                const methodData = performanceData.performance_report.method_performance || {};
                updatePerformanceChart(methodData);
            }
            
            function updateCostChart(costData) {
                const ctx = document.getElementById('costChart').getContext('2d');
                
                if (costChart) {
                    costChart.destroy();
                }
                
                costChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(costData),
                        datasets: [{
                            data: Object.values(costData),
                            backgroundColor: ['#007bff', '#28a745', '#ffc107', '#dc3545']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Cost Breakdown by Service'
                            }
                        }
                    }
                });
            }
            
            function updatePerformanceChart(methodData) {
                const ctx = document.getElementById('performanceChart').getContext('2d');
                
                if (performanceChart) {
                    performanceChart.destroy();
                }
                
                const methods = Object.keys(methodData);
                const successRates = methods.map(m => (methodData[m].success / methodData[m].count) * 100);
                const avgDurations = methods.map(m => methodData[m].avg_duration);
                
                performanceChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: methods,
                        datasets: [{
                            label: 'Success Rate (%)',
                            data: successRates,
                            backgroundColor: '#28a745',
                            yAxisID: 'y'
                        }, {
                            label: 'Avg Duration (s)',
                            data: avgDurations,
                            backgroundColor: '#007bff',
                            yAxisID: 'y1'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                max: 100
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                grid: {
                                    drawOnChartArea: false,
                                }
                            }
                        }
                    }
                });
            }
            
            function updateRecommendations() {
                const recommendations = performanceData.optimization_recommendations;
                const recommendationsDiv = document.getElementById('recommendations');
                
                let html = '<ul>';
                recommendations.forEach(rec => {
                    html += `<li><strong>${rec.title}:</strong> ${rec.description}</li>`;
                });
                html += '</ul>';
                
                recommendationsDiv.innerHTML = html;
            }
            
            function getSuccessRateClass(rate) {
                if (rate >= 90) return 'status-good';
                if (rate >= 70) return 'status-warning';
                return 'status-danger';
            }
            
            function getServiceStatusClass(status) {
                if (!status.api_key_configured || status.circuit_state === 'open') {
                    return 'service-unavailable';
                }
                if (status.quota_usage_percent > 80 || status.circuit_state === 'half-open') {
                    return 'service-limited';
                }
                return 'service-available';
            }
            
            function formatBytes(bytes) {
                if (bytes === 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }
            
            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);
            
            // Initial load
            refreshData();
        </script>
    </body>
    </html>
    """
    return dashboard_html

def _get_optimization_recommendations(report, current_status):
    """Generate optimization recommendations based on performance data"""
    recommendations = []
    
    # Budget recommendations
    budget_usage = current_status.get('budget_usage_percent', 0)
    if budget_usage > 80:
        recommendations.append({
            'title': 'High Budget Usage',
            'description': f'You\'ve used {budget_usage:.1f}% of your budget. Consider using lower-cost services or implementing more aggressive caching.'
        })
    
    # Success rate recommendations
    summary = report.get('summary', {})
    success_rate = summary.get('success_rate', 0)
    if success_rate < 90:
        recommendations.append({
            'title': 'Low Success Rate',
            'description': f'Success rate is {success_rate:.1f}%. Implement retry mechanisms and check service reliability.'
        })
    
    # Performance recommendations
    avg_duration = summary.get('average_duration', 0)
    if avg_duration > 10:
        recommendations.append({
            'title': 'Slow Performance',
            'description': f'Average duration is {avg_duration:.1f}s. Consider using faster services or implementing caching.'
        })
    
    # Service status recommendations
    services = current_status.get('services_status', {})
    for service, status in services.items():
        if not status['api_key_configured'] and service != 'direct_http':
            recommendations.append({
                'title': f'{service.title()} Not Configured',
                'description': f'Configure {service.upper()}_API_KEY to enable this crawling method.'
            })
        
        if status['quota_usage_percent'] > 90:
            recommendations.append({
                'title': f'{service.title()} Quota Nearly Exhausted',
                'description': f'{service} has used {status["quota_usage_percent"]:.1f}% of daily quota. Consider upgrading or using alternative services.'
            })
    
    # Default recommendations if none specific
    if not recommendations:
        recommendations.append({
            'title': 'System Running Optimally',
            'description': 'All metrics are within acceptable ranges. Consider monitoring trends for continued optimization.'
        })
    
    return recommendations