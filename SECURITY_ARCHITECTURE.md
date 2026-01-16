# Security Architecture (Reference)

This document describes the security-related modules that exist in the codebase.
It is a technical reference and **not** a guarantee of complete coverage.

## Data Flow (High Level)

```
Input (Confluence / file / manual)
  -> Validation + sanitization
  -> State persistence
  -> Export (Excel/CSV)
```

## Implemented Modules

1. Prompt Injection Defense
   - `src/utils/security.py`
   - Detects common prompt injection patterns and wraps unsafe input.

2. SSRF Protection (Confluence)
   - `src/utils/ssrf_protection.py`
   - Enforces HTTPS, domain allowlist, blocks private IPs.

3. Rate Limiting
   - `src/utils/rate_limiter.py`
   - Token bucket limiter; currently used for Confluence API calls.

4. Input Validation
   - `src/utils/input_validation.py`
   - Length, size, and path validation for requirements and files.

5. State Integrity
   - `src/utils/state_integrity.py`
   - HMAC signatures, schema validation, and backup/restore.

6. Security Logging
   - `src/utils/security_logging.py`
   - Redacts sensitive data in logs and records security events.

7. Excel Formula Injection Protection
   - `src/generators/exporters.py`
   - Sanitizes cell values starting with formula prefixes.

If you need these to be enforced globally, integrate them in `main.py`
and `src/state/state_manager.py` with explicit checks and failures.
