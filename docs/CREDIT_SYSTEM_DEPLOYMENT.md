# Credit System Deployment Guide

This guide covers deploying the BeatSight credit system to production, including Stripe configuration and database migration.

---

## Prerequisites

- [ ] PostgreSQL database accessible
- [ ] Stripe account with API keys
- [ ] Backend deployed and running
- [ ] Frontend deployed

---

## 1. Database Migration

Run the credit system migration to create the required tables:

```bash
# From backend directory
cd backend

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Run migration
alembic upgrade head
```

This creates:
- `credit_balances` - User credit balances
- `credit_purchases` - Purchase records  
- `credit_transactions` - Ledger of all credit movements

### Verify Tables

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE 'credit%';
```

---

## 2. Stripe Configuration

### 2.1 Create Products in Stripe Dashboard

Navigate to [Stripe Dashboard > Products](https://dashboard.stripe.com/products) and create:

#### Starter Pack
- **Name:** BeatSight Starter Pack
- **Description:** 5 credits for AI beatmap generation
- **Price:** $1.75 USD (one-time)
- **Metadata:**
  - `pack_type`: `starter`
  - `credits`: `5`

#### Value Pack  
- **Name:** BeatSight Value Pack
- **Description:** 15 credits - Save 14%
- **Price:** $4.50 USD (one-time)
- **Metadata:**
  - `pack_type`: `value`
  - `credits`: `15`

#### Power Pack
- **Name:** BeatSight Power Pack
- **Description:** 40 credits - Save 29%
- **Price:** $10.00 USD (one-time)
- **Metadata:**
  - `pack_type`: `power`
  - `credits`: `40`

### 2.2 Get Price IDs

After creating products, note the Price IDs (format: `price_xxxxx`).

### 2.3 Configure Environment Variables

Add to your `.env` or deployment configuration:

```bash
# Stripe API Keys
STRIPE_SECRET_KEY=sk_live_xxxxx  # Use sk_test_ for testing
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Credit Pack Price IDs
STRIPE_PRICE_CREDITS_STARTER=price_xxxxx
STRIPE_PRICE_CREDITS_VALUE=price_xxxxx
STRIPE_PRICE_CREDITS_POWER=price_xxxxx

# Redirect URLs
STRIPE_SUCCESS_URL=https://yourdomain.com/credits/success?session_id={CHECKOUT_SESSION_ID}
STRIPE_CANCEL_URL=https://yourdomain.com/credits/cancel
```

### 2.4 Configure Webhook

1. Go to [Stripe Dashboard > Webhooks](https://dashboard.stripe.com/webhooks)
2. Add endpoint: `https://api.yourdomain.com/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. Copy the signing secret to `STRIPE_WEBHOOK_SECRET`

---

## 3. Backend Configuration

### Update pricing.py (if needed)

Verify `backend/app/core/pricing.py` has correct tier configuration:

```python
PRICING_TIERS = {
    SubscriptionTier.FREE: TierConfig(
        name="Free",
        monthly_limit=3,  # 3 songs/month
        model_version="v5-distilled",
        # ...
    ),
    SubscriptionTier.PRO: TierConfig(
        name="Pro", 
        monthly_limit=50,  # 50 songs/month
        model_version="v5-full",
        price_monthly_cents=1200,  # $12/month
        # ...
    ),
}
```

### Verify Credit Service

Test the credit service is working:

```bash
# Test credit packs endpoint
curl https://api.yourdomain.com/api/credits/packs

# Expected: JSON array of 3 packs
```

---

## 4. Frontend Configuration

### Environment Variables

```bash
# .env.production
VITE_API_URL=https://api.yourdomain.com
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
```

### Build and Deploy

```bash
cd frontend
npm run build
# Deploy dist/ folder
```

---

## 5. Testing Checklist

### Pre-Launch Testing

- [ ] **Credit packs display correctly** on pricing page
- [ ] **Purchase flow works** (use Stripe test mode)
  - Test card: `4242 4242 4242 4242`
- [ ] **Success page** shows updated balance after purchase
- [ ] **Cancel page** returns user gracefully
- [ ] **Credit balance** displays in navigation
- [ ] **Quota exhaustion** correctly triggers credit consumption
- [ ] **Webhook** processes completed payments

### Test Scenarios

1. **New user with credits:**
   - Register → Buy credits → Use credits for generation
   
2. **Pro user exceeding quota:**
   - Pro subscription at 50/50 → Buy credits → Generate with credits

3. **Free user at limit:**
   - Free user at 3/3 → Shown upgrade/credits option → Buy credits → Generate

4. **Auto top-up:**
   - Enable auto top-up → Deplete balance → Verify auto-purchase triggers

---

## 6. Monitoring

### Key Metrics to Track

```sql
-- Daily credit purchases
SELECT DATE(created_at) as date, 
       COUNT(*) as purchases,
       SUM(price_cents)/100.0 as revenue
FROM credit_purchases 
WHERE is_fulfilled = true
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Credit consumption rate
SELECT DATE(created_at) as date,
       COUNT(*) as consumptions,
       SUM(ABS(amount)) as credits_used
FROM credit_transactions
WHERE transaction_type = 'consumption'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Users with credits
SELECT COUNT(DISTINCT user_id) as users_with_credits
FROM credit_balances
WHERE purchased_credits + bonus_credits > 0;
```

### Alerts to Configure

1. **Webhook failures** - Monitor Stripe webhook endpoint errors
2. **Payment failures** - Track failed payment intents
3. **Credit fulfillment delays** - Alert if purchases aren't fulfilled within 5 minutes

---

## 7. Rollback Plan

If issues arise:

### Database Rollback

```bash
# Revert credit migration
alembic downgrade -1
```

### Feature Flag (Optional)

Add to settings if needed:

```python
# backend/app/core/settings.py
CREDITS_ENABLED: bool = True  # Toggle credit system
```

---

## 8. Post-Launch

### Week 1
- Monitor conversion rates
- Check for failed webhooks
- Review user feedback

### Week 2-4
- Analyze credit pack popularity
- Consider adjusting pricing if needed
- Plan promotional credits feature

---

## Support

For issues:
- Check Stripe Dashboard for payment status
- Review `credit_transactions` table for audit trail
- Check application logs for errors

Common issues:
- **Credits not appearing:** Check webhook configuration
- **Purchase stuck pending:** Verify Stripe webhook endpoint
- **Balance mismatch:** Reconcile with `credit_transactions` table
