# Memory Configuration Guide

## Overview

This document describes memory limits and resource management for the AIECS APISource MCP Server deployment.

## Container Memory Limits

### MCP Server Container

**Memory Limits:**
- **Maximum**: 1GB (1024MB)
- **Reserved**: 512MB
- **CPU**: 2 cores max, 0.5 cores reserved

**Rationale:**
- Base Python application: ~100-150MB
- FastMCP server: ~50-100MB
- Provider instances (30 providers): ~100-200MB
- Request handling buffers: ~50-100MB
- Python runtime overhead: ~100-200MB
- **Total estimated**: ~400-650MB under normal load
- **Safety margin**: 1GB limit provides buffer for spikes

### Redis Container

**Memory Limits:**
- **Maximum**: 768MB
- **Reserved**: 256MB
- **CPU**: 1 core max, 0.25 cores reserved
- **Redis maxmemory**: 512MB (leaves ~256MB for Redis overhead)

**Rationale:**
- Redis maxmemory: 512MB (for cached data)
- Redis overhead: ~100-200MB (process, buffers, AOF)
- **Total estimated**: ~600-700MB
- **Safety margin**: 768MB limit prevents OOM kills

## Memory Usage Patterns

### Normal Operation

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| MCP Server | 400-600MB | Base + providers + buffers |
| Redis | 200-400MB | Cache data + overhead |
| **Total** | **600MB-1GB** | Under normal load |

### Peak Load

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| MCP Server | 600-800MB | High concurrency, many requests |
| Redis | 400-600MB | Full cache + AOF buffers |
| **Total** | **1GB-1.4GB** | Peak load scenario |

## Configuration

### Docker Compose (Recommended)

```yaml
services:
  aiecs-apisource-mcp:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2.0'
        reservations:
          memory: 512M
          cpus: '0.5'
  
  redis:
    deploy:
      resources:
        limits:
          memory: 768M
          cpus: '1.0'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### Legacy Docker Compose Format

For older docker-compose versions that don't support `deploy.resources`:

```yaml
services:
  aiecs-apisource-mcp:
    mem_limit: 1g
    mem_reservation: 512m
  
  redis:
    mem_limit: 768m
    mem_reservation: 256m
```

## Memory Monitoring

### Check Container Memory Usage

```bash
# View current memory usage
docker stats aiecs-apisource-mcp aiecs-apisource-mcp-redis --no-stream

# Monitor continuously
docker stats aiecs-apisource-mcp aiecs-apisource-mcp-redis
```

### Check Redis Memory Usage

```bash
# Connect to Redis and check memory
docker exec aiecs-apisource-mcp-redis redis-cli INFO memory

# Key metrics:
# - used_memory: Current memory usage
# - used_memory_peak: Peak memory usage
# - maxmemory: Maximum memory limit
# - mem_fragmentation_ratio: Memory fragmentation
```

### Check MCP Server Memory Usage

```bash
# View process memory
docker exec aiecs-apisource-mcp ps aux

# Or from host
ps aux | grep "python -m aiecs.main_mcp"
```

## Memory Optimization

### Reduce MCP Server Memory

1. **Reduce cache size:**
   ```bash
   TOOL_EXECUTOR_CACHE_SIZE=100  # Default: 200
   ```

2. **Disable dual-layer cache** (use LRU only):
   ```bash
   TOOL_EXECUTOR_ENABLE_DUAL_CACHE=false
   TOOL_EXECUTOR_ENABLE_REDIS_CACHE=false
   ```

3. **Reduce provider instances:**
   - Only initialize needed providers
   - Lazy load providers on first use

### Reduce Redis Memory

1. **Lower maxmemory:**
   ```yaml
   command: >
     redis-server
     --maxmemory 256mb  # Reduced from 512mb
   ```

2. **Adjust eviction policy:**
   ```yaml
   --maxmemory-policy allkeys-lru  # Current: evict LRU keys
   # Alternatives:
   # --maxmemory-policy volatile-lru  # Only evict keys with TTL
   # --maxmemory-policy noeviction    # Return errors when full
   ```

3. **Reduce AOF frequency:**
   ```yaml
   --appendonly yes
   --appendfsync everysec  # Default: everysec
   # Alternatives:
   # --appendfsync no      # Let OS decide (faster, less safe)
   ```

## Scaling Recommendations

### Low Traffic (< 100 req/min)

- **MCP Server**: 512MB limit, 256MB reserved
- **Redis**: 512MB limit, 128MB reserved
- **Total**: ~1GB

### Medium Traffic (100-1000 req/min)

- **MCP Server**: 1GB limit, 512MB reserved (current)
- **Redis**: 768MB limit, 256MB reserved (current)
- **Total**: ~1.7GB

### High Traffic (> 1000 req/min)

- **MCP Server**: 2GB limit, 1GB reserved
- **Redis**: 1GB limit, 512MB reserved
- **Total**: ~3GB

## Troubleshooting

### Container OOM Killed

If containers are being killed due to OOM:

1. **Check logs:**
   ```bash
   docker logs aiecs-apisource-mcp | grep -i oom
   dmesg | grep -i oom
   ```

2. **Increase limits:**
   - Increase `memory` limit in docker-compose.yml
   - Ensure host has sufficient memory

3. **Reduce usage:**
   - Lower cache sizes
   - Reduce Redis maxmemory
   - Limit concurrent requests

### High Memory Usage

If memory usage is consistently high:

1. **Monitor patterns:**
   ```bash
   # Check memory over time
   docker stats --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" --no-stream
   ```

2. **Identify leaks:**
   - Check for memory leaks in application code
   - Monitor Redis memory fragmentation
   - Review cache TTL settings

3. **Optimize:**
   - Adjust cache TTLs (shorter = less memory)
   - Reduce cache sizes
   - Enable memory-efficient Redis settings

## Best Practices

1. **Set appropriate limits**: Always set memory limits to prevent runaway processes
2. **Monitor regularly**: Check memory usage patterns and adjust as needed
3. **Reserve resources**: Use reservations to ensure minimum resources available
4. **Plan for spikes**: Set limits higher than average usage to handle traffic spikes
5. **Test under load**: Verify memory limits work correctly under production-like load

## Production Recommendations

- **Minimum**: 1GB total (512MB MCP + 512MB Redis)
- **Recommended**: 2GB total (1GB MCP + 768MB Redis) - current configuration
- **High Availability**: 4GB+ total with multiple instances

## Environment Variables

Memory-related environment variables:

```bash
# MCP Server
# No specific memory env vars - controlled by Docker limits

# Redis
REDIS_MAXMEMORY=512mb  # Set via command in docker-compose

# Tool Executor (affects memory usage)
TOOL_EXECUTOR_CACHE_SIZE=200        # Reduce to save memory
TOOL_EXECUTOR_ENABLE_DUAL_CACHE=true  # Disable to save memory
```
