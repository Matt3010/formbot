# FormBot Production Deployment Guide

This guide covers deploying FormBot in production environments with public accessibility, SSL/TLS encryption, and proper security configuration.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Environment Configuration](#environment-configuration)
4. [Reverse Proxy Setup (Nginx)](#reverse-proxy-setup-nginx)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Security Checklist](#security-checklist)
7. [Firewall Configuration](#firewall-configuration)
8. [Deployment Steps](#deployment-steps)
9. [Monitoring and Maintenance](#monitoring-and-maintenance)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

- **OS**: Ubuntu 22.04 LTS or newer (recommended)
- **CPU**: 4+ cores (for concurrent browser instances)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 50GB+ SSD
- **Ports**: 80, 443 (public), 6080 (VNC), 9002 (MinIO) - see [Firewall Configuration](#firewall-configuration)

### Software Requirements

- Docker 24.0+ and Docker Compose 2.0+
- Nginx 1.18+ (for reverse proxy)
- Certbot (for Let's Encrypt SSL certificates)
- Git

### Domain Setup

You'll need domain names or subdomains for:
- **Main application**: `app.yourdomain.com`
- **VNC access**: `vnc.yourdomain.com` (can be same as main)
- **MinIO**: `minio.yourdomain.com` (for screenshot access)

Alternatively, use a single domain with path-based routing or use your server's public IP address.

---

## Architecture Overview

FormBot consists of multiple services that need to be accessible:

### Internal Services (Docker network only)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Soketi WebSocket (port 6001)

### Public-Facing Services (require reverse proxy or port exposure)
- **Frontend**: Angular SPA on port 4200
- **Backend API**: Laravel on port 8000
- **VNC/noVNC**: Websockify on port 6080
- **MinIO**: S3-compatible storage on port 9002

### Traffic Flow

```
Internet → Nginx (80/443)
             ├─→ Frontend (4200)
             ├─→ Backend API (8000)
             ├─→ VNC Websocket (6080)
             └─→ MinIO (9002)
```

---

## Environment Configuration

### 1. Clone and Setup

```bash
cd /opt
git clone https://github.com/yourorg/formbot.git
cd formbot
```

### 2. Create Production .env File

Copy the example and customize:

```bash
cp .env.example .env
nano .env
```

### 3. Critical Environment Variables

Update these variables for production:

#### Application Settings
```bash
APP_DEBUG=false
APP_URL=https://app.yourdomain.com
```

#### Database
```bash
DB_PASSWORD=STRONG_RANDOM_PASSWORD_HERE
```

#### Encryption Keys
```bash
# Generate with: php artisan key:generate
APP_KEY=base64:GENERATE_WITH_php_artisan_key_generate

# Generate with: openssl rand -base64 32
ENCRYPTION_KEY=BASE64_ENCODED_32_BYTE_KEY
```

#### MinIO Public URL
```bash
# Internal endpoint (Docker network)
MINIO_ENDPOINT=http://minio:9000

# Public URL for presigned screenshot URLs (browser-accessible)
MINIO_PUBLIC_URL=https://minio.yourdomain.com
# OR if using IP: MINIO_PUBLIC_URL=http://YOUR_SERVER_IP:9002
```

#### VNC Public URL
```bash
# Public URL configuration for VNC session URLs (browser-accessible)
NOVNC_PUBLIC_HOST=vnc.yourdomain.com
NOVNC_PUBLIC_PORT=  # Empty for default https port 443
NOVNC_PUBLIC_SCHEME=https

# OR if using IP:
# NOVNC_PUBLIC_HOST=YOUR_SERVER_IP
# NOVNC_PUBLIC_PORT=6080
# NOVNC_PUBLIC_SCHEME=http
```

#### Pusher/Soketi WebSocket
```bash
# Use strong random values
PUSHER_APP_ID=formbot
PUSHER_APP_KEY=RANDOM_STRING_HERE
PUSHER_APP_SECRET=STRONG_RANDOM_SECRET_HERE
```

#### MinIO Credentials
```bash
MINIO_ROOT_USER=formbot_admin
MINIO_ROOT_PASSWORD=STRONG_RANDOM_PASSWORD_HERE
```

---

## Reverse Proxy Setup (Nginx)

### 1. Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

### 2. Create Nginx Configuration

Create `/etc/nginx/sites-available/formbot`:

```nginx
# Upstream definitions
upstream formbot_frontend {
    server localhost:4200;
}

upstream formbot_backend {
    server localhost:8000;
}

upstream formbot_vnc {
    server localhost:6080;
}

upstream formbot_minio {
    server localhost:9002;
}

# Main application (Frontend + API)
server {
    listen 80;
    server_name app.yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://formbot_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://formbot_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
    }

    # WebSocket (Soketi)
    location /socket.io {
        proxy_pass http://localhost:6001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    client_max_body_size 10M;
}

# VNC Access
server {
    listen 80;
    server_name vnc.yourdomain.com;

    location / {
        proxy_pass http://formbot_vnc;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}

# MinIO (Screenshot Storage)
server {
    listen 80;
    server_name minio.yourdomain.com;

    location / {
        proxy_pass http://formbot_minio;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # MinIO-specific headers
        proxy_buffering off;
        proxy_request_buffering off;
    }

    client_max_body_size 100M;
}
```

### 3. Enable Configuration

```bash
sudo ln -s /etc/nginx/sites-available/formbot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL/TLS Configuration

### Option 1: Let's Encrypt (Recommended)

#### 1. Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx
```

#### 2. Obtain Certificates

```bash
# For each domain
sudo certbot --nginx -d app.yourdomain.com
sudo certbot --nginx -d vnc.yourdomain.com
sudo certbot --nginx -d minio.yourdomain.com
```

Certbot will automatically:
- Obtain SSL certificates
- Update Nginx configuration
- Setup auto-renewal

#### 3. Verify Auto-Renewal

```bash
sudo certbot renew --dry-run
```

### Option 2: Custom SSL Certificates

If using your own certificates, update Nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name app.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... rest of configuration
}
```

### Update Environment Variables After SSL Setup

After SSL is configured, update `.env`:

```bash
NOVNC_PUBLIC_SCHEME=https
MINIO_PUBLIC_URL=https://minio.yourdomain.com
```

Restart services:

```bash
docker compose restart scraper backend queue-worker
```

---

## Security Checklist

### Application Security

- [ ] **APP_DEBUG=false** in production
- [ ] **Strong APP_KEY** generated with `php artisan key:generate`
- [ ] **Strong ENCRYPTION_KEY** generated with `openssl rand -base64 32`
- [ ] **Strong database password** (20+ characters, random)
- [ ] **Strong MinIO credentials** (not default values)
- [ ] **Strong Pusher secrets** (random strings)
- [ ] **Laravel encryption key rotated** from development

### Network Security

- [ ] **Firewall configured** (see [Firewall Configuration](#firewall-configuration))
- [ ] **Direct database access blocked** from public internet
- [ ] **Redis access restricted** to Docker network only
- [ ] **Nginx rate limiting configured** (optional but recommended)
- [ ] **SSL/TLS enabled** for all public endpoints
- [ ] **HTTP → HTTPS redirects** configured

### Docker Security

- [ ] **Non-root users** in Docker containers (already configured)
- [ ] **Docker socket not exposed** to containers
- [ ] **Volumes have correct permissions**
- [ ] **Images from trusted sources** (official images used)

### Operational Security

- [ ] **Regular backups** configured (database, uploads, screenshots)
- [ ] **Log rotation** configured
- [ ] **Security updates** applied regularly
- [ ] **SSH key-based authentication** (disable password auth)
- [ ] **Fail2ban** installed and configured

---

## Firewall Configuration

### Using UFW (Ubuntu Firewall)

```bash
# Enable firewall
sudo ufw enable

# Allow SSH (IMPORTANT: do this first!)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (Nginx)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# If NOT using Nginx reverse proxy, allow direct access
sudo ufw allow 4200/tcp  # Frontend (only if not behind Nginx)
sudo ufw allow 8000/tcp  # Backend (only if not behind Nginx)
sudo ufw allow 6080/tcp  # VNC (only if not behind Nginx)
sudo ufw allow 9002/tcp  # MinIO (only if not behind Nginx)

# BLOCK direct access to internal services
sudo ufw deny 5432/tcp   # PostgreSQL
sudo ufw deny 6379/tcp   # Redis
sudo ufw deny 6001/tcp   # Soketi
sudo ufw deny 9000/tcp   # MinIO internal port

# Check status
sudo ufw status verbose
```

### Recommended Configuration

**With Nginx reverse proxy** (recommended):
- Open: 22, 80, 443
- All other ports handled via localhost proxy

**Without Nginx** (development/testing):
- Open: 22, 4200, 8000, 6080, 9002
- Block: 5432, 6379, 6001, 9000

---

## Deployment Steps

### 1. Initial Setup

```bash
# Navigate to project directory
cd /opt/formbot

# Generate app key
docker compose run --rm backend php artisan key:generate

# Set proper permissions
sudo chown -R $USER:$USER .
chmod +x packages/backend/artisan
```

### 2. Build and Start Services

```bash
# Build all services
docker compose build

# Start services
docker compose up -d

# Check status
docker compose ps
```

### 3. Run Database Migrations

```bash
docker compose exec backend php artisan migrate --force
```

### 4. Verify Services

```bash
# Check logs
docker compose logs -f backend
docker compose logs -f scraper
docker compose logs -f queue-worker

# Test health endpoints
curl http://localhost:8000/api/health
curl http://localhost:9001/health
```

### 5. Setup Nginx and SSL

Follow [Reverse Proxy Setup](#reverse-proxy-setup-nginx) and [SSL/TLS Configuration](#ssltls-configuration) sections.

### 6. Test Public Access

- Visit `https://app.yourdomain.com`
- Create a test task
- Verify VNC editor loads at `https://vnc.yourdomain.com`
- Execute task and verify screenshot URLs work

---

## Monitoring and Maintenance

### Logs

```bash
# View all logs
docker compose logs

# Follow specific service
docker compose logs -f backend
docker compose logs -f scraper

# View last N lines
docker compose logs --tail=100 backend
```

### Backups

#### Database Backup

```bash
# Manual backup
docker compose exec db pg_dump -U formbot formbot > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker compose exec -T db psql -U formbot formbot < backup_20260215_120000.sql
```

#### Automated Backup Script

Create `/opt/formbot/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/formbot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database
docker compose exec -T db pg_dump -U formbot formbot | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Volumes
docker run --rm -v formbot_uploads:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/uploads_$DATE.tar.gz /data
docker run --rm -v formbot_screenshots:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/screenshots_$DATE.tar.gz /data

# Keep last 7 days
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Schedule with cron:
```bash
sudo crontab -e
# Add: 0 2 * * * /opt/formbot/backup.sh >> /opt/formbot/backup.log 2>&1
```

### Updates

```bash
# Pull latest code
cd /opt/formbot
git pull

# Rebuild services
docker compose build scraper queue-worker backend

# Run migrations
docker compose exec backend php artisan migrate --force

# Restart services
docker compose up -d

# Clear caches
docker compose exec backend php artisan config:cache
docker compose exec backend php artisan route:cache
```

### Health Monitoring

Consider setting up:
- **Uptime monitoring**: UptimeRobot, Pingdom
- **Log aggregation**: ELK stack, Grafana Loki
- **Metrics**: Prometheus + Grafana
- **Alerts**: Email/Slack notifications for service failures

---

## Troubleshooting

### Issue: Screenshots Not Loading

**Symptoms**: Execution completes but screenshot URLs return 404 or connection refused

**Solutions**:

1. Verify MinIO is accessible:
   ```bash
   curl http://localhost:9002
   ```

2. Check `MINIO_PUBLIC_URL` is correct:
   ```bash
   docker compose exec backend php artisan tinker
   >>> config('minio.public_url')
   ```

3. Verify presigned URL generation:
   ```bash
   docker compose logs backend | grep "presigned"
   ```

4. Test MinIO directly:
   ```bash
   # List buckets
   docker compose exec minio mc ls local/
   ```

### Issue: VNC Session Not Loading

**Symptoms**: "Open Editor" button shows URL but VNC iframe doesn't connect

**Solutions**:

1. Verify VNC URL configuration:
   ```bash
   docker compose exec scraper python -c "from app.config import settings; print(f'{settings.novnc_public_scheme}://{settings.novnc_public_host}:{settings.novnc_public_port}')"
   ```

2. Check websockify is running:
   ```bash
   docker compose exec scraper ps aux | grep websockify
   ```

3. Test VNC port accessibility:
   ```bash
   curl -I http://localhost:6080
   ```

4. Check scraper logs:
   ```bash
   docker compose logs scraper | grep -i vnc
   ```

### Issue: SSL Certificate Errors

**Solutions**:

1. Verify certificates:
   ```bash
   sudo certbot certificates
   ```

2. Test SSL:
   ```bash
   curl -I https://app.yourdomain.com
   openssl s_client -connect app.yourdomain.com:443
   ```

3. Force renewal:
   ```bash
   sudo certbot renew --force-renewal
   sudo systemctl reload nginx
   ```

### Issue: Queue Jobs Not Processing

**Symptoms**: Tasks stuck in "pending" status

**Solutions**:

1. Check queue worker:
   ```bash
   docker compose logs queue-worker
   ```

2. Restart queue worker:
   ```bash
   docker compose restart queue-worker
   ```

3. Check Redis connection:
   ```bash
   docker compose exec backend php artisan queue:listen --once
   ```

### Issue: Database Connection Errors

**Solutions**:

1. Verify database is running:
   ```bash
   docker compose ps db
   ```

2. Check credentials:
   ```bash
   docker compose exec backend php artisan tinker
   >>> DB::connection()->getPdo();
   ```

3. Test direct connection:
   ```bash
   docker compose exec db psql -U formbot -d formbot
   ```

### Getting Help

- Check logs: `docker compose logs -f`
- Review GitHub issues: [github.com/yourorg/formbot/issues](https://github.com/yourorg/formbot/issues)
- Join community Discord/Slack (if available)

---

## Scaling Considerations

### Horizontal Scaling

- **Multiple queue workers**: Increase `replicas` in docker-compose.yml
- **Load balancing**: Use Nginx upstream with multiple backend instances
- **Database read replicas**: Configure Laravel read/write splitting

### Performance Tuning

- **Browser concurrency**: Adjust `MAX_CONCURRENT_BROWSERS` (default: 5)
- **Queue workers**: Add more workers for high task volume
- **Redis memory**: Increase Redis `maxmemory` for large queue
- **PHP-FPM**: Tune `pm.max_children` in backend container

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  scraper:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

---

## Security Hardening

### Additional Measures

1. **SSH Hardening**:
   ```bash
   # Disable password auth, use keys only
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

2. **Install Fail2ban**:
   ```bash
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   ```

3. **Nginx Rate Limiting**:
   ```nginx
   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

   location /api {
       limit_req zone=api burst=20 nodelay;
       # ... rest of config
   }
   ```

4. **Docker Security**:
   ```bash
   # Run Docker daemon in rootless mode
   # See: https://docs.docker.com/engine/security/rootless/
   ```

---

## License

FormBot is proprietary software. See LICENSE file for details.

## Support

For production deployment support, contact: support@yourdomain.com
