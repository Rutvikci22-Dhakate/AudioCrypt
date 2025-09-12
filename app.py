import os
import time
import logging
from datetime import datetime

# Flask and Web Framework
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, abort
from flask_session import Session
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp
from werkzeug.utils import secure_filename

# Third-party packages
from dotenv import load_dotenv
from pymongo import MongoClient
import bcrypt
from bson.objectid import ObjectId

# Cryptography
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import base64

# ----------------------
# Configuration & Setup
# ----------------------
from config import DevelopmentConfig, ProductionConfig

load_dotenv()

app = Flask(__name__)

# Load configuration based on environment
config_class = DevelopmentConfig if os.getenv('FLASK_ENV') == 'development' else ProductionConfig
app.config.from_object(config_class)

# Initialize extensions
Session(app)
csrf = CSRFProtect(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=50, message="Username must be between 3 and 50 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters")
    ])
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=50, message="Username must be between 3 and 50 characters"),
        Regexp('^[A-Za-z0-9_]+$', message="Username can only contain letters, numbers, and underscores")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, max=128, message="Password must be between 8 and 128 characters"),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', message="Password must contain at least one lowercase letter, one uppercase letter, and one digit")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField('Register')

# ----------------------
# Constants
# ----------------------
# Load constants from configuration
ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']
MAX_FILENAME_LENGTH = app.config['MAX_FILENAME_LENGTH']
RSA_KEY_SIZE = app.config['RSA_KEY_SIZE']
BCRYPT_ROUNDS = app.config['BCRYPT_ROUNDS']
AES_KEY_SIZE = app.config['AES_KEY_SIZE']
GCM_NONCE_SIZE = app.config['GCM_NONCE_SIZE']

# ----------------------
# Database Setup
# ----------------------
def init_database():
    """Initialize MongoDB connection with error handling"""
    try:
        mongo_uri = app.config['MONGO_URI']
        client = MongoClient(mongo_uri)
        
        # Test connection
        client.admin.command('ping')
        
        db = client.audio_encryption_db
        users_collection = db.users
        encrypted_files_collection = db.encrypted_files
        
        app.logger.info("MongoDB connection successful")
        return client, users_collection, encrypted_files_collection
        
    except Exception as e:
        app.logger.error(f"MongoDB connection failed: {e}")
        raise ConnectionError(f"Database connection failed: {e}")

# Initialize database
try:
    client, users_collection, encrypted_files_collection = init_database()
except ConnectionError as e:
    print(f"\n❌ MongoDB Connection Error: {e}")
    print("\n🔧 Solutions:")
    print("1. Start MongoDB: docker run -d -p 27017:27017 mongo:4.5")
    print("2. Use Docker Compose: docker-compose up -d")
    print("3. Install MongoDB locally from: https://www.mongodb.com/try/download/community")
    print("\n💡 For development, use Docker for quick setup!")
    exit(1)

# ----------------------
# Logging setup
# ----------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)

# ----------------------
# Authentication Decorators & Utility Functions
# ----------------------
from functools import wraps

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            # Store the original URL to redirect back after login
            next_page = request.url if request.endpoint != 'login' else None
            if next_page:
                return redirect(url_for('login', next=next_page))
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------
# Utility Functions
# ----------------------
def ensure_directories():
    """Ensure upload and decrypted directories exist"""
    directories = [app.config['UPLOAD_FOLDER'], app.config['DECRYPTED_FOLDER']]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def is_safe_filename(filename):
    """Comprehensive filename security check"""
    if not filename or len(filename) > MAX_FILENAME_LENGTH:
        return False
    
    # Check for path traversal and dangerous characters
    dangerous_patterns = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(pattern in filename for pattern in dangerous_patterns):
        return False
    
    return True

def allowed_file(filename):
    """Check if uploaded file has allowed extension and safe filename"""
    if not filename or '.' not in filename:
        return False
    
    # Security check
    if not is_safe_filename(filename):
        return False
    
    # Extension check
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def hash_password(password):
    """Hash password using bcrypt with proper validation"""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    
    try:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Password hashing failed: {e}")
        raise ValueError("Password hashing failed")

def check_password(hashed_password, password):
    """Verify password against hash with error handling"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        app.logger.error(f"Password verification error: {e}")
        return False

# ----------------------
# Cryptographic Functions
# ----------------------
def generate_rsa_keypair():
    """Generate RSA key pair with secure parameters and error handling"""
    try:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem, public_pem
        
    except Exception as e:
        app.logger.error(f"RSA key generation failed: {e}")
        raise ValueError("Failed to generate encryption keys")

def hybrid_encrypt(data, rsa_public_key):
    """Encrypt data using hybrid encryption (RSA + AES-GCM) with validation"""
    if not data:
        raise ValueError("No data provided for encryption")
    
    try:
        # Generate AES key and nonce
        aes_key = os.urandom(AES_KEY_SIZE)
        nonce = os.urandom(GCM_NONCE_SIZE)
        
        # Encrypt data with AES-GCM
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(nonce, data, associated_data=None)
        
        # Encrypt AES key with RSA
        encrypted_aes_key = rsa_public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Combine components and encode
        encrypted_blob = encrypted_aes_key + nonce + ciphertext
        return base64.b64encode(encrypted_blob)
        
    except Exception as e:
        app.logger.error(f"Encryption failed: {e}")
        return None

def hybrid_decrypt(encrypted_blob, rsa_private_key):
    """Decrypt data using hybrid decryption (RSA + AES-GCM) with validation"""
    if not encrypted_blob:
        raise ValueError("No encrypted data provided")
    
    try:
        # Decode base64
        data = base64.b64decode(encrypted_blob)
        
        # Calculate key size for 4096-bit RSA (512 bytes)
        rsa_key_size = RSA_KEY_SIZE // 8
        
        # Extract components
        encrypted_aes_key = data[:rsa_key_size]
        nonce = data[rsa_key_size:rsa_key_size + GCM_NONCE_SIZE]
        ciphertext = data[rsa_key_size + GCM_NONCE_SIZE:]
        
        # Decrypt AES key with RSA
        aes_key = rsa_private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data with AES-GCM
        aesgcm = AESGCM(aes_key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        
    except Exception as e:
        app.logger.error(f"Decryption failed: {e}")
        return None

# Jinja2 template filter to format timestamps
@app.template_filter('format_datetime')
def format_datetime_filter(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# ----------------------
# Enhanced Security Functions
# ----------------------

def encrypt_private_key_with_password(private_key_pem, password, salt=None):
    """Encrypt private key with user password using PBKDF2 + Fernet"""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    if not salt:
        salt = os.urandom(16)
    
    # Use PBKDF2 for key derivation (OWASP recommended)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=150000,  # Higher than OWASP minimum for extra security
        backend=default_backend()
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    f = Fernet(key)
    
    encrypted_key = f.encrypt(private_key_pem.encode('utf-8'))
    return encrypted_key, salt

def decrypt_private_key_with_password(encrypted_key, password, salt):
    """Decrypt private key using user password"""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=150000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
        f = Fernet(key)
        
        return f.decrypt(encrypted_key).decode('utf-8')
        
    except Exception as e:
        app.logger.error(f"Private key decryption failed: {e}")
        raise ValueError("Failed to decrypt private key - incorrect password or corrupted data")

def secure_session_storage(private_key_pem):
    """Encrypt private key for secure session storage"""
    from cryptography.fernet import Fernet
    
    try:
        # Generate session-specific encryption key
        session_key = Fernet.generate_key()
        f = Fernet(session_key)
        
        # Encrypt the private key
        encrypted_private_key = f.encrypt(private_key_pem.encode('utf-8'))
        
        # Store session key in memory (could be enhanced with Redis)
        session_key_id = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')
        
        # In a production environment, store session_key in secure backend
        # For now, we'll use a simple in-memory store with expiration
        if not hasattr(app, 'session_keys'):
            app.session_keys = {}
        
        app.session_keys[session_key_id] = {
            'key': session_key,
            'expires': time.time() + 3600  # 1 hour expiration
        }
        
        return {
            'encrypted_private_key': base64.b64encode(encrypted_private_key).decode('utf-8'),
            'key_id': session_key_id
        }
        
    except Exception as e:
        app.logger.error(f"Session storage encryption failed: {e}")
        raise ValueError("Failed to secure session data")

def decrypt_session_storage(encrypted_private_key_b64, session_key_id):
    """Decrypt private key from secure session storage"""
    from cryptography.fernet import Fernet
    
    try:
        # Clean up expired session keys
        if hasattr(app, 'session_keys'):
            current_time = time.time()
            expired_keys = [k for k, v in app.session_keys.items() if v['expires'] < current_time]
            for k in expired_keys:
                del app.session_keys[k]
        
        # Retrieve session key
        if not hasattr(app, 'session_keys') or session_key_id not in app.session_keys:
            raise ValueError("Session key not found or expired")
        
        session_data = app.session_keys[session_key_id]
        if session_data['expires'] < time.time():
            del app.session_keys[session_key_id]
            raise ValueError("Session key expired")
        
        # Decrypt private key
        session_key = session_data['key']
        f = Fernet(session_key)
        
        encrypted_private_key = base64.b64decode(encrypted_private_key_b64.encode('utf-8'))
        return f.decrypt(encrypted_private_key).decode('utf-8')
        
    except Exception as e:
        app.logger.error(f"Session storage decryption failed: {e}")
        raise ValueError("Failed to decrypt session data")

def validate_file_input(filename, file_data):
    """Enhanced file input validation"""
    # Note: python-magic library should be installed: pip install python-magic
    
    # Validate filename
    if not filename or len(filename) > MAX_FILENAME_LENGTH:
        raise ValueError(f"Filename must be between 1 and {MAX_FILENAME_LENGTH} characters")
    
    # Check for directory traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename - no path components allowed")
    
    # Validate file extension
    file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if file_ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '.{file_ext}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Validate file size
    if len(file_data) > app.config['MAX_CONTENT_LENGTH']:
        raise ValueError(f"File too large. Maximum size: {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB")
    
    # Validate MIME type (disabled on Windows due to libmagic dependency)
    # try:
    #     import magic
    #     mime_type = magic.from_buffer(file_data, mime=True)
    #     allowed_mimes = {
    #         'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 
    #         'audio/flac', 'audio/ogg', 'audio/mp4', 'audio/m4a'
    #     }
    #     if mime_type not in allowed_mimes:
    #         app.logger.warning(f"MIME type mismatch: {mime_type} for file {filename}")
    #         # Don't reject, just log warning as MIME detection can be inconsistent
    # except ImportError:
    #     app.logger.info("python-magic not installed - skipping MIME validation")
    # except Exception as e:
    #     app.logger.warning(f"MIME type validation failed for {filename}: {e}")
    app.logger.info("MIME validation skipped - using extension-based validation only")
    
    return True

def validate_flask_file(file, max_size_mb=50):
    """
    Enhanced file input validation for Flask file uploads
    
    Args:
        file: Flask file upload object
        max_size_mb: Maximum file size in MB
    
    Returns:
        bool: True if file passes validation
    """
    if not file or not file.filename:
        return False
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        app.logger.warning(f"File size validation failed: {file_size} bytes exceeds {max_size_bytes} bytes")
        return False
    
    # Basic filename validation
    filename = secure_filename(file.filename)
    if not filename or len(filename) > 255:
        return False
    
    # Check for allowed extensions
    allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.enc'}
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in allowed_extensions:
        app.logger.warning(f"File extension validation failed: {file_extension} not in allowed extensions")
        return False
    
    # Basic content validation - check file starts with valid bytes for common audio formats
    file_header = file.read(16)
    file.seek(0)  # Reset file pointer
    
    # For encrypted files, allow any content
    if file_extension == '.enc':
        return True
    
    # Check for common audio file signatures
    audio_signatures = [
        b'ID3',  # MP3 with ID3 tags
        b'\xff\xfb',  # MP3 (MPEG-1 Layer 3)
        b'\xff\xf3',  # MP3 (MPEG-1 Layer 3)
        b'\xff\xf2',  # MP3 (MPEG-1 Layer 3)
        b'RIFF',  # WAV files
        b'fLaC',  # FLAC files
        b'OggS',  # OGG files
        b'\x00\x00\x00\x20ftypM4A',  # M4A files
    ]
    
    # Check if file starts with any valid audio signature
    for signature in audio_signatures:
        if file_header.startswith(signature):
            return True
        if len(signature) <= len(file_header) and file_header[:len(signature)] == signature:
            return True
    
    # For WAV files, check for 'WAVE' at offset 8
    if len(file_header) >= 12 and file_header[8:12] == b'WAVE':
        return True
    
    app.logger.warning(f"File signature validation failed for {filename}")
    return False

def secure_filename_enhanced(filename):
    """Enhanced secure filename generation"""
    # Remove potentially dangerous characters
    import re
    
    # Keep only alphanumeric, dots, hyphens, underscores
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Ensure it doesn't start with a dot
    if safe_filename.startswith('.'):
        safe_filename = 'file_' + safe_filename
    
    # Limit length
    if len(safe_filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(safe_filename)
        safe_filename = name[:MAX_FILENAME_LENGTH - len(ext) - 1] + ext
    
    return safe_filename

def get_user_private_key():
    """Securely retrieve user's private key from session"""
    try:
        # Check for new secure format
        if 'encrypted_private_key' in session and 'session_key_id' in session:
            private_key_pem = decrypt_session_storage(
                session['encrypted_private_key'],
                session['session_key_id']
            )
            
        # Fallback to legacy format (for backward compatibility)
        elif 'rsa_private_pem' in session:
            private_key_pem = session['rsa_private_pem']
            app.logger.warning(f"Using legacy key storage for user: {session.get('username')}")
            
        else:
            raise ValueError("No private key found in session")
        
        # Load the private key
        return serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'), 
            password=None
        )
        
    except Exception as e:
        app.logger.error(f"Failed to retrieve private key for user '{session.get('username')}': {e}")
        raise ValueError("Authentication error. Please log in again.")

def cleanup_session_keys(session_key_id=None):
    """Cleanup session keys from memory"""
    try:
        if not hasattr(app, 'session_keys'):
            return
        
        if session_key_id:
            # Clean specific key
            if session_key_id in app.session_keys:
                del app.session_keys[session_key_id]
        else:
            # Clean expired keys
            current_time = time.time()
            expired_keys = [k for k, v in app.session_keys.items() if v['expires'] < current_time]
            for k in expired_keys:
                del app.session_keys[k]
                
    except Exception as e:
        app.logger.error(f"Session cleanup error: {e}")

# ----------------------
# Routes
# ----------------------

# Security headers middleware
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com"
    return response

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    app.logger.error(f"CSRF Error: {e.description} from IP: {request.remote_addr}")
    return render_template('csrf_error.html', reason=e.description), 400

@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f"404 error: {request.url} from IP: {request.remote_addr}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 error: {error} from IP: {request.remote_addr}")
    return render_template('500.html'), 500

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('options'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")  # More restrictive rate limiting for security
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        
        # Check if username already exists
        if users_collection.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.')
            app.logger.warning(f"Registration failed: Username '{username}' already exists.")
            return render_template('register.html', form=form)
        
        try:
            # Hash password with validation
            hashed_password = hash_password(password)
            
            # Generate RSA key pair
            private_pem, public_pem = generate_rsa_keypair()
            
            # Encrypt private key with user password for secure storage
            encrypted_private_key, salt = encrypt_private_key_with_password(
                private_pem.decode('utf-8'), password
            )
            
            # Create user document with encrypted private key
            user_doc = {
                'username': username,
                'password': hashed_password,
                'encrypted_private_key': base64.b64encode(encrypted_private_key).decode('utf-8'),
                'private_key_salt': base64.b64encode(salt).decode('utf-8'),
                'public_key_pem': public_pem.decode('utf-8'),
                'created_at': time.time(),
                'last_login': None,
                'security_version': '2.0'  # Track security implementation version
            }
            
            # Insert user into database
            result = users_collection.insert_one(user_doc)
            if result.inserted_id:
                app.logger.info(f"New user registered with enhanced security: '{username}'")
                flash('Registration successful! Your account is secured with advanced encryption.')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.')
                app.logger.error(f"Failed to insert user '{username}' into database")
                
        except ValueError as e:
            flash(f'Registration failed: {str(e)}')
            app.logger.warning(f"Registration failed for '{username}': {e}")
        except Exception as e:
            flash('Registration failed due to a technical error. Please try again.')
            app.logger.error(f"Registration error for '{username}': {e}")
            
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # More restrictive rate limiting for security
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        
        # Find user in database
        user = users_collection.find_one({'username': username})
        
        if user and check_password(user['password'], password):
            # Update last login time
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': time.time()}}
            )
            
            try:
                # Handle both old and new security formats
                if 'encrypted_private_key' in user and 'private_key_salt' in user:
                    # New secure format - decrypt private key with password
                    encrypted_private_key = base64.b64decode(user['encrypted_private_key'].encode('utf-8'))
                    salt = base64.b64decode(user['private_key_salt'].encode('utf-8'))
                    
                    private_key_pem = decrypt_private_key_with_password(
                        encrypted_private_key, password, salt
                    )
                    
                    app.logger.info(f"Login with enhanced security for user: '{username}'")
                    
                elif 'private_key_pem' in user:
                    # Legacy format - migrate to new format during login
                    private_key_pem = user['private_key_pem']
                    
                    # Migrate to new format
                    encrypted_private_key, salt = encrypt_private_key_with_password(private_key_pem, password)
                    
                    users_collection.update_one(
                        {'_id': user['_id']},
                        {
                            '$set': {
                                'encrypted_private_key': base64.b64encode(encrypted_private_key).decode('utf-8'),
                                'private_key_salt': base64.b64encode(salt).decode('utf-8'),
                                'security_version': '2.0'
                            },
                            '$unset': {'private_key_pem': 1}  # Remove old plaintext key
                        }
                    )
                    
                    app.logger.info(f"Migrated user '{username}' to enhanced security format")
                    
                else:
                    raise ValueError("User account corrupted - no private key found")
                
                # Use secure session storage for private key
                session_data = secure_session_storage(private_key_pem)
                
                # Set session variables
                session['username'] = username
                session['user_id'] = str(user['_id'])
                session['encrypted_private_key'] = session_data['encrypted_private_key']
                session['session_key_id'] = session_data['key_id']
                session['rsa_public_pem'] = user['public_key_pem']
                session['user'] = username  # Add this for template compatibility
                session.permanent = True  # Make session permanent for security
                
                app.logger.info(f"Successful secure login for user: '{username}'")
                flash('Login successful!')
                
                # Check for next parameter or redirect to options
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('options'))
                
            except Exception as e:
                app.logger.error(f"Login security error for '{username}': {e}")
                flash('Login failed due to security error. Please try again.')
                
        else:
            flash('Invalid username or password.')
            app.logger.warning(f"Failed login attempt for username: '{username}' from IP: {request.remote_addr}")
            
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    username = session.get('username')
    session_key_id = session.get('session_key_id')
    
    # Cleanup session keys from memory
    if session_key_id:
        cleanup_session_keys(session_key_id)
    
    # Clear all session data
    session.clear()
    
    if username:
        app.logger.info(f"User '{username}' logged out securely.")
    
    flash('You have been logged out successfully.')
    return redirect(url_for('login'))

@app.route('/options')
@login_required
def options():
    return render_template('options.html', username=session['username'])

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/audio_encryption', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def audio_encryption():
    """Handle audio file encryption with improved error handling and validation"""
    if request.method == 'POST':
        return handle_file_encryption()
    
    return render_template('audio_encryption.html')

def handle_file_encryption():
    """Process file encryption with comprehensive validation"""
    # Validate file upload
    if 'audio_files' not in request.files:
        return render_template('audio_encryption.html', 
                             error_message="No files were uploaded.")
        
    files = request.files.getlist('audio_files')
    if not files or all(f.filename == '' for f in files):
        return render_template('audio_encryption.html', 
                             error_message="No files selected.")
    
    # Apply enhanced file input validation
    for file in files:
        if not validate_flask_file(file):
            return render_template('audio_encryption.html', 
                                 error_message="Invalid file detected. Only audio files are allowed.")
    
    # Load user's RSA public key
    try:
        rsa_public_pem = session.get('rsa_public_pem')
        if not rsa_public_pem:
            return render_template('audio_encryption.html', 
                                 error_message="Authentication error. Please log in again.")
            
        rsa_public_key = serialization.load_pem_public_key(rsa_public_pem.encode('utf-8'))
    except Exception as e:
        app.logger.error(f"Failed to load public key for user '{session.get('username', 'unknown')}': {e}")
        return render_template('audio_encryption.html', 
                             error_message="Authentication error. Please log in again.")

    # Process files
    encrypted_files = []
    successful_encryptions = 0
    
    for file in files:
        result = process_single_file_for_download(file, rsa_public_key)
        if result:
            encrypted_files.append(result)
            successful_encryptions += 1

    # Provide user feedback
    if successful_encryptions > 0:
        success_message = f"Successfully encrypted {successful_encryptions} file(s)!"
        return render_template('audio_encryption.html', 
                             success_message=success_message,
                             encrypted_files=encrypted_files)
    else:
        return render_template('audio_encryption.html', 
                             error_message="No files were encrypted successfully.")

def process_single_file_for_download(file, rsa_public_key):
    """Process a single file for encryption and return download info"""
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    try:
        # Secure filename and ensure uniqueness
        original_filename = file.filename
        filename = secure_filename(original_filename)
        timestamp = str(int(time.time()))
        base_name, ext = os.path.splitext(filename)
        
        # Read and validate file data
        original_data = file.read()
        file_size = len(original_data)
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return None
        
        if file_size == 0:
            return None
        
        # Encrypt the data
        encrypted_data = hybrid_encrypt(original_data, rsa_public_key)
        if not encrypted_data:
            return None
        
        # Save encrypted file
        encrypted_filename = f"{base_name}_{timestamp}.enc"
        encrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], encrypted_filename)
        
        with open(encrypted_file_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Store metadata in database
        file_doc = {
            'user': session['username'],
            'user_id': session.get('user_id'),
            'original_filename': original_filename,
            'original_extension': ext,  # Store the original file extension
            'encrypted_filename': encrypted_filename,
            'file_size': file_size,
            'created_at': time.time(),
            'file_path': encrypted_file_path
        }
        
        result = encrypted_files_collection.insert_one(file_doc)
        if result.inserted_id:
            app.logger.info(f"User '{session['username']}' encrypted file: '{original_filename}' ({file_size} bytes)")
            return {
                'original_filename': original_filename,
                'encrypted_filename': encrypted_filename,
                'file_size': file_size
            }
        else:
            # Clean up file if database insert failed
            if os.path.exists(encrypted_file_path):
                os.remove(encrypted_file_path)
            return None
            
    except Exception as e:
        app.logger.error(f"Error processing file '{file.filename}' for user '{session['username']}': {e}")
        return None

@app.route('/my_files')
@login_required
def my_files():
    user_files = list(encrypted_files_collection.find({'user': session['username']}))
    
    return render_template('my_files.html', user_files=user_files)

@app.route('/audio_decryption', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def audio_decryption():
    """Handle audio file decryption with direct upload"""
    if request.method == 'POST':
        return handle_file_decryption()
    
    return render_template('audio_decryption.html')

def handle_file_decryption():
    """Process file decryption with comprehensive validation"""
    # Validate file upload
    if 'encrypted_files' not in request.files:
        return render_template('audio_decryption.html', 
                             error_message="No files were uploaded.")
        
    files = request.files.getlist('encrypted_files')
    if not files or all(f.filename == '' for f in files):
        return render_template('audio_decryption.html', 
                             error_message="No files selected.")
    
    # Apply enhanced file input validation
    for file in files:
        if not validate_flask_file(file, max_size_mb=100):  # Allow larger encrypted files
            return render_template('audio_decryption.html', 
                                 error_message="Invalid file detected.")
    
    # Load user's RSA private key using secure retrieval
    try:
        rsa_private_key = get_user_private_key()
        if not rsa_private_key:
            return render_template('audio_decryption.html', 
                                 error_message="Authentication error. Please log in again.")
    except Exception as e:
        app.logger.error(f"Failed to load private key for user '{session.get('username', 'unknown')}': {e}")
        return render_template('audio_decryption.html', 
                             error_message="Authentication error. Please log in again.")

    # Process files
    decrypted_files = []
    successful_decryptions = 0
    
    for file in files:
        result = process_single_file_for_decryption(file, rsa_private_key)
        if result:
            decrypted_files.append(result)
            successful_decryptions += 1

    # Provide user feedback
    if successful_decryptions > 0:
        success_message = f"Successfully decrypted {successful_decryptions} file(s)!"
        return render_template('audio_decryption.html', 
                             success_message=success_message,
                             decrypted_files=decrypted_files)
    else:
        return render_template('audio_decryption.html', 
                             error_message="No files were decrypted successfully.")

def process_single_file_for_decryption(file, rsa_private_key):
    """Process a single encrypted file for decryption and return download info"""
    if not file or not file.filename:
        return None

    try:
        # Read encrypted file data
        encrypted_data = file.read()
        if len(encrypted_data) == 0:
            return None
        
        # Decrypt the data
        decrypted_data = hybrid_decrypt(encrypted_data, rsa_private_key)
        if not decrypted_data:
            return None
        
        # Generate decrypted filename preserving original extension
        original_filename = file.filename
        if original_filename.endswith('.enc'):
            # Try to extract the original name and extension from the encrypted filename
            base_name = original_filename[:-4]  # Remove .enc extension
            
            # If the base name contains a timestamp, try to extract the original name
            # Format is usually: originalname_timestamp.enc or originalname.ext_timestamp.enc
            parts = base_name.split('_')
            if len(parts) > 1 and parts[-1].isdigit():
                # Remove timestamp to get original base name
                original_base = '_'.join(parts[:-1])
            else:
                original_base = base_name
            
            # Try to determine the original extension
            # Check if the original_base has an extension
            if '.' in original_base:
                # Extension is already included in the base name
                original_extension = os.path.splitext(original_base)[1]
                original_name_without_ext = os.path.splitext(original_base)[0]
            else:
                # No extension found, try common audio extensions or default to mp3
                # Look for common audio file patterns in the name
                name_lower = original_base.lower()
                if any(fmt in name_lower for fmt in ['wav', 'flac', 'ogg', 'm4a']):
                    # Try to guess extension from filename
                    if 'wav' in name_lower:
                        original_extension = '.wav'
                    elif 'flac' in name_lower:
                        original_extension = '.flac'
                    elif 'ogg' in name_lower:
                        original_extension = '.ogg'
                    elif 'm4a' in name_lower:
                        original_extension = '.m4a'
                    else:
                        original_extension = '.mp3'
                else:
                    # Default to mp3 for audio files
                    original_extension = '.mp3'
                original_name_without_ext = original_base
        else:
            # If not .enc file, extract extension normally
            original_name_without_ext = os.path.splitext(original_filename)[0]
            original_extension = os.path.splitext(original_filename)[1] or '.mp3'
        
        timestamp = str(int(time.time()))
        decrypted_filename = f"{original_name_without_ext}_decrypted_{timestamp}{original_extension}"
        decrypted_file_path = os.path.join(app.config['DECRYPTED_FOLDER'], decrypted_filename)
        
        # Save decrypted file
        with open(decrypted_file_path, 'wb') as f:
            f.write(decrypted_data)
        
        app.logger.info(f"User '{session['username']}' successfully decrypted file: '{original_filename}'")
        return {
            'original_filename': original_filename,
            'decrypted_filename': decrypted_filename,
            'file_size': len(decrypted_data)
        }
            
    except Exception as e:
        app.logger.error(f"Error decrypting file '{file.filename}' for user '{session['username']}': {e}")
        return None

@app.route('/audio_decryption_post', methods=['POST'])
@login_required
def audio_decryption_post():
    
    # CSRF token is checked automatically by Flask-WTF
    file_id = request.form.get('file_id')
    if not file_id:
        flash("No file selected for decryption.")
        return redirect(url_for('my_files'))

    try:
        file_doc = encrypted_files_collection.find_one({'_id': ObjectId(file_id), 'user': session['username']})
        if not file_doc:
            abort(404, description="File not found or not owned by user.")

        # Load user's RSA private key using secure retrieval
        rsa_private_key = get_user_private_key()
        if not rsa_private_key:
            flash("Authentication error. Please log in again.")
            return redirect(url_for('login'))

        encrypted_file_path = file_doc['file_path']
        if not os.path.exists(encrypted_file_path):
            flash("Encrypted file not found on the server. It may have been deleted.")
            app.logger.error(f"Decryption failed: File '{encrypted_file_path}' not found for user '{session['username']}'")
            return redirect(url_for('my_files'))
            
        encrypted_data = open(encrypted_file_path, 'rb').read()
        
        decrypted_data = hybrid_decrypt(encrypted_data, rsa_private_key)
        if decrypted_data is not None:
            # Use the original extension from the database, fallback to the original filename extension
            original_extension = file_doc.get('original_extension', os.path.splitext(file_doc['original_filename'])[1])
            
            # Create decrypted filename with original extension
            base_name = os.path.splitext(file_doc['original_filename'])[0]
            decrypted_filename = f"{base_name}_decrypted_{int(time.time())}{original_extension}"
            decrypted_path = os.path.join(app.config['DECRYPTED_FOLDER'], decrypted_filename)
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            app.logger.info(f"User '{session['username']}' successfully decrypted file: '{file_doc['original_filename']}'")
            flash(f"File '{file_doc['original_filename']}' decrypted successfully!")
            return redirect(url_for('download_file', filename=decrypted_filename))
        else:
            flash(f"Decryption failed for file: {file_doc['original_filename']}")
            app.logger.error(f"Decryption failed for user '{session['username']}' on file: '{file_doc['original_filename']}'")
            return redirect(url_for('my_files'))

    except Exception as e:
        app.logger.error(f"Decryption error for user '{session['username']}': {e}")
        flash("An error occurred during decryption.")
        return redirect(url_for('my_files'))

@app.route('/audio_decryption', methods=['GET'])
def audio_decryption_get():
    return redirect(url_for('my_files'))

@app.route('/delete_file/<file_id>', methods=['POST'])
@login_required
def delete_file(file_id):

    try:
        file_doc = encrypted_files_collection.find_one({'_id': ObjectId(file_id), 'user': session['username']})
        if not file_doc:
            flash("File not found or you do not have permission to delete it.")
            abort(404)

        # First, delete the file from the filesystem
        if os.path.exists(file_doc['file_path']):
            os.remove(file_doc['file_path'])
            app.logger.info(f"File '{file_doc['original_filename']}' deleted from filesystem by user '{session['username']}'.")
        else:
            app.logger.warning(f"Attempted to delete non-existent file '{file_doc['file_path']}' for user '{session['username']}'.")
        
        # Then, delete the record from the database
        encrypted_files_collection.delete_one({'_id': ObjectId(file_id)})
        
        flash(f"File '{file_doc['original_filename']}' has been successfully deleted.")
        app.logger.info(f"User '{session['username']}' deleted file metadata for: '{file_doc['original_filename']}'")

    except Exception as e:
        app.logger.error(f"Failed to delete file '{file_id}' for user '{session['username']}': {e}")
        flash("An error occurred while trying to delete the file.")
    
    return redirect(url_for('my_files'))

# ----------- Download endpoints ------------
@app.route('/download_encrypted/<path:filename>')
@login_required
def download_encrypted_file(filename):
    """Download encrypted files with proper security checks"""
    # Verify the file belongs to the current user
    file_doc = encrypted_files_collection.find_one({
        'encrypted_filename': filename,
        'user': session['username']
    })
    
    if not file_doc:
        app.logger.warning(f"Unauthorized download attempt for file '{filename}' by user '{session.get('username')}'")
        abort(404, description="File not found or access denied")
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(file_path):
        app.logger.error(f"File not found on disk: {file_path}")
        abort(404, description="File not found on server")
    
    try:
        app.logger.info(f"User '{session['username']}' downloading encrypted file: '{filename}'")
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f"Error serving file '{filename}' to user '{session['username']}': {e}")
        abort(500, description="Error downloading file")

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    """Download decrypted files with security checks"""
    file_path = os.path.join(app.config['DECRYPTED_FOLDER'], filename)
    
    if not os.path.exists(file_path):
        app.logger.warning(f"Decrypted file not found: {file_path}")
        abort(404, description="File not found")
    
    try:
        app.logger.info(f"User '{session['username']}' downloading decrypted file: '{filename}'")
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f"Error serving decrypted file '{filename}' to user '{session['username']}': {e}")
        abort(500, description="Error downloading file")

# Legacy route for backward compatibility
@app.route('/download/uploads/<path:filename>')
@login_required
def download_upload_file(filename):
    """Legacy download route - redirects to new secure endpoint"""
    return redirect(url_for('download_encrypted_file', filename=filename))

# ----------------------
# Database Migration Functions
# ----------------------
def migrate_existing_files():
    """Add original_extension field to existing files in database"""
    try:
        # Find files without original_extension field
        files_to_update = encrypted_files_collection.find({'original_extension': {'$exists': False}})
        updated_count = 0
        
        for file_doc in files_to_update:
            original_filename = file_doc.get('original_filename', '')
            if original_filename:
                # Extract extension from original filename
                _, ext = os.path.splitext(original_filename)
                if not ext:
                    ext = '.mp3'  # Default fallback
                
                # Update the document
                encrypted_files_collection.update_one(
                    {'_id': file_doc['_id']},
                    {'$set': {'original_extension': ext}}
                )
                updated_count += 1
        
        if updated_count > 0:
            app.logger.info(f"Migrated {updated_count} existing files to include original_extension field")
    except Exception as e:
        app.logger.error(f"Error during file migration: {e}")

# ----------------------
# File Cleanup Functions
# ----------------------
def cleanup_old_files():
    """Clean up files older than 1 hour"""
    import time
    current_time = time.time()
    one_hour_ago = current_time - 3600  # 1 hour in seconds
    
    # Clean up old decrypted files
    try:
        for filename in os.listdir(app.config['DECRYPTED_FOLDER']):
            file_path = os.path.join(app.config['DECRYPTED_FOLDER'], filename)
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if file_mtime < one_hour_ago:
                    try:
                        os.remove(file_path)
                        app.logger.info(f"Cleaned up old decrypted file: {filename}")
                    except OSError as e:
                        app.logger.warning(f"Could not delete old file {filename}: {e}")
    except Exception as e:
        app.logger.error(f"Error during file cleanup: {e}")

# ----------------------
# Application Initialization
# ----------------------
def init_app():
    """Initialize the application with all necessary components"""
    # Ensure required directories exist
    ensure_directories()
    
    # Run database migrations
    migrate_existing_files()
    
    # Clean up old files on startup
    cleanup_old_files()
    
    # Set up logging
    if not app.debug:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('audiocrypt.log'),
                logging.StreamHandler()
            ]
        )
    
    app.logger.info("AudioCrypt application initialized successfully")

# ----------------------
# Application Entry Point
# ----------------------
if __name__ == '__main__':
    init_app()
    
    # Development server configuration
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')
    
    app.logger.info(f"Starting AudioCrypt server on {host}:{port} (debug={'on' if debug_mode else 'off'})")
    app.run(host=host, port=port, debug=debug_mode)