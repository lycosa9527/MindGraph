# HMAC-Based URL Signing Explanation

## Overview

HMAC (Hash-based Message Authentication Code) URL signing is a security mechanism used to protect temporary image URLs from unauthorized access. This implementation uses the same `JWT_SECRET_KEY` that's used for JWT token signing, ensuring consistent security across the application.

## How It Works

### 1. URL Generation (When Creating Temp Images)

When a temporary image is created (e.g., via `/api/generate_dingtalk`), the system generates a signed URL:

```python
def generate_signed_url(filename: str, expiration_seconds: int = 86400) -> str:
    """
    Generate a signed URL for temporary image access.
    
    Steps:
    1. Calculate expiration timestamp (current time + expiration seconds)
    2. Create message: "{filename}:{expiration}"
    3. Generate HMAC-SHA256 signature using JWT_SECRET_KEY
    4. Base64 encode signature for URL safety
    5. Return: "{filename}?sig={signature}&exp={expiration}"
    """
```

**Example Flow:**
```
Filename: dingtalk_a1b2c3d4_1704067200.png
Expiration: 1704153600 (24 hours from now)

Message: "dingtalk_a1b2c3d4_1704067200.png:1704153600"
Secret Key: JWT_SECRET_KEY (from environment)

HMAC-SHA256(message, secret_key) → Binary signature
Base64 encode → URL-safe signature string

Result: "dingtalk_a1b2c3d4_1704067200.png?sig=AbCdEf123...&exp=1704153600"
```

### 2. URL Verification (When Accessing Temp Images)

When someone tries to access a temp image URL, the system verifies the signature:

```python
def verify_signed_url(filename: str, signature: str, expiration: int) -> bool:
    """
    Verify a signed URL for temporary image access.
    
    Steps:
    1. Check if URL has expired (current time > expiration)
    2. Reconstruct message: "{filename}:{expiration}"
    3. Generate expected signature using same HMAC-SHA256
    4. Compare signatures using constant-time comparison
    5. Return True if valid and not expired, False otherwise
    """
```

**Example Verification:**
```
Received URL: /api/temp_images/dingtalk_a1b2c3d4_1704067200.png?sig=AbCdEf123...&exp=1704153600

1. Extract: filename="dingtalk_a1b2c3d4_1704067200.png", sig="AbCdEf123...", exp=1704153600
2. Check expiration: current_time (1704070000) < exp (1704153600) ✓
3. Reconstruct message: "dingtalk_a1b2c3d4_1704067200.png:1704153600"
4. Generate expected signature: HMAC-SHA256(message, JWT_SECRET_KEY)
5. Compare: received_sig == expected_sig (using constant-time comparison)
6. Result: ✓ Valid signature, not expired → Allow access
```

## Security Features

### 1. HMAC-SHA256 Algorithm
- **Cryptographically secure**: SHA-256 is a strong hash function
- **Keyed hash**: Requires secret key to generate/verify signatures
- **Tamper-proof**: Any modification to filename or expiration invalidates signature

### 2. Expiration Timestamps
- **Time-limited access**: URLs automatically expire after 24 hours
- **Server-side validation**: Expiration checked on every request
- **Prevents long-term access**: Even if URL is leaked, it becomes useless after expiration

### 3. Constant-Time Comparison
```python
# Uses hmac.compare_digest() instead of ==
# Prevents timing attacks that could reveal signature bits
return hmac.compare_digest(signature, expected_b64)
```
- **Timing attack prevention**: Comparison takes same time regardless of where mismatch occurs
- **Security best practice**: Prevents attackers from learning signature through timing analysis

### 4. URL-Safe Encoding
- **Base64 URL-safe encoding**: Signature encoded for safe use in URLs
- **No special characters**: Removes padding (`=`) to avoid URL encoding issues
- **Compatible**: Works with all HTTP clients and browsers

## Why Use JWT_SECRET_KEY?

### Advantages
1. **Single secret management**: One key to manage instead of multiple
2. **Consistent security**: Same security level as authentication tokens
3. **Simplified configuration**: No additional environment variables needed
4. **Proven security**: JWT_SECRET_KEY is already secured in production

### Security Considerations
- **Key strength**: Ensure JWT_SECRET_KEY is strong (min 32 characters, random)
- **Key rotation**: If JWT_SECRET_KEY is rotated, all signed URLs become invalid
- **Key protection**: Keep JWT_SECRET_KEY secret (never commit to git)

## URL Format

### Signed URL Structure
```
/api/temp_images/{filename}?sig={signature}&exp={expiration_timestamp}
```

**Components:**
- `filename`: Image filename (e.g., `dingtalk_a1b2c3d4_1704067200.png`)
- `sig`: Base64-encoded HMAC-SHA256 signature (URL-safe)
- `exp`: Unix timestamp when URL expires (seconds since epoch)

### Example URLs

**Valid (new format):**
```
/api/temp_images/dingtalk_a1b2c3d4_1704067200.png?sig=AbCdEf123456&exp=1704153600
```

**Invalid (missing signature):**
```
/api/temp_images/dingtalk_a1b2c3d4_1704067200.png
→ Returns 403 Forbidden
```

**Invalid (expired):**
```
/api/temp_images/dingtalk_a1b2c3d4_1704067200.png?sig=AbCdEf123456&exp=1704000000
→ Returns 403 Forbidden (expired)
```

**Invalid (tampered):**
```
/api/temp_images/other_file.png?sig=AbCdEf123456&exp=1704153600
→ Returns 403 Forbidden (signature mismatch)
```

## Implementation Details

### Code Location
- **Generation**: `routers/api.py` → `generate_signed_url()`
- **Verification**: `routers/api.py` → `verify_signed_url()`
- **Usage**: `routers/api.py` → `/api/generate_dingtalk` and `/api/temp_images/{filepath}`

### Key Functions

#### generate_signed_url()
```python
def generate_signed_url(filename: str, expiration_seconds: int = 86400) -> str:
    """
    Generate signed URL with:
    - Message: "{filename}:{expiration}"
    - Signature: HMAC-SHA256(message, JWT_SECRET_KEY)
    - Format: "{filename}?sig={signature}&exp={expiration}"
    """
```

#### verify_signed_url()
```python
def verify_signed_url(filename: str, signature: str, expiration: int) -> bool:
    """
    Verify signed URL by:
    1. Checking expiration
    2. Regenerating signature
    3. Constant-time comparison
    """
```

## Security Benefits

### 1. Prevents Unauthorized Access
- **Without signature**: Cannot access temp images
- **With invalid signature**: Access denied
- **With expired URL**: Access denied

### 2. Prevents URL Tampering
- **Filename modification**: Signature mismatch → Access denied
- **Expiration modification**: Signature mismatch → Access denied
- **Signature guessing**: Cryptographically infeasible

### 3. Time-Limited Access
- **Automatic expiration**: URLs become invalid after 24 hours
- **Server-side enforcement**: Cannot bypass expiration client-side
- **Reduces attack window**: Even if URL leaked, limited time exposure

### 4. No Database Lookup Required
- **Stateless verification**: No need to check database for each request
- **Fast validation**: HMAC verification is very fast (microseconds)
- **Scalable**: Works efficiently under high load

## Coordination with Temp Image Cleaner

The signed URL system works together with the background temp image cleaner (`services/temp_image_cleaner.py`) to ensure proper file lifecycle management.

### How They Work Together

**Temp Image Cleaner**:
- Runs every 1 hour in background (via `start_cleanup_scheduler()`)
- Deletes files older than 24 hours based on file modification time (mtime)
- Uses Redis distributed lock to ensure only one worker cleans files
- Integrated into FastAPI lifespan manager

**Signed URL System**:
- URLs expire after 24 hours from generation time (stored in `exp` parameter)
- Signature prevents tampering with filename or expiration
- Both systems use the same 24-hour window for consistency

### Verification Flow (Coordinated)

The endpoint checks in this order to properly coordinate with the cleaner:

```python
# Step 1: Check file existence FIRST
# If cleaner deleted file → 404 Not Found
if not file.exists():
    return 404  # File deleted by cleaner or never existed

# Step 2: Verify URL expiration
# If URL expired but file exists → 403 Forbidden
if URL_expired:
    return 403  # URL expired (file may still exist)

# Step 3: Verify signature
# If signature invalid → 403 Forbidden
if signature_invalid:
    return 403  # Tampered URL
```

### Timing Synchronization

Both systems use the same 24-hour window:

| System | Timing Basis | Window |
|--------|-------------|--------|
| **File Cleanup** | File modification time (mtime) | 24 hours |
| **URL Expiration** | Generation time (stored in URL) | 24 hours |

**Result**: Files and URLs expire at approximately the same time, ensuring consistent behavior.

### Example Timeline

```
T+0h:   File created (mtime = T)
        Signed URL generated (exp = T+24h)
        → File accessible via signed URL

T+1h:   Cleaner runs → File age = 1h → File kept
        URL still valid → File accessible

T+12h:  Cleaner runs → File age = 12h → File kept
        URL still valid → File accessible

T+24h:  URL expires (exp < current_time)
        → 403 Forbidden (URL expired)
        Cleaner hasn't run yet → File still exists

T+25h:  Cleaner runs → File age = 25h → File deleted
        URL already expired → No access anyway
```

### Edge Cases Handled

1. **File Deleted Before URL Expires**
   - Cleaner runs early (e.g., server restart triggers cleanup)
   - File deleted → 404 Not Found
   - URL still valid but file gone → Proper error handling

2. **URL Expires Before File Deleted**
   - URL expires at T+24h → 403 Forbidden
   - File still exists but inaccessible → Proper security
   - Cleaner will delete file on next run (T+25h)

3. **Both Expire Simultaneously**
   - File age = 24h, URL exp = T+24h
   - URL expiration checked first → 403 Forbidden
   - Cleaner deletes file on next run → Consistent behavior

### Benefits of Coordination

1. **Consistent Expiration**: Both systems use 24-hour window
2. **Proper Error Codes**: Distinguishes "file deleted" (404) from "URL expired" (403)
3. **No Race Conditions**: File existence checked before URL validation
4. **Automatic Cleanup**: Cleaner handles file deletion, URL handles access control
5. **Security**: Even if cleaner fails, URL expiration prevents access

### Implementation Details

**File Creation** (`/api/generate_dingtalk`):
```python
# Create file
filename = f"dingtalk_{unique_id}_{timestamp}.png"
save_file(filename, image_data)

# Generate signed URL (24h expiration)
signed_path = generate_signed_url(filename, expiration_seconds=86400)
# Returns: "filename.png?sig=...&exp={timestamp+86400}"
```

**File Access** (`/api/temp_images/{filepath}`):
```python
# Check file exists (cleaner may have deleted it)
if not file.exists():
    return 404  # File deleted

# Verify URL expiration
if URL_expired:
    return 403  # URL expired

# Verify signature
if signature_invalid:
    return 403  # Invalid signature

# Serve file
return FileResponse(file)
```

**File Cleanup** (`services/temp_image_cleaner.py`):
```python
# Runs every 1 hour
for file in temp_images/*.png:
    file_age = current_time - file.mtime
    if file_age > 86400:  # 24 hours
        delete_file(file)  # File deleted
```

## Legacy Support

The implementation includes temporary legacy support for URLs without signatures:

```python
# Legacy URLs (without signature) are allowed temporarily
# But they must:
# 1. File must exist
# 2. File must be less than 24 hours old
# 3. This allows existing URLs to continue working
```

**Migration Path:**
1. New URLs use signed format (with `sig` and `exp` parameters)
2. Legacy URLs still work (backward compatibility)
3. Legacy support can be removed in future version

## Comparison with Alternatives

### Alternative 1: Database Token Storage
**Pros:**
- Can revoke tokens immediately
- Can track access patterns

**Cons:**
- Requires database lookup per request (slower)
- Database overhead for high traffic
- More complex implementation

### Alternative 2: Random Tokens
**Pros:**
- Simple implementation

**Cons:**
- Requires database storage
- Cannot verify without database lookup
- Harder to expire automatically

### HMAC Signing (Current Implementation)
**Pros:**
- ✅ Stateless (no database lookup)
- ✅ Fast verification
- ✅ Automatic expiration
- ✅ Tamper-proof
- ✅ Scalable

**Cons:**
- Cannot revoke individual URLs (but expiration handles this)
- Requires secret key management

## Best Practices

### 1. Secret Key Management
```bash
# Use strong, random secret key (min 32 characters)
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Never commit to git
echo "JWT_SECRET_KEY=..." >> .env
echo ".env" >> .gitignore
```

### 2. Expiration Times
- **Short-lived content**: Use shorter expiration (1-6 hours)
- **Long-lived content**: Use longer expiration (24-48 hours)
- **Current default**: 24 hours (86400 seconds)

### 3. Error Handling
- **Invalid signature**: Return 403 Forbidden (don't reveal why)
- **Expired URL**: Return 403 Forbidden (don't reveal expiration time)
- **Missing signature**: Return 403 Forbidden (for new URLs)

### 4. Monitoring
- Log failed signature verifications (for security monitoring)
- Track expiration patterns (to optimize expiration times)
- Monitor signature generation performance

## Example Usage

### Generating Signed URL
```python
# When creating temp image
filename = "dingtalk_a1b2c3d4_1704067200.png"
signed_path = generate_signed_url(filename, expiration_seconds=86400)
# Returns: "dingtalk_a1b2c3d4_1704067200.png?sig=AbCdEf123...&exp=1704153600"

# Build full URL
image_url = f"https://example.com/api/temp_images/{signed_path}"
```

### Verifying Signed URL
```python
# When accessing temp image
filename = "dingtalk_a1b2c3d4_1704067200.png"
signature = "AbCdEf123..."
expiration = 1704153600

is_valid = verify_signed_url(filename, signature, expiration)
if is_valid:
    # Serve image
else:
    # Return 403 Forbidden
```

## Security Considerations

### What HMAC Signing Protects Against
- ✅ **Unauthorized access**: Without valid signature, cannot access images
- ✅ **URL tampering**: Cannot modify filename or expiration without invalidating signature
- ✅ **Replay attacks**: Expired URLs are rejected
- ✅ **Signature forgery**: Cannot generate valid signature without secret key

### What HMAC Signing Does NOT Protect Against
- ❌ **URL leakage**: If URL is leaked, anyone with URL can access (until expiration)
- ❌ **Man-in-the-middle**: HTTPS should be used to protect URL in transit
- ❌ **Secret key compromise**: If JWT_SECRET_KEY is leaked, all signatures are compromised

### Recommendations
1. **Use HTTPS**: Always serve signed URLs over HTTPS
2. **Strong secret key**: Use cryptographically random key (min 32 bytes)
3. **Key rotation**: Rotate JWT_SECRET_KEY periodically (invalidates all URLs)
4. **Monitor access**: Log signature verification failures
5. **Short expiration**: Use shortest practical expiration time

## Conclusion

HMAC-based URL signing provides a secure, stateless, and scalable way to protect temporary image URLs. By using the same `JWT_SECRET_KEY` as authentication, we maintain consistent security across the application while avoiding additional configuration complexity.

The implementation is production-ready and follows security best practices including constant-time comparison, automatic expiration, and tamper-proof signatures.

