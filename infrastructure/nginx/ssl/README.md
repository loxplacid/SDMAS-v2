# SSL Certificates for SDMAS v2

## Production

Use Let's Encrypt with Certbot to generate certificates:

```bash
# Install certbot
apt-get install certbot

# Generate certificates
certbot certonly --standalone -d sdmas.example.com -d app.sdmas.example.com

# Copy certificates
cp /etc/letsencrypt/live/sdmas.example.com/fullchain.pem infrastructure/nginx/ssl/
cp /etc/letsencrypt/live/sdmas.example.com/privkey.pem infrastructure/nginx/ssl/

# Auto-renewal (certbot adds systemd timer by default)
certbot renew --dry-run
```

## Development (Self-signed)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout infrastructure/nginx/ssl/privkey.pem \
    -out infrastructure/nginx/ssl/fullchain.pem \
    -subj "/CN=localhost"
```
