# 🔒 **AudioCrypt Security Enhancement Guide**

## **Critical Security Issues & Solutions**

### **1. Session Security**

**❌ Current Issue:**
```python
# RSA private keys stored in session (memory exposure risk)
session['rsa_private_pem'] = user['private_key_pem']
```

**✅ Recommended Solution:**
```python
# Store keys encrypted with session-specific key
from cryptography.fernet import Fernet

def encrypt_session_data(data, session_key):
    f = Fernet(session_key)
    return f.encrypt(data.encode()).decode()

def decrypt_session_data(encrypted_data, session_key):
    f = Fernet(session_key)
    return f.decrypt(encrypted_data.encode()).decode()

# In login route:
session_key = Fernet.generate_key()
session['encrypted_private_key'] = encrypt_session_data(user['private_key_pem'], session_key)
session['key_id'] = store_session_key_securely(session_key)  # Store in Redis/DB
```

### **2. Rate Limiting**

**❌ Current Issue:** No rate limiting on authentication endpoints

**✅ Recommended Solution:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    # Login logic here
    pass
```

### **3. Input Validation Enhancement**

**❌ Current Issue:** Basic validation only

**✅ Recommended Solution:**
```python
from marshmallow import Schema, fields, validate, ValidationError

class FileUploadSchema(Schema):
    filename = fields.String(required=True, validate=validate.Length(max=100))
    file_size = fields.Integer(required=True, validate=validate.Range(min=1, max=16*1024*1024))
    content_type = fields.String(required=True, validate=validate.OneOf([
        'audio/mpeg', 'audio/wav', 'audio/flac', 'audio/ogg', 'audio/mp4'
    ]))

def validate_file_upload(request_data):
    schema = FileUploadSchema()
    try:
        return schema.load(request_data)
    except ValidationError as err:
        raise ValueError(f"Invalid file upload: {err.messages}")
```

### **4. Database Security**

**❌ Current Issues:**
- No input sanitization for MongoDB queries
- Missing indexes for performance and security

**✅ Recommended Solution:**
```python
from pymongo import IndexModel, TEXT

# Create security indexes
def create_security_indexes():
    # User collection indexes
    users_collection.create_index("username", unique=True)
    users_collection.create_index("created_at")
    
    # Files collection indexes
    encrypted_files_collection.create_index([("user", 1), ("created_at", -1)])
    encrypted_files_collection.create_index("encrypted_filename", unique=True)
    
    # Add text search capability
    encrypted_files_collection.create_index([("original_filename", TEXT)])

# Sanitize MongoDB queries
def safe_find_user(username):
    # Prevent NoSQL injection
    if not isinstance(username, str) or len(username) > 50:
        raise ValueError("Invalid username format")
    
    return users_collection.find_one({"username": {"$eq": username}})
```

### **5. File Access Security**

**❌ Current Issue:** Basic filename-based access control

**✅ Recommended Solution:**
```python
import secrets
from pathlib import Path

def secure_file_path(user_id, original_filename):
    """Generate secure file paths with user isolation"""
    # Create user-specific directory
    user_dir = Path(app.config['UPLOAD_FOLDER']) / f"user_{user_id}"
    user_dir.mkdir(exist_ok=True)
    
    # Generate cryptographically secure filename
    secure_name = secrets.token_urlsafe(16)
    file_ext = Path(original_filename).suffix
    
    return user_dir / f"{secure_name}{file_ext}"

def verify_file_access(user_id, file_path):
    """Verify user has access to file"""
    user_dir = Path(app.config['UPLOAD_FOLDER']) / f"user_{user_id}"
    try:
        # Resolve path and check it's within user directory
        resolved_path = Path(file_path).resolve()
        user_dir_resolved = user_dir.resolve()
        
        return resolved_path.is_relative_to(user_dir_resolved)
    except (OSError, ValueError):
        return False
```

### **6. Error Handling Security**

**❌ Current Issue:** Potential information disclosure in error messages

**✅ Recommended Solution:**
```python
import uuid
from flask import request

class SecurityError(Exception):
    """Custom security exception"""
    pass

@app.errorhandler(SecurityError)
def handle_security_error(error):
    error_id = str(uuid.uuid4())
    app.logger.error(f"Security error {error_id}: {error} from IP: {request.remote_addr}")
    
    return render_template('error.html', 
                         message="A security error occurred. Please contact support.",
                         error_id=error_id), 403

@app.errorhandler(500)
def handle_internal_error(error):
    error_id = str(uuid.uuid4())
    app.logger.error(f"Internal error {error_id}: {error}")
    
    if app.debug:
        # Show detailed error in debug mode
        return render_template('error_debug.html', error=error), 500
    else:
        # Generic error message in production
        return render_template('error.html', 
                             message="An internal error occurred.",
                             error_id=error_id), 500
```

### **7. HTTPS and Security Headers**

**✅ Recommended Implementation:**
```python
from flask_talisman import Talisman

# Force HTTPS and add security headers
csp = {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' https://cdn.tailwindcss.com",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data:",
}

Talisman(app, 
         force_https=True,
         strict_transport_security=True,
         content_security_policy=csp)

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response
```

### **8. Audit Logging**

**✅ Recommended Implementation:**
```python
import json
from datetime import datetime

class SecurityAuditLogger:
    def __init__(self, logger):
        self.logger = logger
    
    def log_auth_event(self, event_type, username, ip_address, success=True, details=None):
        audit_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'username': username,
            'ip_address': ip_address,
            'success': success,
            'details': details or {}
        }
        
        if success:
            self.logger.info(f"AUTH_SUCCESS: {json.dumps(audit_data)}")
        else:
            self.logger.warning(f"AUTH_FAILURE: {json.dumps(audit_data)}")
    
    def log_file_event(self, event_type, username, filename, ip_address, details=None):
        audit_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'username': username,
            'filename': filename,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        self.logger.info(f"FILE_EVENT: {json.dumps(audit_data)}")

# Usage in routes:
audit_logger = SecurityAuditLogger(app.logger)

@app.route('/login', methods=['POST'])
def login():
    # ... login logic ...
    if successful_login:
        audit_logger.log_auth_event('LOGIN', username, request.remote_addr, True)
    else:
        audit_logger.log_auth_event('LOGIN', username, request.remote_addr, False)
```

## **Environment Configuration**

**✅ Production .env file:**
```bash
# Security
SECRET_KEY=your-production-secret-key-32-chars-minimum
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# Database
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/audiocrypt

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/audiocrypt/app.log

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://redis:6379

# File Upload
MAX_CONTENT_LENGTH=50000000
ALLOWED_EXTENSIONS=mp3,wav,flac,ogg,m4a

# Monitoring
SENTRY_DSN=your-sentry-dsn-for-error-tracking
```

## **Deployment Security Checklist**

- [ ] **HTTPS enforced** (SSL/TLS certificate configured)
- [ ] **Database credentials** stored securely (not in code)
- [ ] **SECRET_KEY** is cryptographically secure and unique
- [ ] **Rate limiting** implemented on all public endpoints
- [ ] **Input validation** on all user inputs
- [ ] **CSRF protection** enabled on all forms
- [ ] **Security headers** configured
- [ ] **Error handling** doesn't leak sensitive information
- [ ] **Audit logging** implemented for security events
- [ ] **File uploads** restricted by type, size, and location
- [ ] **Session management** is secure (encrypted, proper expiration)
- [ ] **Database queries** are parameterized/sanitized

## **Security Testing**

**✅ Recommended Security Tests:**
```python
import pytest
from app import app

def test_sql_injection_protection():
    """Test protection against NoSQL injection"""
    with app.test_client() as client:
        # Try to inject NoSQL operators
        response = client.post('/login', data={
            'username': {'$ne': None},
            'password': {'$ne': None}
        })
        assert response.status_code != 200

def test_rate_limiting():
    """Test rate limiting on login endpoint"""
    with app.test_client() as client:
        # Make multiple rapid requests
        for _ in range(10):
            response = client.post('/login', data={
                'username': 'test',
                'password': 'test'
            })
        
        # Should be rate limited
        assert response.status_code == 429

def test_file_path_traversal():
    """Test protection against path traversal attacks"""
    with app.test_client() as client:
        # Try to access files outside allowed directory
        response = client.get('/download/../../../etc/passwd')
        assert response.status_code == 404
```

## **Monitoring and Alerting**

**✅ Security Monitoring Setup:**
```python
# Alert on suspicious activities
class SecurityMonitor:
    def __init__(self):
        self.failed_logins = {}
        self.suspicious_ips = set()
    
    def check_failed_logins(self, ip_address):
        """Monitor failed login attempts"""
        current_time = time.time()
        
        if ip_address not in self.failed_logins:
            self.failed_logins[ip_address] = []
        
        # Clean old attempts (older than 1 hour)
        self.failed_logins[ip_address] = [
            timestamp for timestamp in self.failed_logins[ip_address]
            if current_time - timestamp < 3600
        ]
        
        self.failed_logins[ip_address].append(current_time)
        
        # Alert if more than 5 failed attempts in 1 hour
        if len(self.failed_logins[ip_address]) >= 5:
            self.alert_suspicious_activity(ip_address, 'excessive_failed_logins')
            self.suspicious_ips.add(ip_address)
    
    def alert_suspicious_activity(self, ip_address, activity_type):
        """Send security alert"""
        app.logger.critical(f"SECURITY_ALERT: {activity_type} from {ip_address}")
        # Send to monitoring system (Slack, email, etc.)
```

This comprehensive security guide addresses the most critical vulnerabilities identified in the code review and provides practical, implementable solutions for production deployment.