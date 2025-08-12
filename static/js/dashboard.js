// OEE Dashboard JavaScript

// Global variables
let wsConnection = null;
let metricsUpdateInterval = null;

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    setupWebSocketConnection();
    startMetricsUpdates();
    setupNotifications();
});

// Initialize dashboard components
function initializeDashboard() {
    // Animate metrics on load
    animateCounters();
    
    // Setup tooltip triggers
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in');
        }, index * 100);
    });
}

// Animate numeric counters
function animateCounters() {
    const counters = document.querySelectorAll('.metric-value');
    
    counters.forEach(counter => {
        const target = parseFloat(counter.textContent.replace(/[^\d.-]/g, ''));
        const increment = target / 100;
        let current = 0;
        
        const updateCounter = () => {
            if (current < target) {
                current += increment;
                if (counter.textContent.includes('%')) {
                    counter.textContent = current.toFixed(1) + '%';
                } else {
                    counter.textContent = Math.round(current).toLocaleString();
                }
                requestAnimationFrame(updateCounter);
            } else {
                if (counter.textContent.includes('%')) {
                    counter.textContent = target.toFixed(1) + '%';
                } else {
                    counter.textContent = Math.round(target).toLocaleString();
                }
            }
        };
        
        updateCounter();
    });
}

// WebSocket connection for real-time updates
function setupWebSocketConnection() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events/`;
    
    wsConnection = new WebSocket(wsUrl);
    
    wsConnection.onopen = function(e) {
        console.log('WebSocket connected');
        showToast('Connected to real-time updates', 'success');
    };
    
    wsConnection.onmessage = function(e) {
        const data = JSON.parse(e.data);
        handleRealtimeUpdate(data);
    };
    
    wsConnection.onclose = function(e) {
        console.log('WebSocket disconnected');
        showToast('Lost connection to real-time updates', 'warning');
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
            setupWebSocketConnection();
        }, 3000);
    };
    
    wsConnection.onerror = function(e) {
        console.error('WebSocket error:', e);
        showToast('Connection error', 'danger');
    };
}

// Handle real-time updates from WebSocket
function handleRealtimeUpdate(data) {
    switch(data.type) {
        case 'downtime_alert':
            showDowntimeAlert(data);
            break;
        case 'oee_update':
            updateOEEMetrics(data);
            break;
        case 'challenge_complete':
            showChallengeComplete(data);
            break;
        case 'achievement_earned':
            showAchievementEarned(data);
            break;
    }
}

// Show downtime alert
function showDowntimeAlert(data) {
    const alertHtml = `
        <div class="alert alert-danger alert-dismissible fade show downtime-alert" role="alert">
            <div class="d-flex align-items-center">
                <div class="alert-icon me-3">
                    <i class="fas fa-exclamation-triangle fa-2x"></i>
                </div>
                <div class="flex-grow-1">
                    <h5 class="alert-heading mb-1">⚠️ ${data.title}</h5>
                    <p class="mb-2">${data.message}</p>
                    <div class="d-flex align-items-center gap-3">
                        <div class="timer-display">
                            <i class="fas fa-clock me-1"></i>
                            <span id="timer-${data.machine}">5:00</span>
                        </div>
                        <button class="btn btn-sm btn-warning" onclick="acknowledgeDowntime(${data.machine})">
                            I'm On It! 💪
                        </button>
                    </div>
                </div>
                <div class="xp-reward">
                    <span class="badge bg-primary fs-6">+${data.xp_reward} XP</span>
                </div>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.getElementById('alert-container').innerHTML = alertHtml;
    
    // Start countdown timer
    startDowntimeTimer(data.machine, data.timer);
    
    // Play alert sound
    playAlertSound();
}

// Start countdown timer for downtime alerts
function startDowntimeTimer(machineId, seconds) {
    let timeLeft = seconds;
    
    const timerElement = document.getElementById(`timer-${machineId}`);
    if (!timerElement) return;
    
    const interval = setInterval(() => {
        timeLeft--;
        
        const minutes = Math.floor(timeLeft / 60);
        const secs = timeLeft % 60;
        timerElement.textContent = `${minutes}:${secs.toString().padStart(2, '0')}`;
        
        // Change color as time runs out
        if (timeLeft <= 60) {
            timerElement.className = 'text-danger fw-bold';
        } else if (timeLeft <= 120) {
            timerElement.className = 'text-warning fw-bold';
        }
        
        if (timeLeft <= 0) {
            clearInterval(interval);
            timerElement.textContent = 'Time Up!';
            timerElement.className = 'text-danger fw-bold';
        }
    }, 1000);
}

// Acknowledge downtime
function acknowledgeDowntime(machineId) {
    fetch(`/api/acknowledge-downtime/${machineId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    }).then(response => {
        if (response.ok) {
            showToast('Downtime acknowledged. Good luck! 🔧', 'success');
        }
    });
}

// Play alert sound
function playAlertSound() {
    const audio = new Audio('/static/sounds/alert.mp3');
    audio.volume = 0.5;
    audio.play().catch(e => {
        console.log('Could not play alert sound:', e);
    });
}

// Start periodic metrics updates
function startMetricsUpdates() {
    metricsUpdateInterval = setInterval(() => {
        updateMetrics();
    }, 5000); // Update every 5 seconds
}

// Update metrics from API
function updateMetrics() {
    fetch('/api/current-metrics/')
        .then(response => response.json())
        .then(data => {
            updateOEEMetrics(data);
        })
        .catch(error => {
            console.error('Error updating metrics:', error);
        });
}

// Update OEE metrics in UI
function updateOEEMetrics(data) {
    // Update main OEE score
    const oeeElement = document.getElementById('current-oee');
    if (oeeElement) {
        animateValueChange(oeeElement, data.oee.toFixed(1));
    }
    
    // Update component metrics
    updateMetricElement('availability', data.availability.toFixed(1) + '%');
    updateMetricElement('performance', data.performance.toFixed(1) + '%');
    updateMetricElement('quality', data.quality.toFixed(1) + '%');
    updateMetricElement('production-count', data.production_count.toLocaleString());
    
    // Update progress bar
    const progressBar = document.getElementById('oee-progress');
    if (progressBar) {
        progressBar.style.width = data.oee + '%';
        progressBar.className = `progress-bar ${getOEEProgressClass(data.oee)}`;
    }
}

// Update individual metric element
function updateMetricElement(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (element) {
        animateValueChange(element, newValue);
    }
}

// Animate value change
function animateValueChange(element, newValue) {
    element.style.transform = 'scale(1.1)';
    element.style.transition = 'transform 0.3s ease';
    
    setTimeout(() => {
        element.textContent = newValue;
        element.style.transform = 'scale(1)';
    }, 150);
}

// Get progress bar class based on OEE value
function getOEEProgressClass(oee) {
    if (oee >= 90) return 'bg-success';
    if (oee >= 80) return 'bg-info';
    if (oee >= 70) return 'bg-warning';
    return 'bg-danger';
}

// Show challenge completion
function showChallengeComplete(data) {
    showToast(
        `🎉 Challenge Complete! "${data.challenge}" earned ${data.xp} XP!`,
        'success',
        5000
    );
    
    // Update XP display if exists
    updateXPDisplay(data.total_xp);
}

// Show achievement earned
function showAchievementEarned(data) {
    showToast(
        `🏆 Achievement Unlocked! "${data.achievement}" (+${data.xp} XP)`,
        'warning',
        7000
    );
    
    // Show achievement modal
    showAchievementModal(data);
}

// Show achievement modal
function showAchievementModal(achievement) {
    const modalHtml = `
        <div class="modal fade" id="achievementModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">🏆 Achievement Unlocked!</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <div class="achievement-badge mb-3">
                            <i class="fas fa-medal fa-5x text-warning"></i>
                        </div>
                        <h4>${achievement.name}</h4>
                        <p class="text-muted">${achievement.description}</p>
                        <div class="xp-earned">
                            <span class="badge bg-primary fs-5">+${achievement.xp} XP</span>
                        </div>
                    </div>
                    <div class="modal-footer justify-content-center">
                        <button type="button" class="btn btn-warning" data-bs-dismiss="modal">
                            Awesome! 🎉
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('achievementModal'));
    modal.show();
    
    // Remove modal from DOM after hiding
    modal._element.addEventListener('hidden.bs.modal', () => {
        modal._element.remove();
    });
}

// Setup notifications
function setupNotifications() {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Setup notification click handler
    document.getElementById('notification-btn').addEventListener('click', function() {
        toggleNotificationPanel();
    });
}

// Toggle notification panel
function toggleNotificationPanel() {
    // Implementation for notification dropdown/panel
    console.log('Toggle notifications');
}

// Show toast notification
function showToast(message, type = 'info', duration = 4000) {
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert" data-bs-delay="${duration}">
            <div class="toast-header bg-${type} text-white">
                <i class="fas fa-info-circle me-2"></i>
                <strong class="me-auto">OEE Hub</strong>
                <small class="text-white-50">${new Date().toLocaleTimeString()}</small>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    document.getElementById('toast-container').insertAdjacentHTML('beforeend', toastHtml);
    
    const toast = new bootstrap.Toast(document.getElementById(toastId));
    toast.show();
    
    // Remove from DOM after hiding
    toast._element.addEventListener('hidden.bs.toast', () => {
        toast._element.remove();
    });
}

// Update XP display
function updateXPDisplay(totalXP) {
    const xpElements = document.querySelectorAll('.xp-display');
    xpElements.forEach(element => {
        element.textContent = `${totalXP} XP`;
    });
}

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (wsConnection) {
        wsConnection.close();
    }
    if (metricsUpdateInterval) {
        clearInterval(metricsUpdateInterval);
    }
});