# 🚀 BeatSight Production Deployment Guide

This guide walks you through deploying BeatSight to production with:
- **Frontend**: Cloudflare Pages (beatsight.io)
- **Backend API**: Railway (api.beatsight.io)
- **Documentation**: Cloudflare Pages (docs.beatsight.io)
- **AI Pipeline**: Modal.com (already configured)

## Prerequisites

- [Cloudflare account](https://cloudflare.com) (Free tier works)
- [Railway account](https://railway.app) ($5/month hobby plan recommended)
- Domain configured in Cloudflare (beatsight.io ✅)
- GitHub repository access

---

## Step 1: Cloudflare Pages Setup (Frontend)

### 1.1 Create Cloudflare API Token

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Click your profile icon → **My Profile** → **API Tokens**
3. Click **Create Token**
4. Use the **Edit Cloudflare Workers** template, or create custom with:
   - **Permissions**:
     - Account: Cloudflare Pages: Edit
     - Zone: Zone: Read
   - **Account Resources**: Include your account
   - **Zone Resources**: Include beatsight.io
5. Copy the token

### 1.2 Get Cloudflare Account ID

1. Go to your [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select the **beatsight.io** domain
3. On the right sidebar, find **Account ID** (starts with `bfb9d63...`)
4. Copy this ID

### 1.3 Create Pages Project (First time only)

```bash
# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Create the Pages project
cd frontend
npm ci
npm run build
wrangler pages project create beatsight

# Deploy manually first time
wrangler pages deploy dist --project-name=beatsight
```

### 1.4 Configure Custom Domain

1. In Cloudflare Dashboard → Pages → beatsight project
2. Go to **Custom domains** tab
3. Click **Set up a custom domain**
4. Enter `beatsight.io`
5. Cloudflare will auto-configure the DNS

Also add `www.beatsight.io` and set up a redirect rule.

---

## Step 2: Railway Setup (Backend API)

### 2.1 Create Railway Project

1. Go to [Railway](https://railway.app) and sign up/login
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your BeatSight repository
4. Choose **backend** as the root directory

### 2.2 Add PostgreSQL

1. In your Railway project, click **New** → **Database** → **PostgreSQL**
2. Railway auto-generates `DATABASE_URL`
3. The backend will use this automatically

### 2.3 Add Redis

1. Click **New** → **Database** → **Redis**
2. Railway auto-generates `REDIS_URL`
3. The backend will use this automatically

### 2.4 Configure Environment Variables

In Railway → Your backend service → **Variables** tab, add:

```env
# Required
ENVIRONMENT=production
JWT_SECRET_KEY=<generate-a-strong-secret>
DATABASE_DSN=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# Email (SendGrid)
SENDGRID_API_KEY=<your-sendgrid-key>
FROM_EMAIL=noreply@beatsight.io

# Stripe
STRIPE_SECRET_KEY=<your-stripe-key>
STRIPE_WEBHOOK_SECRET=<your-webhook-secret>
STRIPE_PRICE_ID_PRO_MONTHLY=<price-id>
STRIPE_PRICE_ID_PRO_YEARLY=<price-id>

# Modal AI Pipeline
MODAL_WEBHOOK_SECRET=<your-modal-secret>
MODAL_ENABLED=true

# Sentry (optional but recommended)
SENTRY_DSN=<your-sentry-dsn>

# CORS
CORS_ORIGINS=https://beatsight.io,https://www.beatsight.io
```

> **Generate JWT Secret**: `openssl rand -hex 32`

### 2.5 Get Railway Deploy Token

1. Go to Railway → Account Settings → Tokens
2. Create a new token with description "GitHub Actions"
3. Copy the token

### 2.6 Configure Custom Domain

1. In Railway → Your backend service → **Settings** → **Networking**
2. Click **Generate Domain** to get a Railway URL first
3. Then click **Custom Domain** → Enter `api.beatsight.io`
4. Railway will give you a CNAME target

In Cloudflare DNS:
```
Type: CNAME
Name: api
Target: <railway-provided-target>
Proxy: OFF (DNS only - grey cloud)
```

> ⚠️ **Important**: Railway custom domains require DNS-only mode (grey cloud)

---

## Step 3: Cloudflare Pages for Docs

### 3.1 Create Docs Project

```bash
cd docs-site
npm ci
npm run build
wrangler pages project create beatsight-docs
wrangler pages deploy build --project-name=beatsight-docs
```

### 3.2 Configure Custom Domain

1. Pages → beatsight-docs → Custom domains
2. Add `docs.beatsight.io`

---

## Step 4: GitHub Secrets Configuration

Add these secrets to your GitHub repository:

1. Go to GitHub → Settings → Secrets and variables → Actions
2. Add the following **Repository secrets**:

| Secret Name | Description |
|-------------|-------------|
| `CLOUDFLARE_API_TOKEN` | From Step 1.1 |
| `CLOUDFLARE_ACCOUNT_ID` | From Step 1.2 |
| `RAILWAY_TOKEN` | From Step 2.5 |
| `SENTRY_DSN_FRONTEND` | Sentry DSN for frontend (optional) |
| `SENTRY_AUTH_TOKEN` | Sentry auth token for source maps (optional) |

---

## Step 5: DNS Configuration Summary

In Cloudflare DNS for beatsight.io:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | @ | beatsight.pages.dev | Proxied ✅ |
| CNAME | www | beatsight.pages.dev | Proxied ✅ |
| CNAME | api | <railway-target>.railway.app | DNS only ⚪ |
| CNAME | docs | beatsight-docs.pages.dev | Proxied ✅ |
| MX | @ | (Email routing - already set up) | - |
| TXT | @ | (Email verification - already set up) | - |

---

## Step 6: Verify Deployment

### Trigger a Deployment

```bash
git add .
git commit -m "chore: configure production deployment"
git push origin main
```

### Check Deployment Status

1. Go to GitHub → Actions → "Deploy Production" workflow
2. Verify all jobs pass

### Test Endpoints

```bash
# Frontend
curl -I https://beatsight.io

# Backend API
curl https://api.beatsight.io/health

# Docs
curl -I https://docs.beatsight.io
```

---

## Monitoring & Maintenance

### Railway Dashboard
- Monitor CPU, memory, network usage
- View logs in real-time
- Scale up as needed

### Cloudflare Analytics
- View traffic statistics
- Check cache hit rates
- Monitor security events

### Recommended: Set up Alerts

1. **Railway**: Configure Slack/Discord alerts for deploys
2. **Cloudflare**: Set up notification policies for traffic spikes
3. **Sentry**: Configure error alerting (highly recommended)

---

## Troubleshooting

### Backend not starting?
1. Check Railway logs for startup errors
2. Verify `DATABASE_DSN` connects to PostgreSQL
3. Ensure all required env vars are set

### Custom domain not working?
1. Check DNS propagation: `dig api.beatsight.io`
2. Verify SSL is provisioned in Railway/Cloudflare
3. For Railway: Ensure proxy is OFF (grey cloud)

### CORS errors?
1. Verify `CORS_ORIGINS` includes your frontend domain
2. Check browser console for specific errors

---

## Cost Estimates

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Cloudflare Pages | Free | $0 |
| Railway | Hobby | $5 |
| Railway PostgreSQL | Included | $0* |
| Railway Redis | Included | $0* |
| Modal.com | Pay-per-use | ~$5-20** |
| Sentry | Free tier | $0 |
| **Total** | | **~$10-25/month** |

\* Included in Railway's $5 usage-based pricing  
\** Depends on AI processing volume

---

## Next Steps After Deployment

1. ✅ Test user registration and login flow
2. ✅ Test Stripe payment integration
3. ✅ Verify email sending works
4. ✅ Test AI beatmap generation
5. ✅ Monitor error rates in Sentry
6. ✅ Set up uptime monitoring (e.g., BetterStack, UptimeRobot)
