# Server Startup Guide - Arc Backend

This guide covers starting the Arc Backend application in both **Development** and **Production (AWS)** environments.

---

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Redis server
- Virtual environment activated

---

## Development Environment Setup

### 1. Initial Setup (First Time Only)

```bash
# Clone repository and navigate to project
cd /path/to/arc_backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Edit .env with your local configuration
nano .env  # or use your preferred editor
```

### 2. Configure Environment Variables

Edit `.env` file with your local settings:

```bash
# Development Settings
SECRET_KEY=django-insecure-hj+2+o*ywt0200s9a+ze4u#x79_j2t-s&@fzpx7-zn_cr!=)r*
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*

# Local PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=postgres
DB_USER=Arc_New
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Local Redis
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# CORS (Allow all for development)
CORS_ALLOW_ALL_ORIGINS=True


```

### 3. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# (Optional) Populate test data
python manage.py populate_sites_data
python manage.py populate_regulatory_rules
python manage.py populate_compliance_data --count=100
```

### 4. Start Development Servers

**Terminal 1: Start Redis**
```bash
redis-server
```

**Terminal 2: Start Django Development Server**
```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```
Access at: http://localhost:8000

**Terminal 3: Start Celery Worker**
```bash
source venv/bin/activate
celery -A arc_backend worker --loglevel=info --concurrency=2
```

**Terminal 4: Start Celery Beat (Scheduler)**
```bash
source venv/bin/activate
celery -A arc_backend beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Terminal 5 (Optional): Start Celery Flower (Monitoring)**
```bash
source venv/bin/activate
celery -A arc_backend flower
```
Access at: http://localhost:5555

### 5. Quick Start Script (Development)

Create `start_dev.sh`:

```bash
#!/bin/bash

# Start all services in background
redis-server --daemonize yes

# Activate virtual environment
source venv/bin/activate

# Start Django
python manage.py runserver 0.0.0.0:8000 &

# Start Celery Worker
celery -A arc_backend worker --loglevel=info --concurrency=2 --logfile=celery_worker.log &

# Start Celery Beat
celery -A arc_backend beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler --logfile=celery_beat.log &

echo "All services started!"
echo "Django: http://localhost:8000"
echo "Logs: celery_worker.log, celery_beat.log"
```

Make executable and run:
```bash
chmod +x start_dev.sh
./start_dev.sh
```

---

## Production Environment (AWS)

### 1. AWS Infrastructure Setup

**Required AWS Services:**
- **RDS PostgreSQL** - Database
- **ElastiCache Redis** - Celery broker
- **EC2 / Elastic Beanstalk / ECS** - Application hosting
- **S3** - Static files storage
- **Application Load Balancer** - Traffic distribution

### 2. Production Environment Variables

Create `.env` file on production server:

```bash
# Production Settings
SECRET_KEY=<generate-strong-secret-key-with-50+-characters>
DEBUG=False
ALLOWED_HOSTS=your-domain.com,*.elasticbeanstalk.com,*.compute.amazonaws.com

# AWS RDS PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=arc_backend_prod
DB_USER=arc_admin
DB_PASSWORD=<strong-password>
DB_HOST=arc-backend-db.xxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432

# AWS ElastiCache Redis
CELERY_BROKER_URL=redis://arc-backend-redis.xxxxx.cache.amazonaws.com:6379/0
CELERY_RESULT_BACKEND=redis://arc-backend-redis.xxxxx.cache.amazonaws.com:6379/0

# CORS (Production Frontend)
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://your-frontend.com,https://www.your-frontend.com

# CSRF (Production Domain)
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://api.your-domain.com

```

### 3. Production Deployment Process

#### Option A: AWS Elastic Beanstalk

**Step 1: Install EB CLI**
```bash
pip install awsebcli
```

**Step 2: Initialize Elastic Beanstalk**
```bash
eb init -p python-3.12 arc-backend --region us-east-1
```

**Step 3: Create `.ebextensions/django.config`**
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: arc_backend.wsgi:application
  aws:elasticbeanstalk:application:environment:
    DJANGO_SETTINGS_MODULE: arc_backend.settings
    PYTHONPATH: /var/app/current:$PYTHONPATH

container_commands:
  01_migrate:
    command: "source /var/app/venv/*/bin/activate && python manage.py migrate --noinput"
    leader_only: true
  02_collectstatic:
    command: "source /var/app/venv/*/bin/activate && python manage.py collectstatic --noinput"
    leader_only: true
```

**Step 4: Create Procfile**
```
web: gunicorn --bind :8000 --workers 3 --timeout 120 arc_backend.wsgi:application
worker: celery -A arc_backend worker --loglevel=info --concurrency=2
beat: celery -A arc_backend beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Step 5: Deploy**
```bash
# Set environment variables
eb setenv SECRET_KEY=xxx DB_HOST=xxx DB_PASSWORD=xxx ...

# Deploy application
eb create arc-backend-prod
eb deploy
```

**Step 6: Access Application**
```bash
eb open
```

#### Option B: EC2 Manual Deployment

**Step 1: SSH into EC2 Instance**
```bash
ssh -i your-key.pem ubuntu@ec2-xx-xx-xx-xx.compute.amazonaws.com
```

**Step 2: Install Dependencies**
```bash
sudo apt update
sudo apt install python3.12 python3-pip python3-venv postgresql-client redis-tools nginx -y
```

**Step 3: Clone and Setup Application**
```bash
cd /var/www
sudo git clone <repository-url> arc_backend
cd arc_backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with production settings
nano .env
```

**Step 4: Run Migrations and Collect Static**
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

**Step 5: Configure Gunicorn Service**

Create `/etc/systemd/system/arc-backend.service`:
```ini
[Unit]
Description=Arc Backend Gunicorn Service
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/arc_backend
Environment="PATH=/var/www/arc_backend/venv/bin"
ExecStart=/var/www/arc_backend/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/arc_backend/arc_backend.sock \
    --timeout 120 \
    arc_backend.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Step 6: Configure Celery Worker Service**

Create `/etc/systemd/system/arc-celery-worker.service`:
```ini
[Unit]
Description=Arc Backend Celery Worker
After=network.target

[Service]
Type=forking
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/arc_backend
Environment="PATH=/var/www/arc_backend/venv/bin"
ExecStart=/var/www/arc_backend/venv/bin/celery -A arc_backend worker \
    --loglevel=info \
    --concurrency=2 \
    --logfile=/var/log/celery/worker.log

[Install]
WantedBy=multi-user.target
```

**Step 7: Configure Celery Beat Service**

Create `/etc/systemd/system/arc-celery-beat.service`:
```ini
[Unit]
Description=Arc Backend Celery Beat
After=network.target

[Service]
Type=simple
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/arc_backend
Environment="PATH=/var/www/arc_backend/venv/bin"
ExecStart=/var/www/arc_backend/venv/bin/celery -A arc_backend beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --logfile=/var/log/celery/beat.log

[Install]
WantedBy=multi-user.target
```

**Step 8: Configure Nginx**

Create `/etc/nginx/sites-available/arc-backend`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /var/www/arc_backend/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/arc_backend/arc_backend.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/arc-backend /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Step 9: Start All Services**
```bash
# Create log directory
sudo mkdir -p /var/log/celery
sudo chown ubuntu:www-data /var/log/celery

# Enable and start services
sudo systemctl enable arc-backend arc-celery-worker arc-celery-beat
sudo systemctl start arc-backend arc-celery-worker arc-celery-beat

# Check status
sudo systemctl status arc-backend
sudo systemctl status arc-celery-worker
sudo systemctl status arc-celery-beat
```

### 4. Production Monitoring

**View Logs:**
```bash
# Django/Gunicorn logs
sudo journalctl -u arc-backend -f

# Celery Worker logs
sudo journalctl -u arc-celery-worker -f
tail -f /var/log/celery/worker.log

# Celery Beat logs
sudo journalctl -u arc-celery-beat -f
tail -f /var/log/celery/beat.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

**Restart Services:**
```bash
sudo systemctl restart arc-backend
sudo systemctl restart arc-celery-worker
sudo systemctl restart arc-celery-beat
sudo systemctl restart nginx
```

### 5. Production Health Checks

**Check Database Connection:**
```bash
python manage.py dbshell
```

**Check Redis Connection:**
```bash
redis-cli -h <elasticache-endpoint> ping
```

**Check Celery Workers:**
```bash
celery -A arc_backend inspect active
celery -A arc_backend inspect stats
```

---

## API Endpoints

After starting the server, access:

- **API Root**: `http://localhost:8000/api/`
- **Admin Panel**: `http://localhost:8000/admin/`
- **API Documentation**: `http://localhost:8000/api/schema/swagger-ui/`
- **Sites API**: `http://localhost:8000/api/sites/`
- **Communities API**: `http://localhost:8000/api/community/`
- **Map Data API**: `http://localhost:8000/api/community/map-data/`
- **Regulatory Rules API**: `http://localhost:8000/api/regulatory-rules/`
- **Compliance API**: `http://localhost:8000/api/compliance/`

---

## Troubleshooting

### Common Issues

**1. Database Connection Error**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -h localhost -U Arc_New -d postgres
```

**2. Redis Connection Error**
```bash
# Check Redis is running
redis-cli ping

# Start Redis if not running
redis-server
```

**3. Celery Not Processing Tasks**
```bash
# Check worker is running
celery -A arc_backend inspect active

# Restart worker
sudo systemctl restart arc-celery-worker
```

**4. Static Files Not Loading**
```bash
# Collect static files
python manage.py collectstatic --noinput

```

**5. Migration Issues**
```bash
# Show migrations
python manage.py showmigrations

# Run migrations
python manage.py migrate

# Fake initial if needed
python manage.py migrate --fake-initial
```

---

## Security Checklist

- ✅ Set `DEBUG=False` in production
- ✅ Use strong `SECRET_KEY` (50+ characters)
- ✅ Configure `ALLOWED_HOSTS` properly
- ✅ Set `CORS_ALLOW_ALL_ORIGINS=False` in production
- ✅ Use HTTPS (configure SSL certificate)
- ✅ Enable database encryption at rest (RDS)
- ✅ Use VPC for database and Redis
- ✅ Configure security groups (restrict ports)
- ✅ Use IAM roles instead of hardcoded credentials
- ✅ Regular backups of database

---

## Performance Optimization

**1. Increase Gunicorn Workers**
```bash
# Formula: (2 x CPU cores) + 1
gunicorn --workers 5 --bind :8000 arc_backend.wsgi:application
```

**2. Increase Celery Concurrency**
```bash
celery -A arc_backend worker --concurrency=4
```

**3. Enable Database Connection Pooling**
Add to settings.py:
```python
DATABASES['default']['CONN_MAX_AGE'] = 600
```

**4. Configure Redis Persistence**
```bash
# Edit redis.conf
appendonly yes
appendfsync everysec
```

---

## Backup and Restore

**Backup Database:**
```bash
pg_dump -h localhost -U Arc_New postgres > backup_$(date +%Y%m%d).sql
```

**Restore Database:**
```bash
psql -h localhost -U Arc_New postgres < backup_20260320.sql
```

**Backup Redis:**
```bash
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup_redis_$(date +%Y%m%d).rdb
```

---

## Support

For issues or questions:
- Check logs: `sudo journalctl -u arc-backend -f`
- Review Django documentation: https://docs.djangoproject.com/
- Review Celery documentation: https://docs.celeryproject.org/

---

**Last Updated**: March 2026
