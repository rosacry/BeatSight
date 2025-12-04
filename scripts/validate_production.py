#!/usr/bin/env python3
"""
Production Environment Validator for BeatSight

This script validates that the production environment is properly configured.
Run before deploying to production to catch common misconfiguration issues.

Usage:
    python validate_production.py [--env-file .env]
    
Exit codes:
    0 - All checks passed
    1 - One or more critical checks failed
    2 - Warnings present (non-critical issues)
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.parse import urlparse


class CheckResult(NamedTuple):
    name: str
    passed: bool
    message: str
    severity: str  # "critical", "warning", "info"


def load_env_file(env_path: str) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars
    
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                # Remove quotes if present
                value = value.strip().strip("'\"")
                env_vars[key.strip()] = value
    return env_vars


def check_jwt_secret(env_vars: dict[str, str]) -> CheckResult:
    """Verify JWT_SECRET_KEY is set and not a default/weak value."""
    secret = env_vars.get("JWT_SECRET_KEY", os.environ.get("JWT_SECRET_KEY", ""))
    
    weak_secrets = [
        "secret", "your-secret-key", "change-me", "changeme",
        "development", "dev", "test", "testing", "please-change-me",
        "super-secret-key", "supersecretkey", "jwt-secret",
    ]
    
    if not secret:
        return CheckResult(
            "JWT_SECRET_KEY",
            False,
            "JWT_SECRET_KEY is not set! This is required for authentication.",
            "critical"
        )
    
    if len(secret) < 32:
        return CheckResult(
            "JWT_SECRET_KEY",
            False,
            f"JWT_SECRET_KEY is too short ({len(secret)} chars). Use at least 32 characters.",
            "critical"
        )
    
    if secret.lower() in weak_secrets:
        return CheckResult(
            "JWT_SECRET_KEY",
            False,
            "JWT_SECRET_KEY appears to be a default/weak value. Generate a strong random key.",
            "critical"
        )
    
    return CheckResult(
        "JWT_SECRET_KEY",
        True,
        f"JWT_SECRET_KEY is set ({len(secret)} chars)",
        "info"
    )


def check_cors_origins(env_vars: dict[str, str]) -> CheckResult:
    """Verify CORS origins are production-appropriate."""
    origins = env_vars.get("CORS_ORIGINS", os.environ.get("CORS_ORIGINS", ""))
    
    if not origins:
        return CheckResult(
            "CORS_ORIGINS",
            False,
            "CORS_ORIGINS is not set. This may block legitimate requests.",
            "warning"
        )
    
    origin_list = [o.strip() for o in origins.split(",")]
    
    # Check for wildcard
    if "*" in origin_list:
        return CheckResult(
            "CORS_ORIGINS",
            False,
            "CORS_ORIGINS contains wildcard '*'. This is insecure for production!",
            "critical"
        )
    
    # Check for localhost/development origins
    dev_patterns = ["localhost", "127.0.0.1", "0.0.0.0", ":3000", ":5173", ":8080"]
    dev_origins = [o for o in origin_list if any(p in o for p in dev_patterns)]
    
    if dev_origins and len(origin_list) == len(dev_origins):
        return CheckResult(
            "CORS_ORIGINS",
            False,
            f"CORS_ORIGINS only contains development URLs: {dev_origins}",
            "critical"
        )
    elif dev_origins:
        return CheckResult(
            "CORS_ORIGINS",
            True,
            f"CORS_ORIGINS set but includes dev URLs: {dev_origins}. Consider removing for production.",
            "warning"
        )
    
    return CheckResult(
        "CORS_ORIGINS",
        True,
        f"CORS_ORIGINS configured: {origin_list}",
        "info"
    )


def check_database_url(env_vars: dict[str, str]) -> CheckResult:
    """Verify DATABASE_URL is properly configured for production."""
    db_url = env_vars.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    
    if not db_url:
        return CheckResult(
            "DATABASE_URL",
            False,
            "DATABASE_URL is not set!",
            "critical"
        )
    
    # Check for SQLite in production
    if "sqlite" in db_url.lower():
        return CheckResult(
            "DATABASE_URL",
            False,
            "DATABASE_URL uses SQLite. Use PostgreSQL for production!",
            "critical"
        )
    
    # Check for default passwords
    if any(pwd in db_url.lower() for pwd in ["password", "postgres@", "admin@", "root@"]):
        return CheckResult(
            "DATABASE_URL",
            False,
            "DATABASE_URL appears to use a default password. Use a strong password!",
            "warning"
        )
    
    # Check for SSL mode
    if "postgresql" in db_url and "sslmode=" not in db_url:
        return CheckResult(
            "DATABASE_URL",
            True,
            "DATABASE_URL doesn't specify sslmode. Consider adding sslmode=require.",
            "warning"
        )
    
    return CheckResult(
        "DATABASE_URL",
        True,
        "DATABASE_URL is configured for PostgreSQL",
        "info"
    )


def check_redis_url(env_vars: dict[str, str]) -> CheckResult:
    """Verify REDIS_URL is configured if using caching/queues."""
    redis_url = env_vars.get("REDIS_URL", os.environ.get("REDIS_URL", ""))
    
    if not redis_url:
        return CheckResult(
            "REDIS_URL",
            True,
            "REDIS_URL not set. Rate limiting and caching may be affected.",
            "warning"
        )
    
    # Check for TLS
    if redis_url.startswith("redis://") and not redis_url.startswith("rediss://"):
        return CheckResult(
            "REDIS_URL",
            True,
            "REDIS_URL uses unencrypted connection. Consider using rediss:// for TLS.",
            "warning"
        )
    
    return CheckResult(
        "REDIS_URL",
        True,
        "REDIS_URL is configured",
        "info"
    )


def check_stripe_keys(env_vars: dict[str, str]) -> CheckResult:
    """Verify Stripe keys are production keys, not test keys."""
    secret = env_vars.get("STRIPE_SECRET_KEY", os.environ.get("STRIPE_SECRET_KEY", ""))
    webhook = env_vars.get("STRIPE_WEBHOOK_SECRET", os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    
    if not secret:
        return CheckResult(
            "STRIPE_SECRET_KEY",
            True,
            "STRIPE_SECRET_KEY not set. Payment features will be disabled.",
            "warning"
        )
    
    # Check for test keys
    if secret.startswith("sk_test_"):
        return CheckResult(
            "STRIPE_SECRET_KEY",
            False,
            "STRIPE_SECRET_KEY is a test key! Use sk_live_ for production.",
            "critical"
        )
    
    if not secret.startswith("sk_live_"):
        return CheckResult(
            "STRIPE_SECRET_KEY",
            False,
            "STRIPE_SECRET_KEY doesn't appear to be a valid Stripe key.",
            "critical"
        )
    
    if not webhook:
        return CheckResult(
            "STRIPE_WEBHOOK_SECRET",
            False,
            "STRIPE_WEBHOOK_SECRET not set. Webhook validation will fail!",
            "critical"
        )
    
    if webhook.startswith("whsec_test_"):
        return CheckResult(
            "STRIPE_WEBHOOK_SECRET",
            False,
            "STRIPE_WEBHOOK_SECRET is a test key! Use production webhook secret.",
            "warning"
        )
    
    return CheckResult(
        "STRIPE_KEYS",
        True,
        "Stripe production keys are configured",
        "info"
    )


def check_sentry_dsn(env_vars: dict[str, str]) -> CheckResult:
    """Verify Sentry DSN is configured for error tracking."""
    dsn = env_vars.get("SENTRY_DSN", os.environ.get("SENTRY_DSN", ""))
    
    if not dsn:
        return CheckResult(
            "SENTRY_DSN",
            True,
            "SENTRY_DSN not set. Error tracking will be disabled.",
            "warning"
        )
    
    if not dsn.startswith("https://"):
        return CheckResult(
            "SENTRY_DSN",
            False,
            "SENTRY_DSN doesn't look like a valid Sentry DSN.",
            "warning"
        )
    
    return CheckResult(
        "SENTRY_DSN",
        True,
        "SENTRY_DSN is configured",
        "info"
    )


def check_environment_mode(env_vars: dict[str, str]) -> CheckResult:
    """Verify environment is set to production."""
    env = env_vars.get("ENVIRONMENT", os.environ.get("ENVIRONMENT", ""))
    
    if not env:
        return CheckResult(
            "ENVIRONMENT",
            False,
            "ENVIRONMENT is not set. Set to 'production' for production deployments.",
            "warning"
        )
    
    if env.lower() not in ["production", "prod"]:
        return CheckResult(
            "ENVIRONMENT",
            False,
            f"ENVIRONMENT is '{env}'. Should be 'production' for production deployments.",
            "warning"
        )
    
    return CheckResult(
        "ENVIRONMENT",
        True,
        "ENVIRONMENT is set to production",
        "info"
    )


def check_debug_mode(env_vars: dict[str, str]) -> CheckResult:
    """Verify debug mode is disabled."""
    debug = env_vars.get("DEBUG", os.environ.get("DEBUG", "false"))
    
    if debug.lower() in ["true", "1", "yes"]:
        return CheckResult(
            "DEBUG",
            False,
            "DEBUG is enabled! Disable for production.",
            "critical"
        )
    
    return CheckResult(
        "DEBUG",
        True,
        "DEBUG mode is disabled",
        "info"
    )


def check_storage_config(env_vars: dict[str, str]) -> CheckResult:
    """Verify storage configuration for uploaded files."""
    storage_type = env_vars.get("STORAGE_TYPE", os.environ.get("STORAGE_TYPE", "local"))
    
    if storage_type.lower() == "local":
        return CheckResult(
            "STORAGE_TYPE",
            True,
            "STORAGE_TYPE is 'local'. Consider using S3/R2 for production scalability.",
            "warning"
        )
    
    if storage_type.lower() in ["s3", "r2"]:
        bucket = env_vars.get("S3_BUCKET", os.environ.get("S3_BUCKET", ""))
        if not bucket:
            return CheckResult(
                "S3_BUCKET",
                False,
                "STORAGE_TYPE is cloud but S3_BUCKET is not set!",
                "critical"
            )
    
    return CheckResult(
        "STORAGE_CONFIG",
        True,
        f"Storage configured as {storage_type}",
        "info"
    )


def run_all_checks(env_vars: dict[str, str]) -> list[CheckResult]:
    """Run all validation checks."""
    checks = [
        check_jwt_secret,
        check_cors_origins,
        check_database_url,
        check_redis_url,
        check_stripe_keys,
        check_sentry_dsn,
        check_environment_mode,
        check_debug_mode,
        check_storage_config,
    ]
    
    return [check(env_vars) for check in checks]


def print_results(results: list[CheckResult]) -> int:
    """Print results and return exit code."""
    print("\n" + "=" * 60)
    print("BeatSight Production Environment Validation")
    print("=" * 60 + "\n")
    
    critical_failures = []
    warnings = []
    passed = []
    
    for result in results:
        if result.severity == "critical" and not result.passed:
            critical_failures.append(result)
        elif result.severity == "warning" and not result.passed:
            warnings.append(result)
        elif result.passed:
            passed.append(result)
    
    # Print critical failures
    if critical_failures:
        print("❌ CRITICAL FAILURES:")
        for r in critical_failures:
            print(f"   [{r.name}] {r.message}")
        print()
    
    # Print warnings
    if warnings:
        print("⚠️  WARNINGS:")
        for r in warnings:
            print(f"   [{r.name}] {r.message}")
        print()
    
    # Print passed
    if passed:
        print("✅ PASSED:")
        for r in passed:
            print(f"   [{r.name}] {r.message}")
        print()
    
    # Summary
    print("-" * 60)
    total = len(results)
    print(f"Total: {total} checks | ✅ {len(passed)} passed | ⚠️ {len(warnings)} warnings | ❌ {len(critical_failures)} critical")
    
    if critical_failures:
        print("\n🚫 VALIDATION FAILED - Fix critical issues before deploying!")
        return 1
    elif warnings:
        print("\n⚠️  VALIDATION PASSED WITH WARNINGS - Review before deploying.")
        return 2
    else:
        print("\n✅ ALL CHECKS PASSED - Ready for production!")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate production environment configuration for BeatSight"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)"
    )
    args = parser.parse_args()
    
    # Load environment from file
    env_vars = load_env_file(args.env_file)
    
    # Run all checks
    results = run_all_checks(env_vars)
    
    # Print and return exit code
    exit_code = print_results(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
