# MCP Server Deployment Guide

This guide covers deployment options for the MCP server.

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -e .

# Set environment variables
export DOCUMENTSERVER_URL=http://localhost:8000
export DOCUMENTSERVER_JWT_SECRET=your_secret

# Run server
python -m aiecs.main_mcp
```

### Docker Deployment

```bash
# Build image
docker build -f Dockerfile.mcp -t aiecs-office-mcp:latest .

# Run container
docker run -p 5040:5040 \
  -e DOCUMENTSERVER_URL=http://documentserver:8000 \
  -e DOCUMENTSERVER_JWT_SECRET=your_secret \
  aiecs-office-mcp:latest
```

### Docker Compose

```bash
# Start services (MCP server + Redis)
docker-compose -f docker-compose.mcp.yml up -d

# View logs
docker-compose -f docker-compose.mcp.yml logs -f aiecs-office-mcp

# Stop services
docker-compose -f docker-compose.mcp.yml down
```

## Environment Configuration

### Required Configuration

Create a `.env` file or set environment variables:

```bash
# Server configuration
MCP_HOST=0.0.0.0
MCP_PORT=5040
MCP_LOG_LEVEL=info

# DocumentServer (ONLYOFFICE) - required for office tools
DOCUMENTSERVER_URL=http://localhost:8000
DOCUMENTSERVER_JWT_SECRET=your_jwt_secret
DOCUMENTSERVER_JWT_IN_BODY=true

# GCS for office tools (gs:// paths)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Optional Configuration

```bash
# OpenAI function calling format endpoint
MCP_ENABLE_OPENAI_FORMAT=true

# Tool executor caching
TOOL_EXECUTOR_ENABLE_CACHE=true
TOOL_EXECUTOR_CACHE_SIZE=200
TOOL_EXECUTOR_CACHE_TTL=7200

# Redis configuration (for distributed caching)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
```

## Production Deployment

### Docker Production

```bash
# Build production image
docker build -f Dockerfile.mcp -t aiecs-office-mcp:latest .

# Run with environment file
docker run -d \
  --name aiecs-office-mcp \
  -p 5040:5040 \
  --env-file .env.production \
  --restart unless-stopped \
  aiecs-office-mcp:latest
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  aiecs-office-mcp:
    build:
      dockerfile: Dockerfile.mcp
      target: production
    restart: unless-stopped
    ports:
      - "5040:5040"
    env_file:
      - .env.production
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5040/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Reverse Proxy Setup

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name mcp.example.com;

    location / {
        proxy_pass http://localhost:5040;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Traefik Configuration

```yaml
services:
  aiecs-office-mcp:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mcp.rule=Host(`mcp.example.com`)"
      - "traefik.http.routers.mcp.entrypoints=websecure"
      - "traefik.http.routers.mcp.tls.certresolver=letsencrypt"
```

### HTTPS/TLS Setup

Use Let's Encrypt with Certbot:

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d mcp.example.com

# Auto-renewal (already configured)
sudo certbot renew --dry-run
```

## Monitoring

### Health Checks

```bash
# Check server health
curl http://localhost:5040/health

# Expected response
{
  "status": "healthy",
  "version": "1.0.0",
  "server_type": "office_mcp",
  "tools": ["office_execute_builder", "office_edit_document", "office_read_document", "office_merge_documents", "office_apply_template", "office_call_api"],
  "tool_count": 6,
  "documentserver_reachable": true
}
```

### Logging

Logs are output to stdout/stderr. For production:

```bash
# Docker logging
docker logs -f aiecs-office-mcp

# Docker Compose logging
docker-compose -f docker-compose.mcp.yml logs -f aiecs-office-mcp

# Redirect to file
python -m aiecs.main_mcp > aiecs-office-mcp.log 2>&1
```

### Metrics

The server exposes health metrics via the `/health` endpoint. For production monitoring:

1. Set up a monitoring service (Prometheus, Datadog, etc.)
2. Configure health check endpoint scraping
3. Monitor `documentserver_reachable` status
4. Alert on unhealthy providers

## Scaling

### Horizontal Scaling

Run multiple instances behind a load balancer:

```yaml
# docker-compose.scale.yml
services:
  aiecs-office-mcp:
    deploy:
      replicas: 3
    # ... configuration
```

### Redis for Distributed Caching

Enable Redis for shared cache across instances:

```bash
# Set environment variables
export TOOL_EXECUTOR_ENABLE_DUAL_CACHE=true
export TOOL_EXECUTOR_ENABLE_REDIS_CACHE=true
export REDIS_HOST=redis
export REDIS_PORT=6379
```

## Security

### API Key and Secret Management

- Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never commit `DOCUMENTSERVER_JWT_SECRET` or GCS credentials to version control
- Rotate JWT secret regularly
- Use different secrets for different environments

### Network Security

- Use HTTPS/TLS in production
- Restrict network access (firewall rules)
- Use VPN or private networks for internal services
- Implement rate limiting at reverse proxy level

### Container Security

- Run containers as non-root user
- Use minimal base images
- Regularly update dependencies
- Scan images for vulnerabilities

## Troubleshooting

### Server Won't Start

1. Check port availability: `netstat -tuln | grep 5040`
2. Verify environment variables are set (DOCUMENTSERVER_URL, DOCUMENTSERVER_JWT_SECRET)
3. Check logs for errors: `docker logs aiecs-office-mcp`

### DocumentServer Errors

1. Verify DocumentServer is reachable: `curl http://localhost:5040/health` (check `documentserver_reachable`)
2. Check JWT secret matches DocumentServer configuration
3. Ensure DOCUMENTSERVER_JWT_IN_BODY matches DocumentServer settings
4. For GCS: verify GOOGLE_APPLICATION_CREDENTIALS is set

### Performance Issues

1. Enable caching: `TOOL_EXECUTOR_ENABLE_CACHE=true`
2. Increase cache size: `TOOL_EXECUTOR_CACHE_SIZE=500`
3. Use Redis for distributed caching
4. Monitor provider response times

## Backup and Recovery

### Configuration Backup

Backup your `.env` file and environment configuration:

```bash
# Backup environment file
cp .env .env.backup

# Store in secure location
# (Use secrets management in production)
```

### Redis Data Backup

If using Redis for caching:

```bash
# Redis persistence is enabled by default
# Data is stored in Docker volume: redis-data

# Backup volume
docker run --rm \
  -v mcp_redis-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/redis-backup.tar.gz /data
```

## Upgrading

### Docker Image Update

```bash
# Pull latest image
docker pull aiecs-office-mcp:latest

# Restart container
docker-compose -f docker-compose.mcp.yml up -d --force-recreate aiecs-office-mcp
```

### Configuration Updates

1. Update `.env` file with new configuration
2. Restart server: `docker-compose restart aiecs-office-mcp`
3. Verify health: `curl http://localhost:5040/health`

## Support

For deployment issues:
- Check [MCP Server Configuration](aiecs/mcp/README.md)
- Review [Migration Guide](MCP_MIGRATION_GUIDE.md)
- Check server logs for errors
- Verify environment variables are set correctly
