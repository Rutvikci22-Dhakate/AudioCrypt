# 🎵 AudioCrypt - Military-Grade Audio File Encryption

![AudioCrypt](https://img.shields.io/badge/Security-Military%20Grade-red)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green)
![Encryption](https://img.shields.io/badge/Encryption-RSA%204096%20%2B%20AES%20256-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

**AudioCrypt** is a production-ready web application that provides military-grade encryption for audio files using hybrid cryptography. Built with Flask and featuring a modern, responsive interface, it ensures your audio files are protected with industry-standard security protocols.

## ✨ **Key Features**

### 🔐 **Advanced Cryptography**
- **RSA-4096** asymmetric encryption for key exchange
- **AES-256-GCM** authenticated encryption for data
- **PBKDF2-HMAC-SHA256** key derivation (150,000 iterations)
- **Fernet** encryption for session security
- **Zero-knowledge architecture** - server never sees private keys

### 🛡️ **Security Features**
- **Private key encryption at rest** using user passwords
- **Session-specific encryption keys** with automatic cleanup
- **Rate limiting** protection against brute force attacks
- **CSRF protection** on all forms
- **Input validation** with file signature verification
- **Automatic legacy account migration**

### 💻 **User Experience**
- **Modern, responsive UI** with TailwindCSS
- **Drag & drop file uploads** with progress tracking
- **Real-time encryption/decryption** feedback
- **File management dashboard** with download links
- **Mobile-friendly interface**

### 🚀 **Production Ready**
- **Docker containerization** for easy deployment
- **MongoDB integration** for scalable storage
- **Comprehensive logging** and error handling
- **Environment-based configuration**
- **Health checks** and monitoring endpoints

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │───▶│   Flask App     │───▶│    MongoDB      │
│                 │    │                 │    │                 │
│ • File Upload   │    │ • RSA Key Gen   │    │ • User Data     │
│ • Encryption UI │    │ • AES Encryption│    │ • Encrypted     │
│ • Progress      │    │ • Session Mgmt  │    │   Private Keys  │
│ • Download      │    │ • Rate Limiting │    │ • File Metadata │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Encryption Workflow**
1. **Key Generation**: RSA-4096 keypair generated per user
2. **File Upload**: Audio file validated and processed
3. **Hybrid Encryption**: AES-256 encrypts data, RSA encrypts AES key
4. **Secure Storage**: Encrypted file saved, metadata in database
5. **Download**: Encrypted file available for secure download

## 🚦 **Quick Start**

### **Prerequisites**
- Python 3.8 or higher
- MongoDB instance
- Git

### **Installation**

1. **Clone the repository**
```bash
git clone https://github.com/Rutvikci22-Dhakate/AudioCrypt.git
cd AudioCrypt
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your MongoDB URI and secret key
```

4. **Run with Docker (Recommended)**
```bash
docker-compose up -d
```

5. **Or run locally**
```bash
python app.py
```

6. **Access the application**
```
http://localhost:5000
```

## 🔧 **Configuration**

### **Environment Variables**

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode | `development` |
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `UPLOAD_FOLDER` | File upload directory | `uploads` |
| `MAX_CONTENT_LENGTH` | Max file size (bytes) | `16777216` (16MB) |

### **Security Configuration**
- **RSA Key Size**: 4096 bits
- **AES Key Size**: 256 bits (32 bytes)
- **PBKDF2 Iterations**: 150,000
- **Session Timeout**: 1 hour
- **Rate Limits**: 3-10 requests/minute depending on endpoint

## 🎯 **Supported File Formats**

| Format | Extension | Max Size |
|--------|-----------|----------|
| MP3 | `.mp3` | 16 MB |
| WAV | `.wav` | 16 MB |
| FLAC | `.flac` | 16 MB |
| OGG | `.ogg` | 16 MB |
| M4A | `.m4a` | 16 MB |

## 🐳 **Docker Deployment**

### **Using Docker Compose**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### **Manual Docker Build**
```bash
# Build image
docker build -t audiocrypt .

# Run container
docker run -d -p 5000:5000 --name audiocrypt-app audiocrypt
```

## 🔐 **Security Details**

### **Cryptographic Specifications**
- **Asymmetric**: RSA-4096 with OAEP padding (SHA-256, MGF1)
- **Symmetric**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: PBKDF2-HMAC-SHA256 (150k iterations)
- **Session Security**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Password Hashing**: bcrypt (12 rounds)

### **Security Layers**
1. **Transport**: HTTPS/TLS encryption
2. **Authentication**: bcrypt password hashing
3. **Session**: Encrypted session storage
4. **Data**: Hybrid RSA+AES encryption
5. **Storage**: Private keys encrypted at rest

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### **Development Setup**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest

# Code formatting
black app.py
flake8 app.py
```

## 📝 **API Documentation**

### **Key Endpoints**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/register` | POST | User registration |
| `/login` | POST | User authentication |
| `/audio_encryption` | POST | File encryption |
| `/audio_decryption` | POST | File decryption |
| `/my_files` | GET | File management |

### **Response Format**
```json
{
  "status": "success",
  "message": "File encrypted successfully",
  "data": {
    "filename": "encrypted_file.enc",
    "size": 1024000,
    "download_url": "/download/encrypted_file.enc"
  }
}
```

## 🚨 **Security Considerations**

### **Production Deployment**
- Use HTTPS in production
- Configure proper MongoDB authentication
- Set strong environment variables
- Enable request logging
- Implement backup strategies
- Regular security updates

### **Known Limitations**
- File size limited to 16MB per upload
- Session timeout requires re-authentication
- MongoDB dependency for persistence
- No multi-user file sharing

## 📈 **Roadmap**

- [ ] **Multi-user file sharing** with permission controls
- [ ] **Batch file processing** for multiple uploads
- [ ] **API rate limiting** with Redis backend
- [ ] **File compression** before encryption
- [ ] **Mobile app** development
- [ ] **Two-factor authentication** integration

## 📞 **Support**

### **Documentation**
- [Security Guide](SECURITY_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)

### **Community**
- **Issues**: [GitHub Issues](https://github.com/Rutvikci22-Dhakate/AudioCrypt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Rutvikci22-Dhakate/AudioCrypt/discussions)

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **Flask** community for excellent web framework
- **Cryptography** library for robust encryption
- **TailwindCSS** for modern UI components
- **MongoDB** for scalable data storage
- **Security research** community for best practices

## ⭐ **Star History**

[![Star History Chart](https://api.star-history.com/svg?repos=Rutvikci22-Dhakate/AudioCrypt&type=Date)](https://star-history.com/#Rutvikci22-Dhakate/AudioCrypt&Date)

---

**Built with ❤️ by [Rutvik Dhakate](https://github.com/Rutvikci22-Dhakate)**

*Secure your audio files with confidence. AudioCrypt - Where security meets simplicity.*

---

## Features

- **User Authentication**: Secure login system to access encryption and decryption functionalities.
- **Audio File Encryption**: Upload an `.mp3` file, and the system encrypts it using AES and ChaCha20.
- **Audio File Decryption**: Decrypt previously encrypted files back into `.mp3` format.
- **Elliptic Curve Cryptography**: Uses ECDH for secure symmetric key generation.
- **Chaotic Key Derivation**: Adds an extra layer of security by deriving chaotic keys.
- **Secure File Handling**: Files are securely saved in specific folders, ensuring privacy.
- **Downloadable Output**: Users can download encrypted or decrypted files directly.

---

## Technologies Used

- **Backend**: Flask
- **Cryptography**: Python's `cryptography` library for AES, ChaCha20, and ECDH implementations
- **Frontend**: HTML and Flask templates
- **File Management**: `werkzeug` for secure file uploads
- **Session Management**: Flask's built-in session handling

---
