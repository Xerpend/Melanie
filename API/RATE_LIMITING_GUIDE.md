# Rate Limiting Guide

## Overview

The Melanie AI API implements rate limiting to ensure fair usage and system stability. This guide covers rate limit policies, monitoring, and best practices for handling rate limits in your applications.

## Rate Limit Policies

### Default Limits

- **Rate**: 100 requests per minute per API key
- **Window**: Sliding 60-second window
- **Burst**: Short bursts allowed within the window
- **Enforcement**: Per API key basis

### Rate Limit Algorithm

The API uses a sliding window rate limiter:

```python
class RateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)  # key_id -> [timestamps]
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key_id: str, limit: int = 100) -> Tuple[bool, int]:
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            
            # Remove old requests (older than 1 minute)
            self._requests[key_id] = [
                req_time for req_time in self._requests[key_id]
                if req_time > minute_ago
            ]
            
            current_count = len(self._requests[key_id])
            
            if current_count >= limit:
                return False, 0
            
            # Add current request
            self._requests[key_id].append(now)
            remaining = limit - (current_count + 1)
            
            return True, remaining
```

## Rate Limit Headers

### Response Headers

Every API response includes rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 60
```

#### Header Descriptions

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `X-RateLimit-Window` | Window duration in seconds |

### Example Response

```bash
curl -I -H "Authorization: Bearer mel_your_key" \
     http://your-tailscale-ip:8000/health

HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1640995260
X-RateLimit-Window: 60
Content-Type: application/json
```

## Rate Limit Exceeded Response

### 429 Too Many Requests

When rate limit is exceeded:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests per minute exceeded",
  "details": {
    "limit": 100,
    "remaining": 0,
    "reset_at": "2023-12-01T10:05:00Z",
    "retry_after": 45
  },
  "timestamp": "2023-12-01T10:04:15Z"
}
```

### Response Headers

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995260
Retry-After: 45
Content-Type: application/json
```

## Handling Rate Limits

### Basic Retry Logic

#### Python Implementation

```python
import time
import random
import requests
from typing import Optional

class RateLimitHandler:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    def make_request_with_retry(self, func, *args, **kwargs):
        """Make request with automatic retry on rate limit."""
        for attempt in range(self.max_retries + 1):
            try:
                response = func(*args, **kwargs)
                
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        retry_after = self._get_retry_delay(response)
                        print(f"Rate limited. Retrying in {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError("Max retries exceeded")
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                raise e
        
        raise Exception("Request failed after all retries")
    
    def _get_retry_delay(self, response) -> int:
        """Get retry delay from response headers."""
        # Try Retry-After header first
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            return int(retry_after)
        
        # Calculate from rate limit reset
        reset_time = response.headers.get('X-RateLimit-Reset')
        if reset_time:
            current_time = time.time()
            reset_timestamp = int(reset_time)
            return max(1, reset_timestamp - current_time)
        
        # Default fallback
        return 60

# Usage
handler = RateLimitHandler(max_retries=3)

def make_api_call():
    return requests.post(
        "http://your-tailscale-ip:8000/chat/completions",
        headers={"Authorization": "Bearer mel_your_key"},
        json={"model": "Melanie-3", "messages": [{"role": "user", "content": "Hello"}]}
    )

response = handler.make_request_with_retry(make_api_call)
```

#### JavaScript Implementation

```javascript
class RateLimitHandler {
    constructor(maxRetries = 3) {
        this.maxRetries = maxRetries;
    }

    async makeRequestWithRetry(requestFunc) {
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await requestFunc();
                
                if (response.status === 429) {
                    if (attempt < this.maxRetries) {
                        const retryAfter = this.getRetryDelay(response);
                        console.log(`Rate limited. Retrying in ${retryAfter} seconds...`);
                        await this.sleep(retryAfter * 1000);
                        continue;
                    } else {
                        throw new Error('Max retries exceeded');
                    }
                }
                
                return response;
                
            } catch (error) {
                if (attempt < this.maxRetries) {
                    const waitTime = (Math.pow(2, attempt) + Math.random()) * 1000;
                    await this.sleep(waitTime);
                    continue;
                }
                throw error;
            }
        }
    }

    getRetryDelay(response) {
        // Try Retry-After header first
        const retryAfter = response.headers.get('Retry-After');
        if (retryAfter) {
            return parseInt(retryAfter);
        }

        // Calculate from rate limit reset
        const resetTime = response.headers.get('X-RateLimit-Reset');
        if (resetTime) {
            const currentTime = Math.floor(Date.now() / 1000);
            const resetTimestamp = parseInt(resetTime);
            return Math.max(1, resetTimestamp - currentTime);
        }

        // Default fallback
        return 60;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Usage
const handler = new RateLimitHandler(3);

const makeApiCall = () => {
    return fetch('http://your-tailscale-ip:8000/chat/completions', {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer mel_your_key',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            model: 'Melanie-3',
            messages: [{role: 'user', content: 'Hello'}]
        })
    });
};

const response = await handler.makeRequestWithRetry(makeApiCall);
```

### Advanced Rate Limit Handling

#### Exponential Backoff with Jitter

```python
import random
import time

class ExponentialBackoffHandler:
    def __init__(self, base_delay=1, max_delay=60, jitter=True):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        if self.jitter:
            # Add random jitter (±25% of delay)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    async def retry_with_backoff(self, func, max_retries=5):
        """Retry function with exponential backoff."""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await func()
            except RateLimitError as e:
                last_exception = e
                if attempt < max_retries:
                    delay = self.calculate_delay(attempt)
                    print(f"Rate limited. Waiting {delay:.2f}s before retry {attempt + 1}")
                    await asyncio.sleep(delay)
                    continue
                break
            except Exception as e:
                # Don't retry on non-rate-limit errors
                raise e
        
        raise last_exception
```

#### Rate Limit Monitoring

```python
class RateLimitMonitor:
    def __init__(self):
        self.request_history = []
        self.rate_limit_events = []
    
    def record_request(self, response):
        """Record request and rate limit information."""
        timestamp = time.time()
        
        rate_limit_info = {
            'timestamp': timestamp,
            'limit': int(response.headers.get('X-RateLimit-Limit', 0)),
            'remaining': int(response.headers.get('X-RateLimit-Remaining', 0)),
            'reset': int(response.headers.get('X-RateLimit-Reset', 0)),
            'status_code': response.status_code
        }
        
        self.request_history.append(rate_limit_info)
        
        # Record rate limit events
        if response.status_code == 429:
            self.rate_limit_events.append({
                'timestamp': timestamp,
                'retry_after': response.headers.get('Retry-After'),
                'reset_time': response.headers.get('X-RateLimit-Reset')
            })
    
    def get_usage_stats(self):
        """Get rate limit usage statistics."""
        if not self.request_history:
            return {}
        
        recent_requests = [
            req for req in self.request_history
            if time.time() - req['timestamp'] < 3600  # Last hour
        ]
        
        return {
            'total_requests': len(recent_requests),
            'rate_limited_requests': len([r for r in recent_requests if r['status_code'] == 429]),
            'average_remaining': sum(r['remaining'] for r in recent_requests) / len(recent_requests),
            'rate_limit_events': len(self.rate_limit_events),
            'last_reset': max(r['reset'] for r in recent_requests) if recent_requests else None
        }
    
    def should_throttle(self, threshold=10):
        """Check if client should throttle requests."""
        if not self.request_history:
            return False
        
        recent = [r for r in self.request_history if time.time() - r['timestamp'] < 60]
        if not recent:
            return False
        
        latest = recent[-1]
        return latest['remaining'] < threshold
```

## Client-Side Rate Limiting

### Request Queue Implementation

```python
import asyncio
from collections import deque
import time

class RequestQueue:
    def __init__(self, rate_limit=100, window=60):
        self.rate_limit = rate_limit
        self.window = window
        self.queue = deque()
        self.request_times = deque()
        self.processing = False
    
    async def add_request(self, request_func, *args, **kwargs):
        """Add request to queue."""
        future = asyncio.Future()
        self.queue.append((request_func, args, kwargs, future))
        
        if not self.processing:
            asyncio.create_task(self._process_queue())
        
        return await future
    
    async def _process_queue(self):
        """Process queued requests respecting rate limits."""
        self.processing = True
        
        while self.queue:
            # Clean old request times
            now = time.time()
            while self.request_times and now - self.request_times[0] > self.window:
                self.request_times.popleft()
            
            # Check if we can make a request
            if len(self.request_times) >= self.rate_limit:
                # Wait until we can make another request
                sleep_time = self.window - (now - self.request_times[0])
                await asyncio.sleep(sleep_time)
                continue
            
            # Process next request
            request_func, args, kwargs, future = self.queue.popleft()
            
            try:
                result = await request_func(*args, **kwargs)
                self.request_times.append(now)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        self.processing = False

# Usage
queue = RequestQueue(rate_limit=100, window=60)

async def make_api_call(message):
    # Your API call implementation
    response = await client.chat_completion(
        model="Melanie-3",
        messages=[{"role": "user", "content": message}]
    )
    return response

# Queue requests
result1 = await queue.add_request(make_api_call, "Hello")
result2 = await queue.add_request(make_api_call, "How are you?")
```

### Batch Request Optimization

```python
class BatchRequestManager:
    def __init__(self, batch_size=10, batch_timeout=1.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests = []
        self.batch_timer = None
    
    async def add_request(self, request_data):
        """Add request to current batch."""
        future = asyncio.Future()
        self.pending_requests.append((request_data, future))
        
        # Start batch timer if this is the first request
        if len(self.pending_requests) == 1:
            self.batch_timer = asyncio.create_task(
                self._batch_timeout_handler()
            )
        
        # Process batch if it's full
        if len(self.pending_requests) >= self.batch_size:
            await self._process_batch()
        
        return await future
    
    async def _batch_timeout_handler(self):
        """Process batch after timeout."""
        await asyncio.sleep(self.batch_timeout)
        if self.pending_requests:
            await self._process_batch()
    
    async def _process_batch(self):
        """Process current batch of requests."""
        if not self.pending_requests:
            return
        
        batch = self.pending_requests.copy()
        self.pending_requests.clear()
        
        if self.batch_timer:
            self.batch_timer.cancel()
            self.batch_timer = None
        
        # Process batch (implement your batch processing logic)
        try:
            results = await self._execute_batch([req[0] for req in batch])
            
            # Set results for each future
            for i, (_, future) in enumerate(batch):
                if i < len(results):
                    future.set_result(results[i])
                else:
                    future.set_exception(Exception("Batch processing failed"))
        
        except Exception as e:
            # Set exception for all futures
            for _, future in batch:
                future.set_exception(e)
    
    async def _execute_batch(self, requests):
        """Execute batch of requests."""
        # Implement your batch execution logic here
        # This could involve making multiple API calls concurrently
        # while respecting rate limits
        
        tasks = []
        for request in requests:
            task = asyncio.create_task(self._single_request(request))
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _single_request(self, request_data):
        """Execute single request with rate limiting."""
        # Implement your single request logic
        pass
```

## Monitoring and Analytics

### Rate Limit Metrics

```python
class RateLimitMetrics:
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'rate_limited_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0,
            'peak_usage_time': None,
            'rate_limit_events': []
        }
    
    def record_request(self, response, response_time):
        """Record request metrics."""
        self.metrics['total_requests'] += 1
        
        if response.status_code == 200:
            self.metrics['successful_requests'] += 1
        elif response.status_code == 429:
            self.metrics['rate_limited_requests'] += 1
            self.metrics['rate_limit_events'].append({
                'timestamp': time.time(),
                'remaining': response.headers.get('X-RateLimit-Remaining'),
                'reset': response.headers.get('X-RateLimit-Reset')
            })
        else:
            self.metrics['failed_requests'] += 1
        
        # Update average response time
        total_time = self.metrics['average_response_time'] * (self.metrics['total_requests'] - 1)
        self.metrics['average_response_time'] = (total_time + response_time) / self.metrics['total_requests']
    
    def get_rate_limit_efficiency(self):
        """Calculate rate limit efficiency."""
        if self.metrics['total_requests'] == 0:
            return 0
        
        return (self.metrics['successful_requests'] / self.metrics['total_requests']) * 100
    
    def get_report(self):
        """Generate rate limit report."""
        return {
            'efficiency': self.get_rate_limit_efficiency(),
            'rate_limit_percentage': (self.metrics['rate_limited_requests'] / max(1, self.metrics['total_requests'])) * 100,
            'average_response_time': self.metrics['average_response_time'],
            'total_requests': self.metrics['total_requests'],
            'recent_rate_limits': len([
                event for event in self.metrics['rate_limit_events']
                if time.time() - event['timestamp'] < 3600
            ])
        }
```

## Best Practices

### 1. Implement Proper Retry Logic

```python
# Good: Exponential backoff with jitter
async def smart_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
            else:
                raise

# Bad: Fixed delay retry
async def bad_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            await asyncio.sleep(1)  # Always wait 1 second
```

### 2. Monitor Rate Limit Headers

```python
def check_rate_limit_health(response):
    """Check rate limit health and warn if approaching limit."""
    remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
    limit = int(response.headers.get('X-RateLimit-Limit', 100))
    
    usage_percentage = ((limit - remaining) / limit) * 100
    
    if usage_percentage > 90:
        print(f"WARNING: Rate limit usage at {usage_percentage:.1f}%")
    elif usage_percentage > 75:
        print(f"CAUTION: Rate limit usage at {usage_percentage:.1f}%")
```

### 3. Use Request Queuing

```python
# Good: Queue requests to respect rate limits
class RateLimitedClient:
    def __init__(self):
        self.request_queue = RequestQueue(rate_limit=90)  # Leave buffer
    
    async def make_request(self, data):
        return await self.request_queue.add_request(self._api_call, data)

# Bad: Make requests without queuing
class BadClient:
    async def make_request(self, data):
        return await self._api_call(data)  # May hit rate limits
```

### 4. Implement Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except RateLimitError as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

## Troubleshooting

### Common Issues

1. **Consistent 429 Errors**
   - Check if you're exceeding 100 requests per minute
   - Implement proper retry logic with exponential backoff
   - Consider request queuing

2. **Unexpected Rate Limits**
   - Monitor `X-RateLimit-Remaining` header
   - Check for concurrent requests from same API key
   - Verify rate limit window understanding

3. **Poor Performance Due to Rate Limiting**
   - Implement request batching where possible
   - Use multiple API keys for higher throughput
   - Optimize request frequency

### Debug Commands

```bash
# Monitor rate limit headers
curl -I -H "Authorization: Bearer mel_your_key" \
     http://your-tailscale-ip:8000/health

# Test rate limit behavior
for i in {1..105}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer mel_your_key" \
    http://your-tailscale-ip:8000/health
done
```

This rate limiting guide provides comprehensive coverage of rate limit handling, monitoring, and optimization strategies for the Melanie AI API.