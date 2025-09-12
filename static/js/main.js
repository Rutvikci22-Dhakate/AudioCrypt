// AudioCrypt - Main JavaScript Functions
// Enhanced user interactions and form handling

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize file upload handling
    initFileUploads();
    
    // Initialize form validation
    initFormValidation();
    
    // Initialize UI interactions
    initUIInteractions();
    
    // Initialize progress tracking
    initProgressTracking();
    
    console.log('AudioCrypt JavaScript initialized successfully');
}

// File Upload Enhancements
function initFileUploads() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            handleFileSelection(e.target);
        });
        
        // Add drag and drop functionality
        const container = input.closest('.file-upload-container') || input.parentElement;
        if (container) {
            addDragDropToContainer(container, input);
        }
    });
}

function handleFileSelection(input) {
    const files = input.files;
    const maxSize = 16 * 1024 * 1024; // 16MB
    const allowedTypes = ['audio/mpeg', 'audio/wav', 'audio/flac', 'audio/ogg', 'audio/mp4'];
    
    let validFiles = 0;
    let totalSize = 0;
    
    // Validate files
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        if (file.size > maxSize) {
            showAlert(`File "${file.name}" is too large. Maximum size is 16MB.`, 'error');
            continue;
        }
        
        if (!allowedTypes.includes(file.type) && !isAudioFileByExtension(file.name)) {
            showAlert(`File "${file.name}" is not a supported audio format.`, 'error');
            continue;
        }
        
        validFiles++;
        totalSize += file.size;
    }
    
    // Update UI with file information
    updateFileInfo(input, validFiles, totalSize);
}

function isAudioFileByExtension(filename) {
    const audioExtensions = ['.mp3', '.wav', '.flac', '.ogg', '.m4a'];
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return audioExtensions.includes(ext);
}

function addDragDropToContainer(container, input) {
    container.addEventListener('dragover', function(e) {
        e.preventDefault();
        container.classList.add('drag-over');
    });
    
    container.addEventListener('dragleave', function(e) {
        e.preventDefault();
        container.classList.remove('drag-over');
    });
    
    container.addEventListener('drop', function(e) {
        e.preventDefault();
        container.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            input.files = files;
            handleFileSelection(input);
        }
    });
}

function updateFileInfo(input, validFiles, totalSize) {
    const infoElement = input.parentElement.querySelector('.file-info');
    if (infoElement) {
        const sizeText = formatFileSize(totalSize);
        infoElement.textContent = `${validFiles} file(s) selected (${sizeText})`;
        infoElement.style.display = validFiles > 0 ? 'block' : 'none';
    }
}

// Form Validation and Enhancement
function initFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(form)) {
                e.preventDefault();
                return false;
            }
            
            // Add loading state
            showFormLoading(form);
        });
    });
}

function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        } else {
            clearFieldError(field);
        }
    });
    
    // Validate file inputs
    const fileInputs = form.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        if (input.hasAttribute('required') && input.files.length === 0) {
            showFieldError(input, 'Please select at least one file');
            isValid = false;
        }
    });
    
    return isValid;
}

function showFieldError(field, message) {
    clearFieldError(field);
    
    const errorElement = document.createElement('div');
    errorElement.className = 'field-error text-red-400 text-sm mt-1';
    errorElement.textContent = message;
    
    field.classList.add('border-red-400');
    field.parentElement.appendChild(errorElement);
}

function clearFieldError(field) {
    field.classList.remove('border-red-400');
    const existingError = field.parentElement.querySelector('.field-error');
    if (existingError) {
        existingError.remove();
    }
}

function showFormLoading(form) {
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');
        submitBtn.textContent = 'Processing...';
    }
}

// UI Interactions
function initUIInteractions() {
    // Initialize download buttons
    initDownloadButtons();
    
    // Initialize delete confirmations
    initDeleteConfirmations();
    
    // Initialize tooltips
    initTooltips();
    
    // Initialize card animations
    initCardAnimations();
}

function initDownloadButtons() {
    const downloadBtns = document.querySelectorAll('.download-btn');
    
    downloadBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            const button = e.target.closest('button') || e.target.closest('a');
            if (button) {
                button.classList.add('loading');
                setTimeout(() => {
                    button.classList.remove('loading');
                }, 2000);
            }
        });
    });
}

function initDeleteConfirmations() {
    const deleteBtns = document.querySelectorAll('.delete-btn');
    
    deleteBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const filename = btn.dataset.filename || 'this file';
            if (confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
                // Submit the form
                const form = btn.closest('form');
                if (form) {
                    form.submit();
                }
            }
        });
    });
}

function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            showTooltip(element, element.dataset.tooltip);
        });
        
        element.addEventListener('mouseleave', function() {
            hideTooltip();
        });
    });
}

function showTooltip(element, text) {
    hideTooltip(); // Remove any existing tooltip
    
    const tooltip = document.createElement('div');
    tooltip.id = 'tooltip';
    tooltip.className = 'absolute z-50 bg-gray-800 text-white px-2 py-1 rounded text-sm pointer-events-none';
    tooltip.textContent = text;
    
    document.body.appendChild(tooltip);
    
    const rect = element.getBoundingClientRect();
    tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

function initCardAnimations() {
    const cards = document.querySelectorAll('.file-card, .glass-card');
    
    cards.forEach((card, index) => {
        // Add staggered animation delay
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in');
    });
}

// Progress Tracking
function initProgressTracking() {
    // Track form submissions and show progress
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            if (form.querySelector('input[type="file"]')) {
                showProgressBar();
            }
        });
    });
}

function showProgressBar() {
    const progressContainer = document.createElement('div');
    progressContainer.id = 'progress-container';
    progressContainer.className = 'fixed top-0 left-0 w-full bg-gray-800 bg-opacity-50 z-50';
    
    const progressBar = document.createElement('div');
    progressBar.className = 'bg-blue-500 h-1 transition-all duration-300';
    progressBar.style.width = '0%';
    
    progressContainer.appendChild(progressBar);
    document.body.appendChild(progressContainer);
    
    // Simulate progress
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress > 90) progress = 90;
        
        progressBar.style.width = progress + '%';
        
        if (progress >= 90) {
            clearInterval(interval);
        }
    }, 200);
}

// Utility Functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || createAlertContainer();
    
    const alert = document.createElement('div');
    alert.className = `alert-${type} p-4 rounded-lg mb-4 border fade-in`;
    alert.textContent = message;
    
    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'float-right ml-4 text-xl leading-none';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => alert.remove());
    
    alert.appendChild(closeBtn);
    alertContainer.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.className = 'fixed top-4 right-4 z-50 max-w-sm';
    document.body.appendChild(container);
    return container;
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S to save/submit forms
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const form = document.querySelector('form');
        if (form) {
            form.submit();
        }
    }
    
    // Escape to close modals/alerts
    if (e.key === 'Escape') {
        const alerts = document.querySelectorAll('#alert-container .alert-info, #alert-container .alert-error');
        alerts.forEach(alert => alert.remove());
        
        hideTooltip();
    }
});

// Export functions for use in templates
window.AudioCrypt = {
    showAlert,
    formatFileSize,
    showProgressBar
};