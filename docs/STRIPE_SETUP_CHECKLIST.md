# BeatSight Stripe Setup Checklist

## Quick Reference

Your billing system is **fully implemented** with:
- ✅ Subscription management (Free → Pro upgrades)
- ✅ One-time credit purchases
- ✅ Customer portal for self-service
- ✅ Webhook handling with idempotency
- ✅ Auto top-up for credits

---

## What You Need To Do

### 1. Create Stripe Account (~5 min)
- [ ] Go to https://stripe.com and sign up
- [ ] Complete email verification
- [ ] Enable **Test Mode** (toggle in dashboard top-right)

### 2. Get API Keys (~2 min)
- [ ] Dashboard → Developers → API Keys
- [ ] Copy **Publishable key** (pk_test_...)
- [ ] Copy **Secret key** (sk_test_...)

### 3. Create Products (~10 min)

You can either:

**Option A: Use the setup script (recommended)**
```bash
cd backend
export STRIPE_SECRET_KEY=sk_test_YOUR_KEY
poetry run python -m scripts.setup_stripe
```

**Option B: Create manually in Stripe Dashboard**

Create these products at https://dashboard.stripe.com/test/products:

| Product | Price | Billing | Copy Price ID |
|---------|-------|---------|---------------|
| BeatSight Pro (Monthly) | $12.00 | Monthly | `STRIPE_PRO_MONTHLY_PRICE_ID` |
| BeatSight Pro (Yearly) | $96.00 | Yearly | `STRIPE_PRO_YEARLY_PRICE_ID` |
| Credits - Starter (10) | $3.50 | One-time | (optional) |
| Credits - Value (30) | $9.00 | One-time | (optional) |
| Credits - Bundle (100) | $25.00 | One-time | (optional) |
| Credits - Studio (250) | $50.00 | One-time | (optional) |

### 4. Set Up Webhook (~5 min)
- [ ] Dashboard → Developers → Webhooks → Add endpoint
- [ ] Endpoint URL: `https://api.beatsight.io/api/billing/webhook`
  - For local dev: Use Stripe CLI (see below)
- [ ] Select events:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- [ ] Copy **Signing secret** (whsec_...)

### 5. Update Environment Variables (~2 min)

Add to your `.env` file:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Price IDs (from step 3)
STRIPE_PRO_MONTHLY_PRICE_ID=price_xxx
STRIPE_PRO_YEARLY_PRICE_ID=price_xxx
```

### 6. Configure Customer Portal (~3 min)
- [ ] Dashboard → Settings → Billing → Customer portal
- [ ] Enable: Update payment method, Cancel subscription, View invoices
- [ ] Set return URL: `https://beatsight.io/settings/billing`
- [ ] Save

---

## Local Development Testing

### Install Stripe CLI
```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows (with scoop)
scoop install stripe
```

### Forward Webhooks Locally
```bash
# Login first
stripe login

# Forward to local backend
stripe listen --forward-to localhost:8000/api/billing/webhook

# You'll get a webhook secret - use this for local dev
```

### Test Cards
| Scenario | Card Number |
|----------|-------------|
| ✅ Success | 4242 4242 4242 4242 |
| ❌ Declined | 4000 0000 0000 0002 |
| 🔐 Auth Required | 4000 0025 0000 3155 |

Use any future expiry date and any 3-digit CVC.

---

## Verification Checklist

After setup, test these flows:

- [ ] **Pricing Page**: Shows plans at `/pricing`
- [ ] **Upgrade Flow**: Click upgrade → Stripe checkout → Payment → Redirect back
- [ ] **Subscription Status**: `/api/billing/subscription` returns correct plan
- [ ] **Customer Portal**: Can access and manage subscription
- [ ] **Webhook Processing**: Check server logs for webhook events
- [ ] **Credit Purchase**: Buy credits → Balance updates

---

## Production Deployment

When ready to go live:

1. [ ] Switch Stripe dashboard to **Live mode**
2. [ ] Create products/prices in live mode (or copy from test)
3. [ ] Update webhook endpoint to production URL
4. [ ] Replace all `sk_test_` with `sk_live_` keys
5. [ ] Update Kubernetes secrets
6. [ ] Test with real card (small amount)

---

## Files Modified

- `backend/app/api/routes/health.py` - Added Stripe health check
- `backend/scripts/setup_stripe.py` - New product setup script
- `docs/STRIPE_SETUP.md` - Full documentation

## Helpful Commands

```bash
# Check if Stripe is configured
curl https://api.beatsight.io/api/billing/config

# View health status (includes Stripe)
curl https://api.beatsight.io/health/detailed

# List existing Stripe products
cd backend && poetry run python -m scripts.setup_stripe --list
```

---

## Support

- Stripe Docs: https://stripe.com/docs
- Stripe CLI: https://stripe.com/docs/stripe-cli
- Dashboard: https://dashboard.stripe.com
