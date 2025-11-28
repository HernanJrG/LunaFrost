# LunaFrost Translator - Hetzner Deployment Guide

This guide covers deploying the translator app to a Hetzner VPS without Docker, using Cloudflare Tunnel for secure access.

## Table of Contents
1. [Create Hetzner Server](#1-create-hetzner-server)
2. [Initial Server Setup](#2-initial-server-setup)
3. [Install Dependencies](#3-install-dependencies)
4. [Setup PostgreSQL](#4-setup-postgresql)
5. [Setup Redis](#5-setup-redis)
6. [Deploy Application](#6-deploy-application)
7. [Setup Systemd Services](#7-setup-systemd-services)
8. [Setup Cloudflare Tunnel](#8-setup-cloudflare-tunnel)
9. [Setup Backups](#9-setup-backups)
10. [Maintenance & Updates](#10-maintenance--updates)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Create Hetzner Server

### 1.1 Create Account
1. Go to https://www.hetzner.com/cloud
2. Create an account and add payment method

### 1.2 Create Server
1. Click "Add Server"
2. **Location:** Choose closest to your users (Ashburn for US, Falkenstein for EU)
3. **Image:** Ubuntu 24.04
4. **Type:** CX21 (2 vCPU, 4GB RAM) - $5/mo, or CX31 (2 vCPU, 8GB RAM) - $10/mo
5. **Networking:** Leave defaults (public IPv4 + IPv6)
6. **SSH Keys:** Add your SSH public key (recommended) or use password
7. **Name:** `translator-prod`
8. Click "Create & Buy Now"

### 1.3 Get Server IP
After creation, note your server's IP address (e.g., `65.108.xx.xx`)

### 1.4 Connect to Server
```bash
ssh root@YOUR_SERVER_IP
```

---

## 2. Initial Server Setup

### 2.1 Update System
```bash
apt update && apt upgrade -y
```

### 2.2 Create Application User
```bash
# Create user for running the app (don't run as root)
adduser --system --group --home /var/www/translator --shell /bin/bash translator

# Allow the user to read logs
usermod -aG systemd-journal translator
```

### 2.3 Setup Firewall
```bash
# Install UFW
apt install -y ufw

# Allow SSH (important - don't lock yourself out!)
ufw allow OpenSSH

# We don't need to open 80/443 since we're using Cloudflare Tunnel
# The tunnel connects outbound, not inbound

# Enable firewall
ufw enable

# Check status
ufw status
```

### 2.4 Setup Automatic Security Updates
```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
# Select "Yes" when prompted
```

### 2.5 Set Timezone
```bash
timedatectl set-timezone UTC
# Or your preferred timezone, e.g.:
# timedatectl set-timezone America/New_York
```

---

## 3. Install Dependencies

### 3.1 Install Python 3.11+
```bash
apt install -y python3 python3-pip python3-venv python3-dev
python3 --version  # Should be 3.11 or higher
```

### 3.2 Install Build Tools
```bash
apt install -y build-essential libpq-dev git curl wget
```

---

## 4. Setup PostgreSQL

### 4.1 Install PostgreSQL
```bash
apt install -y postgresql postgresql-contrib
```

### 4.2 Create Database and User
```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL shell, run:
CREATE USER translator WITH PASSWORD 'your_secure_password_here';
CREATE DATABASE translator_db OWNER translator;
GRANT ALL PRIVILEGES ON DATABASE translator_db TO translator;

# Enable UUID extension (if needed)
\c translator_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

# Exit
\q
```

### 4.3 Configure PostgreSQL for Local Connections
```bash
# Edit pg_hba.conf to allow password auth for local connections
nano /etc/postgresql/16/main/pg_hba.conf

# Find the line:
# local   all             all                                     peer
# Change it to:
# local   all             all                                     md5

# Save and exit (Ctrl+X, Y, Enter)

# Restart PostgreSQL
systemctl restart postgresql
```

### 4.4 Test Connection
```bash
psql -U translator -d translator_db -h localhost
# Enter password when prompted
# Type \q to exit
```

---

## 5. Setup Redis

### 5.1 Install Redis
```bash
apt install -y redis-server
```

### 5.2 Configure Redis
```bash
nano /etc/redis/redis.conf

# Find and modify these lines:
supervised systemd
maxmemory 256mb
maxmemory-policy allkeys-lru

# Save and exit
```

### 5.3 Start Redis
```bash
systemctl enable redis-server
systemctl start redis-server
systemctl status redis-server
```

### 5.4 Test Redis
```bash
redis-cli ping
# Should return: PONG
```

---

## 6. Deploy Application

### 6.1 Create Directory Structure
```bash
mkdir -p /var/www/translator
mkdir -p /var/www/translator/data/images
mkdir -p /var/www/translator/data/exports
mkdir -p /var/www/translator/data/users
mkdir -p /var/www/translator/logs
chown -R translator:translator /var/www/translator
```

### 6.2 Clone or Upload Your Code

**Option A: Using Git (Recommended)**
```bash
# As root, temporarily allow translator to use git
su - translator
cd /var/www/translator

# If you have a git repo:
git clone https://github.com/yourusername/translator.git .

# Or initialize and pull:
git init
git remote add origin https://github.com/yourusername/translator.git
git pull origin main

exit  # Back to root
```

**Option B: Using SCP/SFTP**
```bash
# From your LOCAL machine, upload files:
scp -r /path/to/your/translator/* root@YOUR_SERVER_IP:/var/www/translator/

# Then fix ownership on server:
chown -R translator:translator /var/www/translator
```

### 6.3 Create Virtual Environment
```bash
su - translator
cd /var/www/translator

python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install production server
pip install gunicorn

exit  # Back to root
```

### 6.4 Create Environment File
```bash
nano /var/www/translator/.env
```

Add the following:
```env
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=generate_a_long_random_string_here_use_python_secrets

# Database
DATABASE_URL=postgresql://translator:your_secure_password_here@localhost/translator_db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Data directories
DATA_DIR=/var/www/translator/data
IMAGES_DIR=/var/www/translator/data/images
EXPORTS_DIR=/var/www/translator/data/exports
USERS_DIR=/var/www/translator/data/users

# Optional: Set if you want to restrict registration
# REGISTRATION_ENABLED=true
```

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set permissions:
```bash
chmod 600 /var/www/translator/.env
chown translator:translator /var/www/translator/.env
```

### 6.5 Initialize Database
```bash
su - translator
cd /var/www/translator
source venv/bin/activate

# Run database migrations or initialization
python3 -c "from models.database import init_db; init_db()"

# Or if you have a migration script:
# python3 migrate.py

exit
```

### 6.6 Test Application Manually
```bash
su - translator
cd /var/www/translator
source venv/bin/activate

# Test that the app starts
gunicorn --bind 127.0.0.1:5000 app:app

# Press Ctrl+C to stop after confirming it works
exit
```

---

## 7. Setup Systemd Services

### 7.1 Create Gunicorn Service
```bash
nano /etc/systemd/system/translator.service
```

Add:
```ini
[Unit]
Description=LunaFrost Translator Gunicorn Service
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
User=translator
Group=translator
WorkingDirectory=/var/www/translator
Environment="PATH=/var/www/translator/venv/bin"
EnvironmentFile=/var/www/translator/.env
ExecStart=/var/www/translator/venv/bin/gunicorn \
    --workers 4 \
    --worker-class gthread \
    --threads 2 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile /var/www/translator/logs/access.log \
    --error-logfile /var/www/translator/logs/error.log \
    --capture-output \
    --enable-stdio-inheritance \
    wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 7.2 Create Celery Worker Service
```bash
nano /etc/systemd/system/translator-celery.service
```

Add:
```ini
[Unit]
Description=LunaFrost Translator Celery Worker
After=network.target redis.service postgresql.service
Requires=redis.service

[Service]
User=translator
Group=translator
WorkingDirectory=/var/www/translator
Environment="PATH=/var/www/translator/venv/bin"
EnvironmentFile=/var/www/translator/.env
ExecStart=/var/www/translator/venv/bin/celery \
    -A celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --logfile=/var/www/translator/logs/celery.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7.3 Create Celery Beat Service (if using scheduled tasks)
```bash
nano /etc/systemd/system/translator-celery-beat.service
```

Add:
```ini
[Unit]
Description=LunaFrost Translator Celery Beat Scheduler
After=network.target redis.service
Requires=redis.service

[Service]
User=translator
Group=translator
WorkingDirectory=/var/www/translator
Environment="PATH=/var/www/translator/venv/bin"
EnvironmentFile=/var/www/translator/.env
ExecStart=/var/www/translator/venv/bin/celery \
    -A celery_app beat \
    --loglevel=info \
    --logfile=/var/www/translator/logs/celery-beat.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7.4 Enable and Start Services
```bash
# Reload systemd
systemctl daemon-reload

# Enable services to start on boot
systemctl enable translator
systemctl enable translator-celery
systemctl enable translator-celery-beat

# Start services
systemctl start translator
systemctl start translator-celery
systemctl start translator-celery-beat

# Check status
systemctl status translator
systemctl status translator-celery
systemctl status translator-celery-beat
```

### 7.5 View Logs
```bash
# Application logs
tail -f /var/www/translator/logs/error.log
tail -f /var/www/translator/logs/access.log

# Celery logs
tail -f /var/www/translator/logs/celery.log

# System logs
journalctl -u translator -f
journalctl -u translator-celery -f
```

---

## 8. Setup Cloudflare Tunnel

### 8.1 Install Cloudflared
```bash
# Download and install
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 8.2 Authenticate with Cloudflare
```bash
cloudflared tunnel login
# This opens a browser URL - copy it and open in your browser
# Select your domain and authorize
```

### 8.3 Create Tunnel
```bash
cloudflared tunnel create translator

# This creates a tunnel and outputs a tunnel ID like:
# Created tunnel translator with id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Note this ID!
```

### 8.4 Create Tunnel Configuration
```bash
mkdir -p /etc/cloudflared
nano /etc/cloudflared/config.yml
```

Add:
```yaml
tunnel: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # Your tunnel ID
credentials-file: /root/.cloudflared/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.json

ingress:
  - hostname: translator.yourdomain.com
    service: http://127.0.0.1:5000
  - service: http_status:404
```

### 8.5 Route DNS
```bash
cloudflared tunnel route dns translator translator.yourdomain.com
```

### 8.6 Install Tunnel as Service
```bash
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared
```

### 8.7 Verify Tunnel
```bash
# Check tunnel is running
cloudflared tunnel info translator

# Visit your domain in browser
# https://translator.yourdomain.com
```

---

## 9. Setup Backups

### 9.1 Create Backup Script
```bash
nano /var/www/translator/backup.sh
```

Add:
```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/var/www/translator/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
PGPASSWORD="your_secure_password_here" pg_dump -U translator -h localhost translator_db > "$BACKUP_DIR/db_$DATE.sql"
gzip "$BACKUP_DIR/db_$DATE.sql"

# Backup user data (images, exports, user files)
echo "Backing up user data..."
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C /var/www/translator data/

# Backup environment and config
echo "Backing up configuration..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /var/www/translator/.env /etc/cloudflared/config.yml

# Delete old backups
echo "Cleaning old backups..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

Set permissions:
```bash
chmod +x /var/www/translator/backup.sh
chown translator:translator /var/www/translator/backup.sh
mkdir -p /var/www/translator/backups
chown translator:translator /var/www/translator/backups
```

### 9.2 Schedule Daily Backups
```bash
crontab -e

# Add this line to run backup at 3 AM daily:
0 3 * * * /var/www/translator/backup.sh >> /var/www/translator/logs/backup.log 2>&1
```

### 9.3 (Optional) Offsite Backups to Hetzner Storage Box
```bash
# Order a Storage Box from Hetzner (~$3/mo for 100GB)
# Then add to backup script:

# Upload to Hetzner Storage Box
echo "Uploading to offsite storage..."
rsync -avz $BACKUP_DIR/ uXXXXXX@uXXXXXX.your-storagebox.de:backups/translator/
```

---

## 10. Maintenance & Updates

### 10.1 Create Deploy Script
```bash
nano /var/www/translator/deploy.sh
```

Add:
```bash
#!/bin/bash
set -e

echo "=== Starting deployment ==="
cd /var/www/translator

# Pull latest code (if using git)
echo "Pulling latest code..."
sudo -u translator git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
sudo -u translator venv/bin/pip install -r requirements.txt

# Run database migrations (if any)
# echo "Running migrations..."
# sudo -u translator venv/bin/python migrate.py

# Restart services (graceful reload)
echo "Restarting services..."
systemctl reload translator || systemctl restart translator
systemctl restart translator-celery
systemctl restart translator-celery-beat

echo "=== Deployment complete ==="
systemctl status translator --no-pager
```

Set permissions:
```bash
chmod +x /var/www/translator/deploy.sh
```

### 10.2 Quick Commands Reference
```bash
# View app status
systemctl status translator

# Restart app (graceful - no downtime)
systemctl reload translator

# Restart app (full restart)
systemctl restart translator

# View live logs
journalctl -u translator -f

# View app error logs
tail -f /var/www/translator/logs/error.log

# Restart all services
systemctl restart translator translator-celery translator-celery-beat

# Check disk usage
df -h

# Check memory usage
free -h

# Check running processes
htop
```

### 10.3 Update System Packages
```bash
# Run monthly
apt update && apt upgrade -y
systemctl restart translator translator-celery translator-celery-beat
```

---

## 11. Troubleshooting

### 11.1 App Won't Start
```bash
# Check logs
journalctl -u translator -n 50 --no-pager
cat /var/www/translator/logs/error.log

# Test manually
su - translator
cd /var/www/translator
source venv/bin/activate
python app.py  # See actual error
```

### 11.2 Database Connection Issues
```bash
# Check PostgreSQL is running
systemctl status postgresql

# Test connection
psql -U translator -d translator_db -h localhost

# Check pg_hba.conf allows connections
cat /etc/postgresql/16/main/pg_hba.conf | grep -v "^#" | grep -v "^$"
```

### 11.3 Redis Connection Issues
```bash
# Check Redis is running
systemctl status redis-server

# Test connection
redis-cli ping

# Check Redis logs
journalctl -u redis-server -n 50
```

### 11.4 Cloudflare Tunnel Issues
```bash
# Check tunnel status
systemctl status cloudflared

# View tunnel logs
journalctl -u cloudflared -f

# Test tunnel manually
cloudflared tunnel run translator
```

### 11.5 Permission Issues
```bash
# Fix ownership
chown -R translator:translator /var/www/translator

# Fix data directory permissions
chmod -R 755 /var/www/translator/data
```

### 11.6 Out of Memory
```bash
# Check memory
free -h

# Add swap if needed (2GB)
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 11.7 High CPU/Load
```bash
# Check what's using CPU
htop

# Check Celery workers
systemctl status translator-celery

# Reduce Gunicorn workers in /etc/systemd/system/translator.service
# Change --workers 4 to --workers 2
```

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Deploy updates | `/var/www/translator/deploy.sh` |
| Restart app | `systemctl restart translator` |
| View logs | `journalctl -u translator -f` |
| Check status | `systemctl status translator` |
| Run backup | `/var/www/translator/backup.sh` |
| SSH to server | `ssh root@YOUR_SERVER_IP` |
| Check disk | `df -h` |
| Check memory | `free -h` |

---

## Security Checklist

- [x] Firewall enabled (UFW)
- [x] No unnecessary ports open
- [x] SSH key authentication (disable password in /etc/ssh/sshd_config)
- [x] Automatic security updates enabled
- [x] App runs as non-root user
- [x] Database password is strong
- [x] .env file has restricted permissions (600)
- [x] Cloudflare Tunnel hides server IP
- [x] Regular backups configured

---

## Cost Summary

| Service | Monthly Cost |
|---------|-------------|
| Hetzner CX21 (2 vCPU, 4GB) | ~$5 |
| Hetzner CX31 (2 vCPU, 8GB) | ~$10 |
| Cloudflare Tunnel | Free |
| Domain (if needed) | ~$10/year |
| Storage Box 100GB (optional) | ~$3 |
| **Total** | **$5-13/month** |

---

## Next Steps After Deployment

1. Create your admin user account
2. Test all features (import, translate, export)
3. Set up monitoring (optional): Uptime Kuma, Netdata
4. Configure your domain's email (for password reset if needed)
5. Share with beta testers!
