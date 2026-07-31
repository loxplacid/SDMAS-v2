# Secrets Management — SDMAS v2

## ⚠️ IMPORTANT

This directory is gitignored. **Never commit actual secrets.**

## Setup

Generate required secrets for production:

```bash
# Database password
openssl rand -base64 32 > secrets/db_password.txt

# JWT signing secret
openssl rand -base64 64 > secrets/jwt_secret.txt

# Razorpay API keys (copy from Razorpay dashboard)
echo "rzp_live_xxxxxxxx" > secrets/razorpay_key_id.txt
echo "xxxxxxxxxxxxxxxx" > secrets/razorpay_key_secret.txt
```

## Secret Rotation

Rotate secrets periodically:
- JWT_SECRET: every 90 days (existing tokens will be invalidated)
- DB_PASSWORD: every 180 days (requires application restart)
- Razorpay keys: only on compromise

## Alternatives

For production, consider:
1. **Docker Secrets** (used in docker-compose.production.yml)
2. **HashiCorp Vault** (via VaultBackend in app/core/secrets.py)
3. **Cloud provider secret managers** (AWS Secrets Manager, GCP Secret Manager)
4. **CI/CD pipeline secrets** (GitHub Actions secrets, GitLab CI variables)
