# Captcha Storage Concurrency Analysis

## Current Implementation

### SQLite WAL Mode Configuration

The captcha storage system uses SQLite with **WAL (Write-Ahead Logging) mode** enabled. This configuration provides:

1. **WAL Mode**: Enabled via `PRAGMA journal_mode=WAL` on each connection
2. **Busy Timeout**: Set to 5000ms (5 seconds) via `PRAGMA busy_timeout=5000`
3. **Connection Management**: Each operation creates a new SQLAlchemy session and closes it immediately
4. **Database Location**: Uses `data/mindgraph.db` (or configured via `DATABASE_URL`)

### How WAL Mode Works

**WAL (Write-Ahead Logging)** is SQLite's concurrent access mode that allows:

- **Multiple concurrent readers**: Many read operations can happen simultaneously
- **One writer at a time**: Only one write operation can proceed, but readers don't block writers
- **Immediate visibility**: Changes are immediately visible to all connections
- **Better concurrency**: Much better than default rollback journal mode

**SHM (Shared Memory) File**: 
- Created automatically when WAL mode is enabled
- Used for coordinating between multiple database connections
- Typically very small (few KB)

**WAL File**:
- Stores uncommitted changes temporarily
- Merged back to main database during checkpoint
- Can grow if checkpointing is infrequent
- Automatically checkpointed every 5 minutes in our system

### Current Architecture

```
User Request → FastAPI → SQLiteCaptchaStorage → SQLAlchemy Session → SQLite DB (WAL mode)
                                                      ↓
                                              New session per operation
                                              (opened and closed immediately)
```

## Concurrency Characteristics

### Theoretical Limits

SQLite WAL mode can handle:
- **Hundreds of concurrent readers** (limited mainly by system resources)
- **One writer at a time** (writers queue behind each other)
- **Mixed read/write workloads** (reads don't block writes, writes don't block reads)

### Practical Considerations

1. **Write Contention**: 
   - Multiple simultaneous writes will queue
   - Busy timeout (5 seconds) prevents indefinite waiting
   - If timeout exceeded, operation fails with "database is locked"

2. **Read Performance**:
   - Reads are very fast and don't block each other
   - Can handle hundreds of concurrent reads easily

3. **Write Performance**:
   - Each write requires exclusive access
   - Write latency increases with contention
   - Typical write latency: 1-10ms under light load, 10-100ms under heavy contention

4. **Connection Pooling**:
   - SQLite doesn't use traditional connection pooling
   - Each operation creates a new connection
   - SQLAlchemy manages connection lifecycle
   - Connections are lightweight but still have overhead

## Expected Capacity

### Based on Typical Usage Patterns

**Captcha Operations per Login Flow**:
1. Generate captcha: 1 write (store)
2. Verify captcha: 1 read + 1 write (get + verify_and_remove)

**Estimated Concurrent User Capacity**:

| Scenario | Concurrent Users | Notes |
|----------|-----------------|-------|
| **Light Load** | 50-100 | Minimal contention, <10ms latency |
| **Medium Load** | 100-200 | Some write contention, 10-50ms latency |
| **Heavy Load** | 200-500 | Significant contention, may see timeouts |
| **Very Heavy Load** | 500+ | High timeout risk, consider alternatives |

**Important Notes**:
- These estimates assume typical login patterns (not all users generating/verifying captchas simultaneously)
- Actual capacity depends on:
  - Write frequency (captcha generation + verification)
  - System resources (CPU, disk I/O)
  - Database file location (local SSD vs network storage)
  - Other database operations (users, tokens, etc.)

### Bottlenecks

1. **Write Contention**: Primary bottleneck for high concurrency
2. **Disk I/O**: SQLite performance depends on disk speed
3. **Session Overhead**: Creating/closing sessions has overhead
4. **WAL Checkpointing**: Periodic checkpointing can cause brief pauses

## Testing

### Running the Concurrency Test

**Full Test Suite**:
```bash
python tests/test_captcha_concurrency.py --users 100 --duration 30 --operations-per-user 20
```

**Quick Test** (multiple scenarios):
```bash
python tests/quick_captcha_test.py
```

**Custom Test**:
```bash
python tests/test_captcha_concurrency.py \
    --users 200 \
    --duration 60 \
    --operations-per-user 30 \
    --max-workers 100
```

### Test Parameters

- `--users`: Number of concurrent users to simulate
- `--duration`: Test duration in seconds
- `--operations-per-user`: Maximum operations per user
- `--max-workers`: Thread pool size (default: same as users)

### Interpreting Results

**Key Metrics**:

1. **Success Rate**: Should be >95% for production use
   - <90%: Critical issue, investigate immediately
   - 90-95%: Acceptable but monitor closely
   - >95%: Good performance

2. **Operations per Second**: Throughput metric
   - Higher is better
   - Depends on operation mix (reads vs writes)

3. **Latency Percentiles**:
   - P50 (median): Typical user experience
   - P95: 95% of users experience this or better
   - P99: 99% of users experience this or better
   - P99 > 1000ms: May indicate contention issues

4. **WAL File Growth**:
   - Should remain stable or grow slowly
   - Large growth may indicate checkpoint issues
   - Checkpoint runs every 5 minutes automatically

**Warning Signs**:

- ❌ Success rate < 90%
- ❌ "database is locked" errors
- ❌ P99 latency > 1000ms
- ❌ WAL file growing unbounded
- ❌ High error count

**Good Performance Indicators**:

- ✅ Success rate > 95%
- ✅ P95 latency < 100ms
- ✅ Stable WAL file size
- ✅ No lock timeout errors

## Optimization Recommendations

### If Hitting Concurrency Limits

1. **Increase Busy Timeout** (if seeing timeout errors):
   ```python
   # In config/database.py
   cursor.execute("PRAGMA busy_timeout=10000")  # 10 seconds
   ```

2. **Optimize Write Operations**:
   - Batch operations where possible
   - Reduce write frequency
   - Consider async write queue

3. **Monitor WAL Checkpointing**:
   - Ensure checkpoint scheduler is running
   - Check WAL file size regularly
   - Consider more frequent checkpointing under heavy load

4. **Consider Alternatives** (if >500 concurrent users):
   - **Redis**: In-memory storage, excellent for high concurrency
   - **PostgreSQL**: Better write concurrency, more overhead
   - **Distributed Cache**: For multi-server deployments

### Monitoring in Production

1. **Track Metrics**:
   - Captcha operation success rate
   - Average latency
   - Error rates (especially "database is locked")
   - WAL file size

2. **Set Alerts**:
   - Success rate < 95%
   - P95 latency > 200ms
   - Lock timeout errors > 1%

3. **Regular Testing**:
   - Run concurrency tests periodically
   - Test with realistic user patterns
   - Monitor trends over time

## Technical Details

### SQLite WAL Mode Limitations

1. **Single Writer**: Only one write transaction at a time
2. **File System Requirements**: Requires proper file locking (NFS may have issues)
3. **WAL File Size**: Can grow if checkpointing fails
4. **Cross-Process**: Works well for multi-process deployments (e.g., Gunicorn workers)

### Connection Lifecycle

```python
# Each operation:
1. Create SQLAlchemy session (SessionLocal())
2. Execute operation (store/get/verify)
3. Commit transaction
4. Close session
5. Connection returned to pool (or closed)
```

### WAL Checkpoint Process

1. Runs every 5 minutes automatically
2. Merges WAL pages into main database
3. Truncates WAL file
4. Coordinates with backup system
5. Non-blocking (runs in thread pool)

## Conclusion

The current SQLite WAL implementation should handle **100-200 concurrent users** comfortably for captcha operations. For higher concurrency requirements (>500 users), consider migrating to Redis or PostgreSQL.

**Recommendation**: 
- Monitor production metrics
- Run concurrency tests regularly
- Consider Redis if consistently hitting >200 concurrent captcha operations

