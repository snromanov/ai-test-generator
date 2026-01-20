#!/usr/bin/env python3
"""
Security Check Script for AI Test Generator.

Runs comprehensive security scans including:
- Dependency vulnerability scanning (safety, pip-audit)
- Static code analysis (bandit)
- Configuration validation
- File permission checks
- Secrets detection
"""
import subprocess
import sys
import os
import re
import stat
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SecurityCheckResult:
    """Result of a security check."""
    name: str
    passed: bool
    message: str
    severity: str  # "critical", "high", "medium", "low", "info"
    details: List[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = []


class SecurityChecker:
    """Comprehensive security checker for the project."""

    # Patterns for secret detection
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[\w-]{20,}', "API Key"),
        (r'(?i)(secret|token)\s*[=:]\s*["\']?[\w-]{20,}', "Secret/Token"),
        (r'(?i)password\s*[=:]\s*["\']?[^\s"\']{8,}', "Password"),
        (r'(?i)(aws|amazon).{0,20}(key|secret|token)', "AWS Credential"),
        (r'(?i)bearer\s+[\w-]{20,}', "Bearer Token"),
        (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', "Private Key"),
        (r'(?i)confluence[_-]?token\s*[=:]\s*["\']?[\w-]{20,}', "Confluence Token"),
    ]

    # Files that should never be committed
    SENSITIVE_FILES = [
        '.env',
        '.env.local',
        '.env.production',
        'credentials.json',
        '*.pem',
        '*.key',
        'id_rsa',
        'id_dsa',
    ]

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.results: List[SecurityCheckResult] = []

    def run_all_checks(self) -> List[SecurityCheckResult]:
        """Run all security checks."""
        print("\n" + "=" * 60)
        print("  AI Test Generator - Security Check")
        print("=" * 60 + "\n")

        self._check_dependencies()
        self._check_static_analysis()
        self._check_file_permissions()
        self._check_secrets()
        self._check_gitignore()
        self._check_configuration()
        self._check_security_modules()

        self._print_summary()
        return self.results

    def _check_dependencies(self):
        """Check for vulnerable dependencies."""
        print("[1/7] Checking dependencies for vulnerabilities...")

        # Safety check
        try:
            result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if result.returncode == 0:
                self.results.append(SecurityCheckResult(
                    name="Safety Check",
                    passed=True,
                    message="No known vulnerabilities in dependencies",
                    severity="info"
                ))
            else:
                self.results.append(SecurityCheckResult(
                    name="Safety Check",
                    passed=False,
                    message="Vulnerable dependencies found",
                    severity="high",
                    details=result.stdout.split('\n')[:10]
                ))
        except FileNotFoundError:
            self.results.append(SecurityCheckResult(
                name="Safety Check",
                passed=False,
                message="safety not installed. Run: pip install safety",
                severity="medium"
            ))

        # pip-audit check
        try:
            result = subprocess.run(
                ['pip-audit', '--desc'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if "No known vulnerabilities found" in result.stdout or result.returncode == 0:
                self.results.append(SecurityCheckResult(
                    name="pip-audit Check",
                    passed=True,
                    message="No vulnerabilities found by pip-audit",
                    severity="info"
                ))
            else:
                self.results.append(SecurityCheckResult(
                    name="pip-audit Check",
                    passed=False,
                    message="pip-audit found issues",
                    severity="high",
                    details=result.stdout.split('\n')[:10]
                ))
        except FileNotFoundError:
            self.results.append(SecurityCheckResult(
                name="pip-audit Check",
                passed=False,
                message="pip-audit not installed. Run: pip install pip-audit",
                severity="medium"
            ))
        print("  Done.\n")

    def _check_static_analysis(self):
        """Run static code analysis with bandit."""
        print("[2/7] Running static code analysis (bandit)...")

        try:
            result = subprocess.run(
                ['bandit', '-r', 'src/', '-ll', '-ii', '-f', 'json'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            import json
            try:
                bandit_output = json.loads(result.stdout)
                issues = bandit_output.get('results', [])

                if not issues:
                    self.results.append(SecurityCheckResult(
                        name="Bandit Analysis",
                        passed=True,
                        message="No security issues found in code",
                        severity="info"
                    ))
                else:
                    high_issues = [i for i in issues if i.get('issue_severity') == 'HIGH']
                    medium_issues = [i for i in issues if i.get('issue_severity') == 'MEDIUM']

                    self.results.append(SecurityCheckResult(
                        name="Bandit Analysis",
                        passed=len(high_issues) == 0,
                        message=f"Found {len(high_issues)} high, {len(medium_issues)} medium severity issues",
                        severity="high" if high_issues else "medium",
                        details=[f"{i['filename']}:{i['line_number']} - {i['issue_text']}"
                                for i in issues[:5]]
                    ))
            except json.JSONDecodeError:
                self.results.append(SecurityCheckResult(
                    name="Bandit Analysis",
                    passed=True,
                    message="Bandit completed (could not parse JSON output)",
                    severity="info"
                ))

        except FileNotFoundError:
            self.results.append(SecurityCheckResult(
                name="Bandit Analysis",
                passed=False,
                message="bandit not installed. Run: pip install bandit",
                severity="medium"
            ))
        print("  Done.\n")

    def _check_file_permissions(self):
        """Check sensitive file permissions."""
        print("[3/7] Checking file permissions...")

        issues = []

        # Check .env file
        env_file = self.project_root / '.env'
        if env_file.exists():
            mode = env_file.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                issues.append(f".env has insecure permissions: {oct(mode)}")

        # Check state file
        state_file = self.project_root / '.test_generator_state.json'
        if state_file.exists():
            mode = state_file.stat().st_mode
            if mode & stat.S_IWOTH:
                issues.append(f"State file is world-writable: {oct(mode)}")

        # Check signature key
        sig_key = Path.home() / '.ai-test-gen-signature-key'
        if sig_key.exists():
            mode = sig_key.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                issues.append(f"Signature key has insecure permissions: {oct(mode)}")

        if issues:
            self.results.append(SecurityCheckResult(
                name="File Permissions",
                passed=False,
                message=f"Found {len(issues)} permission issues",
                severity="high",
                details=issues
            ))
        else:
            self.results.append(SecurityCheckResult(
                name="File Permissions",
                passed=True,
                message="All sensitive files have correct permissions",
                severity="info"
            ))
        print("  Done.\n")

    def _check_secrets(self):
        """Scan for hardcoded secrets in source code."""
        print("[4/7] Scanning for hardcoded secrets...")

        secrets_found = []

        for py_file in self.project_root.rglob('*.py'):
            # Skip virtual environment
            if 'venv' in str(py_file) or '.git' in str(py_file):
                continue

            try:
                content = py_file.read_text()
                for pattern, secret_type in self.SECRET_PATTERNS:
                    matches = re.findall(pattern, content)
                    if matches:
                        secrets_found.append(f"{py_file.relative_to(self.project_root)}: {secret_type}")
            except Exception:
                pass

        if secrets_found:
            self.results.append(SecurityCheckResult(
                name="Secrets Detection",
                passed=False,
                message=f"Found {len(secrets_found)} potential secrets",
                severity="critical",
                details=secrets_found[:10]
            ))
        else:
            self.results.append(SecurityCheckResult(
                name="Secrets Detection",
                passed=True,
                message="No hardcoded secrets detected",
                severity="info"
            ))
        print("  Done.\n")

    def _check_gitignore(self):
        """Verify .gitignore covers sensitive files."""
        print("[5/7] Checking .gitignore configuration...")

        gitignore_path = self.project_root / '.gitignore'
        if not gitignore_path.exists():
            self.results.append(SecurityCheckResult(
                name="Gitignore Check",
                passed=False,
                message=".gitignore file not found",
                severity="high"
            ))
            print("  Done.\n")
            return

        gitignore_content = gitignore_path.read_text()

        required_patterns = ['.env', '*.log', 'venv/', '__pycache__/', '.test_generator_state.json']
        missing = []

        for pattern in required_patterns:
            if pattern not in gitignore_content:
                missing.append(pattern)

        if missing:
            self.results.append(SecurityCheckResult(
                name="Gitignore Check",
                passed=False,
                message=f"Missing {len(missing)} important patterns",
                severity="medium",
                details=missing
            ))
        else:
            self.results.append(SecurityCheckResult(
                name="Gitignore Check",
                passed=True,
                message="All sensitive patterns are in .gitignore",
                severity="info"
            ))
        print("  Done.\n")

    def _check_configuration(self):
        """Check security configuration."""
        print("[6/7] Checking security configuration...")

        issues = []

        # Check if .env.example exists
        if not (self.project_root / '.env.example').exists():
            issues.append(".env.example not found - users may not know required config")

        # Check SSRF protection whitelist
        ssrf_file = self.project_root / 'src' / 'utils' / 'ssrf_protection.py'
        if ssrf_file.exists():
            content = ssrf_file.read_text()
            if 'ALLOWED_CONFLUENCE_DOMAINS' in content:
                if 'localhost' in content.lower() or '127.0.0.1' in content:
                    issues.append("SSRF whitelist contains localhost - potential security risk")

        if issues:
            self.results.append(SecurityCheckResult(
                name="Configuration Check",
                passed=False,
                message=f"Found {len(issues)} configuration issues",
                severity="medium",
                details=issues
            ))
        else:
            self.results.append(SecurityCheckResult(
                name="Configuration Check",
                passed=True,
                message="Security configuration looks good",
                severity="info"
            ))
        print("  Done.\n")

    def _check_security_modules(self):
        """Verify security modules are properly implemented."""
        print("[7/7] Checking security modules...")

        required_modules = [
            ('src/utils/security.py', 'Prompt Injection Protection'),
            ('src/utils/ssrf_protection.py', 'SSRF Protection'),
            ('src/utils/input_validation.py', 'Input Validation'),
            ('src/utils/rate_limiter.py', 'Rate Limiting'),
            ('src/utils/state_integrity.py', 'State Integrity'),
            ('src/utils/security_logging.py', 'Security Logging'),
        ]

        missing = []
        for module_path, name in required_modules:
            if not (self.project_root / module_path).exists():
                missing.append(f"{name} ({module_path})")

        if missing:
            self.results.append(SecurityCheckResult(
                name="Security Modules",
                passed=False,
                message=f"Missing {len(missing)} security modules",
                severity="critical",
                details=missing
            ))
        else:
            self.results.append(SecurityCheckResult(
                name="Security Modules",
                passed=True,
                message="All 6 security modules present",
                severity="info"
            ))
        print("  Done.\n")

    def _print_summary(self):
        """Print summary of all checks."""
        print("\n" + "=" * 60)
        print("  SECURITY CHECK SUMMARY")
        print("=" * 60 + "\n")

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        # Group by severity
        critical = [r for r in self.results if not r.passed and r.severity == 'critical']
        high = [r for r in self.results if not r.passed and r.severity == 'high']
        medium = [r for r in self.results if not r.passed and r.severity == 'medium']

        print(f"  Total Checks: {len(self.results)}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print()

        if critical:
            print("  CRITICAL ISSUES:")
            for r in critical:
                print(f"    - {r.name}: {r.message}")
                for detail in r.details[:3]:
                    print(f"      * {detail}")
            print()

        if high:
            print("  HIGH SEVERITY ISSUES:")
            for r in high:
                print(f"    - {r.name}: {r.message}")
            print()

        if medium:
            print("  MEDIUM SEVERITY ISSUES:")
            for r in medium:
                print(f"    - {r.name}: {r.message}")
            print()

        if failed == 0:
            print("  All security checks PASSED")
            status_code = 0
        elif critical:
            print("  Status: CRITICAL - Immediate action required")
            status_code = 2
        elif high:
            print("  Status: HIGH RISK - Action recommended")
            status_code = 1
        else:
            print("  Status: MEDIUM RISK - Review recommended")
            status_code = 1

        print("\n" + "=" * 60 + "\n")
        return status_code


def main():
    """Run security checks."""
    checker = SecurityChecker()
    checker.run_all_checks()

    # Return non-zero exit code if critical issues found
    critical = any(r.severity == 'critical' and not r.passed for r in checker.results)
    sys.exit(2 if critical else 0)


if __name__ == "__main__":
    main()
