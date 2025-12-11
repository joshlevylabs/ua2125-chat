# Deployment Guide - UA2-125 AI Chatbot Assistant

This guide covers deploying the UA2-125 AI Chatbot Assistant to production environments.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Variables](#environment-variables)
3. [Deployment Options](#deployment-options)
4. [Cloud Platform Guides](#cloud-platform-guides)
5. [Security Hardening](#security-hardening)
6. [Monitoring & Logging](#monitoring--logging)
7. [Scaling Considerations](#scaling-considerations)

---

## Pre-Deployment Checklist

Before deploying to production:

- [ ] Test all functionality locally
- [ ] Review and secure environment variables
- [ ] Configure CORS to allow only your domain
- [ ] Set up SSL/TLS certificates (HTTPS)
- [ ] Implement rate limiting
- [ ] Configure logging and monitoring
- [ ] Set up backup strategy for vector index
- [ ] Test with production-scale knowledge base
- [ ] Document deployment configuration
- [ ] Plan rollback strategy

---

## Environment Variables

Create production `.env` file with secure values:

```bash
# OpenAI API
OPENAI_API_KEY=sk-prod-key-here

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Optional: Custom model configurations
# EMBEDDING_MODEL=text-embedding-3-large
# LLM_MODEL=gpt-4o-mini
```

**Security Notes:**
- Never commit `.env` files to version control
- Use secrets management systems (AWS Secrets Manager, Azure Key Vault, etc.)
- Rotate API keys regularly
- Restrict API key permissions to minimum required

---

## Deployment Options

### Option 1: Docker Deployment (Recommended)

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Install Python dependencies
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# Create data directories
RUN mkdir -p data/raw data/processed data/index

# Copy pre-built index (if available)
# COPY backend/data/index/ /app/backend/data/index/

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "app.py"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ua2125-chatbot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LOG_LEVEL=INFO
    volumes:
      - ./backend/data:/app/backend/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Build and run:**

```bash
docker-compose up -d
```

### Option 2: Traditional Server Deployment

**Using systemd (Linux):**

Create `/etc/systemd/system/ua2125-chatbot.service`:

```ini
[Unit]
Description=UA2-125 AI Chatbot Assistant
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ua2125-chat/backend
Environment="PATH=/opt/ua2125-chat/venv/bin"
EnvironmentFile=/opt/ua2125-chat/.env
ExecStart=/opt/ua2125-chat/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable ua2125-chatbot
sudo systemctl start ua2125-chatbot
sudo systemctl status ua2125-chatbot
```

### Option 3: Gunicorn with Nginx (Production)

**Install Gunicorn:**

```bash
pip install gunicorn
```

**Run with Gunicorn:**

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app:app
```

**Nginx configuration:**

Create `/etc/nginx/sites-available/ua2125-chatbot`:

```nginx
upstream ua2125_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy settings
    location / {
        proxy_pass http://ua2125_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=chatbot_limit:10m rate=10r/s;
    limit_req zone=chatbot_limit burst=20;
}
```

---

## Cloud Platform Guides

### AWS Deployment

**Option A: AWS Elastic Beanstalk**

1. Install EB CLI:
```bash
pip install awsebcli
```

2. Initialize:
```bash
eb init -p python-3.11 ua2125-chatbot
```

3. Create environment:
```bash
eb create ua2125-prod
```

4. Set environment variables:
```bash
eb setenv OPENAI_API_KEY=your-key-here
```

5. Deploy:
```bash
eb deploy
```

**Option B: AWS ECS (Docker)**

1. Build and push Docker image to ECR
2. Create ECS task definition
3. Configure ECS service with load balancer
4. Set up CloudWatch for logging

**Option C: AWS Lambda + API Gateway**

For serverless deployment (requires code modifications for cold starts).

### Azure Deployment

**Azure App Service:**

1. Create App Service:
```bash
az webapp create --resource-group myResourceGroup \
  --plan myAppServicePlan --name ua2125-chatbot \
  --runtime "PYTHON:3.11"
```

2. Configure environment variables:
```bash
az webapp config appsettings set --resource-group myResourceGroup \
  --name ua2125-chatbot \
  --settings OPENAI_API_KEY="your-key-here"
```

3. Deploy:
```bash
az webapp up --name ua2125-chatbot
```

### Google Cloud Platform

**Google Cloud Run:**

1. Build container:
```bash
gcloud builds submit --tag gcr.io/PROJECT-ID/ua2125-chatbot
```

2. Deploy:
```bash
gcloud run deploy ua2125-chatbot \
  --image gcr.io/PROJECT-ID/ua2125-chatbot \
  --platform managed \
  --set-env-vars OPENAI_API_KEY=your-key-here
```

### DigitalOcean App Platform

1. Connect GitHub repository
2. Configure build settings (Python)
3. Set environment variables in dashboard
4. Deploy

### Heroku

Create `Procfile`:

```
web: cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

Deploy:

```bash
heroku create ua2125-chatbot
heroku config:set OPENAI_API_KEY=your-key-here
git push heroku main
```

---

## Security Hardening

### 1. CORS Configuration

Edit `backend/config.py`:

```python
# Restrict to your domain only
CORS_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com"
]
```

### 2. Rate Limiting

Add rate limiting to `app.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    # ... existing code
```

Install dependency:
```bash
pip install slowapi
```

### 3. API Key Management

Use environment-specific secrets management:

- **AWS:** AWS Secrets Manager
- **Azure:** Azure Key Vault
- **GCP:** Google Secret Manager
- **Docker:** Docker Secrets

### 4. HTTPS/TLS

Always use HTTPS in production. Options:

- **Let's Encrypt:** Free SSL certificates
- **Cloudflare:** Free SSL + CDN
- **Cloud Provider:** Built-in SSL (AWS Certificate Manager, etc.)

### 5. Input Validation

Already implemented via Pydantic models. Add additional sanitization if needed.

### 6. Logging Sensitive Data

Ensure logs don't contain API keys or sensitive information:

```python
# In config.py or logging setup
import logging

# Filter to redact sensitive info
class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        record.msg = record.msg.replace(OPENAI_API_KEY, "***REDACTED***")
        return True

logger.addFilter(SensitiveDataFilter())
```

---

## Monitoring & Logging

### Application Monitoring

**Option 1: Prometheus + Grafana**

Add metrics endpoint:

```python
from prometheus_client import Counter, Histogram, generate_latest

chat_requests = Counter('chat_requests_total', 'Total chat requests')
chat_duration = Histogram('chat_duration_seconds', 'Chat processing time')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

**Option 2: Cloud Provider Monitoring**

- **AWS:** CloudWatch
- **Azure:** Application Insights
- **GCP:** Cloud Monitoring

**Option 3: Third-Party Services**

- **Datadog**
- **New Relic**
- **Sentry** (error tracking)

### Log Aggregation

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Loki + Grafana**
- **Cloud Logging** (CloudWatch Logs, Azure Log Analytics)

---

## Scaling Considerations

### Horizontal Scaling

Run multiple instances behind a load balancer:

```yaml
# docker-compose.yml with scaling
services:
  ua2125-chatbot:
    # ... existing config
    deploy:
      replicas: 3

  nginx:
    image: nginx
    ports:
      - "80:80"
    depends_on:
      - ua2125-chatbot
```

### Vector Store Scaling

For large knowledge bases (>10,000 documents), migrate to dedicated vector database:

**Pinecone:**

```python
import pinecone

pinecone.init(api_key="your-key", environment="us-west1-gcp")
index = pinecone.Index("ua2125-index")

# Query
results = index.query(vector=query_embedding, top_k=5)
```

**Weaviate, Qdrant, or ChromaDB** offer similar capabilities.

### Caching

Add Redis for caching frequent queries:

```python
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Cache responses
def get_cached_response(query_hash):
    return redis_client.get(f"chat:{query_hash}")

def cache_response(query_hash, response):
    redis_client.setex(f"chat:{query_hash}", 3600, response)
```

### Load Balancing

- **AWS:** Application Load Balancer (ALB)
- **Azure:** Azure Load Balancer
- **GCP:** Cloud Load Balancing
- **Self-hosted:** Nginx, HAProxy

---

## Backup Strategy

### Vector Index Backup

Regularly backup the vector index:

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/ua2125-chatbot"

mkdir -p $BACKUP_DIR

# Backup index files
cp -r /opt/ua2125-chat/backend/data/index $BACKUP_DIR/index_$DATE

# Backup knowledge base
cp -r /opt/ua2125-chat/backend/data/raw $BACKUP_DIR/raw_$DATE

# Compress
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz $BACKUP_DIR/*_$DATE

# Clean up old backups (keep last 30 days)
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +30 -delete
```

Schedule with cron:

```bash
0 2 * * * /opt/ua2125-chat/backup.sh
```

---

## Health Checks

The `/health` endpoint is already implemented. Configure monitoring:

```bash
# Example: Monitor with curl
while true; do
  if ! curl -f http://localhost:8000/health; then
    echo "Health check failed!"
    # Send alert (email, Slack, PagerDuty, etc.)
  fi
  sleep 60
done
```

---

## Rollback Plan

1. **Version Control:** Tag each deployment
2. **Database/Index Snapshots:** Backup before updates
3. **Blue-Green Deployment:** Run old and new versions simultaneously
4. **Quick Rollback:** Keep previous container/code available

---

## Production Checklist

- [ ] SSL/TLS configured
- [ ] CORS restricted to production domain
- [ ] Rate limiting enabled
- [ ] Environment variables secured
- [ ] Monitoring and alerting configured
- [ ] Logs aggregated and searchable
- [ ] Backup strategy implemented
- [ ] Health checks configured
- [ ] Load balancer configured (if multi-instance)
- [ ] Domain name configured
- [ ] API keys rotated
- [ ] Documentation updated
- [ ] Rollback plan tested

---

## Support

For deployment issues or questions:

- Review application logs
- Check `/health` endpoint status
- Verify environment variables
- Consult cloud provider documentation

---

**Deployment completed successfully?** Great! Your UA2-125 AI Chatbot Assistant is now live.
