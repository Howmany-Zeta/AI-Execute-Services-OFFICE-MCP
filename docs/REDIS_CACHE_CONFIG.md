# Redis Cache Configuration Guide

## Overview

The MCP server uses a dual-layer caching strategy for optimal performance:
- **L1 Cache**: In-memory LRU cache (fast access, 5 minutes TTL)
- **L2 Cache**: Redis cache (persistent, 1 day TTL)

## TTL Strategy

The server implements intelligent TTL (Time-To-Live) strategies based on data type:

### Default TTL Values

| Data Type | TTL | Reason |
|-----------|-----|--------|
| Historical time series data | 7 days (604800s) | Historical data rarely changes |
| Recent time series data | 1 hour (3600s) | Recent data may update frequently |
| News data | 5 minutes (300s) | News is time-sensitive |
| Metadata operations | 1 day (86400s) | Metadata changes infrequently |
| Search operations | 10 minutes (600s) | Search results may vary |
| Info operations | 1 hour (3600s) | Info data is relatively stable |
| Default | 10 minutes (600s) | Safe default for unknown types |

### Cache Layer TTL

- **L1 Cache (LRU)**: 5 minutes (300s) - Fast access layer
- **L2 Cache (Redis)**: 1 day (86400s) - Persistent cache layer

## Configuration

### Environment Variables

```bash
# Enable caching
TOOL_EXECUTOR_ENABLE_CACHE=true

# Cache size (number of entries)
TOOL_EXECUTOR_CACHE_SIZE=200

# Base cache TTL (seconds)
TOOL_EXECUTOR_CACHE_TTL=7200

# Enable dual-layer cache (L1 + L2)
TOOL_EXECUTOR_ENABLE_DUAL_CACHE=true

# Enable Redis as L2 cache
TOOL_EXECUTOR_ENABLE_REDIS_CACHE=true

# Redis cache TTL (seconds)
TOOL_EXECUTOR_REDIS_CACHE_TTL=86400

# L1 cache TTL (seconds)
TOOL_EXECUTOR_L1_CACHE_TTL=300

# Redis connection
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=your_password  # Optional
```

### Docker Compose Configuration

The `docker-compose.mcp.yml` file is pre-configured with optimal Redis settings:

```yaml
services:
  aiecs-apisource-mcp:
    environment:
      - TOOL_EXECUTOR_ENABLE_CACHE=true
      - TOOL_EXECUTOR_ENABLE_DUAL_CACHE=true
      - TOOL_EXECUTOR_ENABLE_REDIS_CACHE=true
      - TOOL_EXECUTOR_REDIS_CACHE_TTL=86400
      - TOOL_EXECUTOR_L1_CACHE_TTL=300
      - REDIS_HOST=redis
      - REDIS_PORT=6379

  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
```

## Redis Memory Management

### Recommended Settings

- **Max Memory**: 512MB (adjust based on your workload)
- **Eviction Policy**: `allkeys-lru` (evict least recently used keys)
- **Persistence**: AOF (Append Only File) enabled for durability

### Memory Calculation

Approximate memory usage:
- Average cache entry: ~10-50KB
- 512MB can hold: ~10,000-50,000 entries
- With 1-day TTL: Suitable for moderate to high traffic

### Scaling Recommendations

| Traffic Level | Max Memory | Expected Entries |
|---------------|------------|------------------|
| Low (< 100 req/min) | 256MB | 5,000-25,000 |
| Medium (100-1000 req/min) | 512MB | 10,000-50,000 |
| High (> 1000 req/min) | 1GB+ | 20,000-100,000+ |

## Performance Benefits

### Cache Hit Rates

With Redis caching enabled:
- **L1 Cache Hit**: < 1ms response time
- **L2 Cache Hit**: < 5ms response time
- **Cache Miss**: Full API call (varies by provider, typically 100-500ms)

### Expected Improvements

- **API Call Reduction**: 60-80% reduction in external API calls
- **Response Time**: 50-90% faster for cached responses
- **Rate Limit Protection**: Reduced risk of hitting provider rate limits
- **Cost Savings**: Lower API usage costs

## Monitoring

### Health Check

Redis health is monitored via:
```bash
curl http://localhost:5055/health
```

Response includes Redis connection status:
```json
{
  "status": "healthy",
  "redis": {
    "connected": true,
    "info": {...}
  }
}
```

### Cache Statistics

Monitor cache performance:
- Cache hit/miss ratios
- Memory usage
- Eviction rates
- TTL distribution

## Troubleshooting

### Redis Connection Issues

If Redis is unavailable:
1. Server continues with LRU cache only
2. Check Redis container: `docker ps | grep redis`
3. Check Redis logs: `docker logs aiecs-apisource-mcp-redis`
4. Verify network: `docker network inspect aiecs-apisource-mcp-network`

### Memory Issues

If Redis runs out of memory:
1. Increase `maxmemory` in Redis config
2. Adjust `TOOL_EXECUTOR_CACHE_SIZE` to reduce entries
3. Reduce `TOOL_EXECUTOR_REDIS_CACHE_TTL` for shorter retention

### Performance Issues

If cache performance is poor:
1. Check Redis connection latency
2. Monitor cache hit rates
3. Adjust TTL values based on data freshness requirements
4. Consider Redis clustering for high-traffic scenarios

## Best Practices

1. **TTL Selection**: Choose TTL based on data update frequency
2. **Memory Management**: Monitor Redis memory usage regularly
3. **Cache Warming**: Pre-populate cache for frequently accessed data
4. **Monitoring**: Set up alerts for Redis health and memory usage
5. **Backup**: Regular Redis backups for data persistence

## Production Recommendations

1. **Enable Redis**: Always use Redis in production for optimal performance
2. **Memory Allocation**: Allocate 512MB-1GB for Redis based on traffic
3. **Persistence**: Enable AOF for data durability
4. **Monitoring**: Set up Redis monitoring and alerts
5. **Scaling**: Consider Redis clustering for high-availability scenarios
