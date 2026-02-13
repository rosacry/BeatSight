# Stripe Payment Setup Guide

Complete guide for setting up Stripe payments for BeatSight.

## Overview

BeatSight uses Stripe for:
- **Subscriptions**: Pro tier ($12/month or $96/year)
- **One-time purchases**: Credit packs ($3.50 - $70)
- **Customer portal**: Self-service subscription management

## Prerequisites

1. Stripe account (https://stripe.com)
2. Backend environment access
3. Domain verified for webhooks (for production)

---

## Step 1: Create Stripe Account

1. Go to https://dashboard.stripe.com/register
2. Complete account setup and verification
3. For testing, use **Test Mode** (toggle in top-right)

---

## Step 2: Get API Keys

1. Go to **Developers** → **API Keys**
2. Copy these keys:

```
STRIPE_SECRET_KEY=sk_test_...      # Secret key (keep private!)
STRIPE_PUBLISHABLE_KEY=pk_test_... # Publishable key (safe for frontend)
```

> ⚠️ **Never commit secret keys to git!** Use environment variables or secrets management.

---

## Step 3: Create Products & Prices

### Subscription Plans

Create in **Products** → **Add Product**:

#### Pro Monthly
- **Name**: BeatSight Pro (Monthly)
- **Description**: 50 AI transcriptions/month, priority processing
- **Price**: $12.00 USD / month (recurring)
- **Price ID**: Copy this → `STRIPE_PRO_MONTHLY_PRICE_ID`

#### Pro Yearly
- **Name**: BeatSight Pro (Yearly)
- **Description**: 50 AI transcriptions/month, priority processing
- **Price**: $96.00 USD / year (recurring)
- **Price ID**: Copy this → `STRIPE_PRO_YEARLY_PRICE_ID`

### Credit Packs (Optional - if using credit system)

Create one-time prices for credit packs:

| Pack Name | Credits | Price | Create As |
|-----------|---------|-------|-----------|
| Starter | 10 | $3.50 | One-time |
| Value | 30 | $9.00 | One-time |
| Bundle | 100 | $25.00 | One-time |
| Studio | 250 | $50.00 | One-time |

---

## Step 4: Configure Webhook Endpoint

1. Go to **Developers** → **Webhooks**
2. Click **Add endpoint**
3. Enter your endpoint URL:
   - **Development**: Use [Stripe CLI](#local-development-with-stripe-cli) or ngrok
   - **Production**: `https://api.beatsight.io/api/billing/webhook`
4. Select events to listen for:

```
checkout.session.completed
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
invoice.payment_succeeded
invoice.payment_failed
```

5. Copy the **Signing secret** → `STRIPE_WEBHOOK_SECRET`

---

## Step 5: Configure Environment Variables

Add to your `.env` file:

```env
# Stripe API Keys
STRIPE_SECRET_KEY=sk_test_51ABC...
STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...

# Webhook Secret
STRIPE_WEBHOOK_SECRET=whsec_...

# Price IDs
STRIPE_PRO_MONTHLY_PRICE_ID=price_1ABC...
STRIPE_PRO_YEARLY_PRICE_ID=price_1DEF...

# Optional: Basic tier (if enabled)
# STRIPE_BASIC_MONTHLY_PRICE_ID=price_...
# STRIPE_BASIC_YEARLY_PRICE_ID=price_...
```

For **Kubernetes secrets**, add to your sealed secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: stripe-secrets
  namespace: beatsight
type: Opaque
stringData:
  STRIPE_SECRET_KEY: "sk_live_..."
  STRIPE_WEBHOOK_SECRET: "whsec_..."
  STRIPE_PRO_MONTHLY_PRICE_ID: "price_..."
  STRIPE_PRO_YEARLY_PRICE_ID: "price_..."
```

---

## Step 6: Configure Customer Portal

1. Go to **Settings** → **Billing** → **Customer portal**
2. Enable features:
   - ✅ Update payment method
   - ✅ View invoice history
   - ✅ Cancel subscription
   - ✅ Switch plans (if multiple tiers)
3. Set **Return URL**: `https://beatsight.io/settings/billing`
4. Customize branding to match BeatSight

---

## Local Development with Stripe CLI

For testing webhooks locally:

### Install Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows (scoop)
scoop install stripe

# Or download from https://stripe.com/docs/stripe-cli
```

### Forward Webhooks to Local Server

```bash
# Login to Stripe
stripe login

# Forward webhooks to your local backend
stripe listen --forward-to localhost:8000/api/billing/webhook

# You'll see output like:
# > Ready! Your webhook signing secret is whsec_abc123...
# Use this as STRIPE_WEBHOOK_SECRET for local testing
```

### Test Webhook Events

```bash
# Trigger test events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.created
stripe trigger invoice.payment_succeeded
```

---

## Testing Checklist

### Test Cards

Use these test card numbers:

| Scenario | Card Number | CVC | Expiry |
|----------|-------------|-----|--------|
| Success | 4242 4242 4242 4242 | Any 3 digits | Any future date |
| Declined | 4000 0000 0000 0002 | Any | Any future |
| Requires Auth | 4000 0025 0000 3155 | Any | Any future |

### Verify These Flows

- [ ] **Checkout Flow**
  - User clicks upgrade
  - Redirected to Stripe Checkout
  - Payment succeeds
  - Redirected back with active subscription

- [ ] **Subscription Status**
  - `/api/billing/subscription` returns correct plan
  - AI quota reflects Pro tier limits

- [ ] **Customer Portal**
  - User can access portal
  - Can update payment method
  - Can cancel subscription

- [ ] **Webhook Processing**
  - Subscription created/updated events processed
  - User's plan updates in database
  - Idempotency prevents duplicate processing

- [ ] **Credit Purchases** (if enabled)
  - Credit pack checkout works
  - Credits added to balance after payment
  - Balance reflected in UI

---

## Going Live (Production)

### Pre-launch Checklist

1. [ ] Switch from Test to Live mode in Stripe dashboard
2. [ ] Update all environment variables with live keys
3. [ ] Create live webhook endpoint for production URL
4. [ ] Re-create products and prices in live mode (or use Stripe CLI to copy)
5. [ ] Test a real transaction with a real card
6. [ ] Set up Stripe Radar for fraud protection
7. [ ] Configure tax settings if required (Stripe Tax)

### Update Secrets in Production

```bash
# Update Kubernetes secrets
kubectl create secret generic stripe-secrets \
  --from-literal=STRIPE_SECRET_KEY=sk_live_... \
  --from-literal=STRIPE_WEBHOOK_SECRET=whsec_... \
  --namespace=beatsight \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Monitor

- Set up Stripe webhook failure alerts
- Monitor failed payments in Stripe dashboard
- Review Radar rules for fraud patterns

---

## Troubleshooting

### Webhook signature verification failed

- Ensure `STRIPE_WEBHOOK_SECRET` matches the webhook endpoint's signing secret
- Check that you're using the raw request body (not parsed JSON)
- Verify clock sync between servers

### Checkout session not creating

- Verify price IDs exist and are active
- Check Stripe API key is valid
- Look for error details in backend logs

### Subscription not updating after payment

- Check webhook endpoint is receiving events
- Verify webhook events are being processed (check logs)
- Ensure database connection is working

### Customer portal returns error

- Verify user has a Stripe customer ID
- Check portal configuration in Stripe dashboard
- Ensure return URL is valid

---

## API Reference

### Create Checkout Session
```bash
POST /api/billing/checkout
Authorization: Bearer <token>

{
  "plan": "pro_monthly"
}
```

### Get Subscription Status
```bash
GET /api/billing/subscription
Authorization: Bearer <token>
```

### Create Portal Session
```bash
POST /api/billing/portal
Authorization: Bearer <token>
```

### Purchase Credits
```bash
POST /api/credits/purchase
Authorization: Bearer <token>

{
  "pack_id": "value"
}
```

---

## Support

- Stripe Documentation: https://stripe.com/docs
- Stripe Discord: https://stripe.com/discord
- BeatSight Issues: https://github.com/rosacry/BeatSight/issues
