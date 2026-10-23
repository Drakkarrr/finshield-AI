# FinShield AI — Deployment Guide

## Production Deployment Checklist

### 1. Prerequisites

- Docker and Docker Compose installed
- Domain name pointed to your server
- SSL/TLS certificate (Let's Encrypt recommended)
- PostgreSQL database (managed service recommended)
- Redis instance (managed service recommended)

### 2. Environment Variables

Create `.env` file with production values:

```bash
# Application
APP_ENV=production
APP_NAME=FinShield AI

# Database (use managed PostgreSQL)
DATABASE_URL=postgresql://user:password@host:5432/finshield
POSTGRES_HOST=your-db-host
POSTGRES_PORT=5432
POSTGRES_DB=finshield
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password

# Redis (use managed Redis)
REDIS_URL=redis://your-redis-host:6379/0

# Security (GENERATE SECURE RANDOM VALUES)
JWT_SECRET_KEY=<generate-64-char-random-string>
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# CORS (your domain)
CORS_ORIGINS=https://your-domain.com

# API URL (for Next.js rewrites)
API_URL=http://backend:8091
NEXT_PUBLIC_API_URL=https://your-domain.com

# Observability (optional)
OTEL_ENABLED=false
SENTRY_DSN=https://...@sentry.io/...
```

### 3. TLS/SSL Certificate

#### Option A: Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Certificates will be at:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

#### Option B: Manual Certificate

Place your certificate files in `deploy/ssl/`:
```
deploy/ssl/fullchain.pem
deploy/ssl/privkey.pem
```

### 4. Nginx Configuration

1. Copy `deploy/nginx.conf` to your nginx config directory
2. Update `server_name` to your domain
3. Update SSL certificate paths if using Let's Encrypt:
   ```nginx
   ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
   ```

### 5. Database Setup

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create initial admin user
docker-compose exec backend python -c "
from app.database import SessionLocal
from app.db_models import User
from app.auth import hash_password
db = SessionLocal()
user = User(
    email='admin@your-domain.com',
    first_name='Admin',
    last_name='User',
    hashed_password=hash_password('CHANGE_THIS_PASSWORD'),
    plan='enterprise',
    total_credits=10000,
    is_active=True
)
db.add(user)
db.commit()
db.close()
"
```

### 6. Deploy

```bash
# Build and start services
docker-compose up -d --build

# Check logs
docker-compose logs -f

# Verify health
curl https://your-domain.com/api/health/ready
```

### 7. Security Hardening

#### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp    # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 22/tcp    # SSH
sudo ufw enable
```

#### Fail2Ban (Brute Force Protection)

```bash
sudo apt-get install fail2ban

# Create /etc/fail2ban/jail.local
[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log

[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
```

### 8. Monitoring

#### Health Checks

```bash
# Liveness probe
curl https://your-domain.com/api/health/live

# Readiness probe
curl https://your-domain.com/api/health/ready

# Metrics (Prometheus)
curl https://your-domain.com/api/metrics
```

#### Log Aggregation

Configure log shipping to your log aggregation service:
- `/var/log/nginx/access.log`
- `/var/log/nginx/error.log`
- `docker-compose logs backend`
- `docker-compose logs frontend`

### 9. Backup Strategy

```bash
# Daily database backups
0 2 * * * /path/to/scripts/backup.sh

# Verify backups weekly
0 3 * * 0 /path/to/scripts/test_backup_restore.sh
```

### 10. Performance Tuning

#### Nginx Worker Processes

```nginx
# In /etc/nginx/nginx.conf
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    multi_accept on;
}
```

#### Database Connection Pooling

```python
# In backend/app/database.py
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

## Security Headers Verification

After deployment, verify security headers:

```bash
curl -I https://your-domain.com

# Expected headers:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
# Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
# Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
# Content-Security-Policy: default-src 'self'; ...
```

## TLS Verification

```bash
# Check TLS configuration
nmap --script ssl-enum-ciphers -p 443 your-domain.com

# Expected: TLS 1.2 and 1.3 only, no weak ciphers
```

## Troubleshooting

### 502 Bad Gateway

- Check backend is running: `docker-compose ps`
- Check backend logs: `docker-compose logs backend`
- Verify API_URL in frontend environment

### SSL Certificate Errors

- Verify certificate paths in nginx.conf
- Check certificate expiration: `openssl x509 -in fullchain.pem -noout -dates`
- Ensure domain matches certificate CN/SAN

### CORS Errors

- Update CORS_ORIGINS in .env to include your domain
- Restart backend after changing CORS settings

### Database Connection Errors

- Verify DATABASE_URL format
- Check database is accessible from backend container
- Verify database credentials

## Compliance Notes

### PCI DSS (Payment Card Industry)

- Stripe handles all card data (PCI SAQ A eligible)
- No card data stored in FinShield database
- TLS 1.2+ enforced for all connections

### GDPR (General Data Protection)

- DSAR endpoints available: `/api/v1/privacy/access`, `/api/v1/privacy/erasure`
- PII masking in audit logs
- Data retention policies enforced via Celery Beat jobs

### SOC 2

- Immutable audit trail with hash chain
- Role-based access control (RBAC)
- Multi-tenancy with row-level security
- Comprehensive logging and monitoring

## Support

For deployment issues:
1. Check logs: `docker-compose logs -f`
2. Verify health endpoints
3. Review environment variables
4. Check firewall and network configuration
