# 🚀 AudioCrypt Production Deployment Guide

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: Minimum 2GB, Recommended 4GB+
- **CPU**: 2+ cores recommended
- **Storage**: 20GB+ for application and files
- **Network**: Open ports 80, 443, 27017

### Software Dependencies
- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Git** (for deployment)
- **SSL Certificate** (Let's Encrypt recommended)

## 🔧 Pre-Deployment Setup

### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### 2. Clone and Configure
```bash
# Clone repository
git clone <your-audiocrypt-repo>
cd audiocrypt

# Create production environment file
cp .env.example .env.production
```

### 3. Environment Configuration
Edit `.env.production`:
```env
# Application Settings
FLASK_ENV=production
SECRET_KEY=your-super-secure-secret-key-minimum-32-chars
HOST=0.0.0.0
PORT=5000

# Database Configuration
MONGO_URI=mongodb://mongo:27017/audio_encryption_prod

# File Storage
UPLOAD_FOLDER=/app/uploads
DECRYPTED_FOLDER=/app/decrypted
MAX_CONTENT_LENGTH=16777216

# Email Configuration (for password reset)
MAIL_USERNAME=your-app-email@domain.com
MAIL_PASSWORD=your-app-password

# Security Settings
SESSION_TYPE=filesystem
PERMANENT_SESSION_LIFETIME=3600

# MongoDB Settings
MONGO_INITDB_DATABASE=audio_encryption_prod
```

## 🚀 Deployment Steps

### Option 1: Docker Compose (Recommended)

#### Step 1: Build and Start Services
```bash
# Production deployment
docker-compose --profile production up -d --build

# Check status
docker-compose ps
```

#### Step 2: Verify Deployment
```bash
# Check application logs
docker-compose logs audiocrypt

# Check MongoDB connection
docker-compose exec mongo mongo --eval "db.adminCommand('ping')"

# Test application
curl http://localhost
```

### Option 2: Manual Docker Deployment

#### Step 1: Build Application Image
```bash
docker build -t audiocrypt:production .
```

#### Step 2: Start MongoDB
```bash
docker run -d \
  --name audiocrypt-mongo \
  --restart unless-stopped \
  -v audiocrypt_mongo_data:/data/db \
  -p 27017:27017 \
  mongo:4.5
```

#### Step 3: Start Application
```bash
docker run -d \
  --name audiocrypt-app \
  --restart unless-stopped \
  -p 5000:5000 \
  --link audiocrypt-mongo:mongo \
  --env-file .env.production \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/decrypted:/app/decrypted \
  audiocrypt:production
```

## 🔒 SSL/HTTPS Setup

### Using Let's Encrypt with Nginx

#### Step 1: Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

#### Step 2: Obtain SSL Certificate
```bash
sudo certbot --nginx -d yourdomain.com
```

#### Step 3: Configure Nginx
Create `/etc/nginx/sites-available/audiocrypt`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    # File upload size
    client_max_body_size 20M;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Step 4: Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/audiocrypt /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 📊 Monitoring and Maintenance

### Health Checks
```bash
# Application health
curl -f http://localhost:5000/ || echo "App Down"

# Database health
docker exec audiocrypt-mongo mongo --eval "db.adminCommand('ping')"

# Disk space monitoring
df -h
```

### Log Management
```bash
# View application logs
docker-compose logs -f audiocrypt

# Rotate logs (add to crontab)
0 0 * * * docker-compose exec audiocrypt find /app/logs -name "*.log" -mtime +7 -delete
```

### Backup Strategy
```bash
#!/bin/bash
# Daily backup script
DATE=$(date +%Y%m%d)

# Backup MongoDB
docker exec audiocrypt-mongo mongodump --out /backup/mongo_$DATE

# Backup uploaded files
tar -czf /backup/uploads_$DATE.tar.gz uploads/

# Clean old backups (keep 30 days)
find /backup -name "*" -mtime +30 -delete
```

## 🔧 Performance Optimization

### 1. Resource Limits
Add to docker-compose.yml:
```yaml
services:
  audiocrypt:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
```

### 2. MongoDB Optimization
```javascript
// Connect to MongoDB and create indexes
use audio_encryption_prod

// Index on user for faster queries
db.encrypted_files.createIndex({"user": 1})
db.encrypted_files.createIndex({"user": 1, "created_at": -1})

// Index on users collection
db.users.createIndex({"username": 1}, {"unique": true})
```

### 3. File Cleanup Automation
Add to crontab:
```bash
# Clean old decrypted files every hour
0 * * * * docker exec audiocrypt-app python -c "from app import cleanup_old_files; cleanup_old_files()"
```

## 🚨 Security Hardening

### 1. Firewall Configuration
```bash
# UFW setup
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw deny 27017  # Block external MongoDB access
```

### 2. Docker Security
```bash
# Run with security options
docker run --security-opt=no-new-privileges:true \
           --read-only \
           --tmpfs /tmp \
           audiocrypt:production
```

### 3. Regular Updates
```bash
#!/bin/bash
# Update script - run weekly
docker-compose pull
docker-compose up -d --remove-orphans
docker image prune -f
```

## 📈 Scaling Considerations

### Horizontal Scaling
- Use Redis for session storage
- Implement load balancer (Nginx/HAProxy)
- Separate file storage (S3/MinIO)
- Database clustering for high availability

### Monitoring Tools
- **Prometheus + Grafana** for metrics
- **ELK Stack** for log analysis
- **Uptime monitoring** (UptimeRobot, etc.)

## 🆘 Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check logs
docker-compose logs audiocrypt

# Check configuration
docker-compose config

# Restart services
docker-compose restart
```

#### Database Connection Issues
```bash
# Check MongoDB status
docker-compose exec mongo mongo --eval "db.adminCommand('ping')"

# Check network connectivity
docker network ls
docker network inspect audiocrypt_audiocrypt-network
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Monitor disk space
df -h

# Check memory usage
free -h
```

## 📞 Support

For production support:
- Check application logs first
- Review this deployment guide
- Verify environment configuration
- Test individual components

Remember to:
- ✅ Change default passwords
- ✅ Enable SSL/HTTPS
- ✅ Set up monitoring
- ✅ Configure backups
- ✅ Test disaster recovery