# Security Policy

## Reporting a Vulnerability

Please do **not** open a public issue for security bugs.

Report privately with:
- краткое описание проблемы
- шаги воспроизведения
- ожидаемое/фактическое поведение
- потенциальное влияние

If you are using GitHub, prefer GitHub Security Advisories.
Otherwise, contact the maintainers via a private channel listed in the project
README or repository settings.

## Supported Versions

We currently support the latest `main` branch.
Older tags/releases may not receive security fixes.

## Security Features (Implemented)

The project includes the following implemented protections:
- Prompt injection detection + sanitization in `src/utils/security.py`.
- SSRF protections for Confluence URLs in `src/utils/ssrf_protection.py`.
- Rate limiting for Confluence API calls in `src/utils/rate_limiter.py`.
- Input size/path validation in `src/utils/input_validation.py`.
- State integrity checks + HMAC signing in `src/utils/state_integrity.py`.
- Formula injection protection for Excel export in `src/generators/exporters.py`.
- Security event logging and log sanitization in `src/utils/security_logging.py`.

For architectural details, see `SECURITY_ARCHITECTURE.md`.
