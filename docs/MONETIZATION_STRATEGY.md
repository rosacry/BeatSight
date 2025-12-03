# BeatSight Monetization Strategy & Implementation Plan

*Created: December 2, 2025*  
*Author: Engineering Analysis*  
*Status: In Progress*

---

## Executive Decision: Hybrid Subscription + Credits Model

After analyzing your cost structure, user psychology, and competitive landscape, I recommend a **simplified 2-tier subscription with universal credit system**.

### Why NOT 3 Tiers (Free/Basic/Pro)?

| Issue | Impact |
|-------|--------|
| **Choice paralysis** | Users hesitate between Basic ($8) and Pro ($15) |
| **Unclear value prop** | "30 songs vs unlimited" is hard to evaluate for new users |
| **Basic tier cannibalization** | Power users pick Basic, hit limit, get frustrated, churn |
| **Complexity** | 3 tiers + credits = 4 things to explain on pricing page |

### Why NOT Pure Pay-Per-Use?

| Issue | Impact |
|-------|--------|
| **Unpredictable revenue** | Hard to forecast MRR |
| **No commitment** | Users never "invest" in the platform |
| **Higher CAC** | Must re-acquire users for each transaction |
| **Price sensitivity** | Every song feels like a purchase decision |

---

## Recommended Model: "Free + Pro + Credits"

### Tier Structure

| Tier | Price | Monthly Quota | Model Quality | Priority |
|------|-------|---------------|---------------|----------|
| **Free** | $0 | 3 songs | V5-Distilled | Low |
| **Pro** | $12/mo ($96/yr) | 50 songs | V5-Full | High |
| **Credits** | $0.35/song | Pay-per-use | V5-Full | Standard |

### Key Design Decisions

#### 1. **Free Tier: 3 Songs (Down from 5)**
- **Rationale:** 5 songs/month is too generous—users can stay free forever
- 3 songs = enough to experience value, not enough to avoid paying
- Creates natural pressure to upgrade after ~2 months of use

#### 2. **Pro Tier: 50 Songs at $12/mo (Not Unlimited)**
- **Rationale:** "Unlimited" attracts abuse and unprofitable power users
- 50 songs/month covers 99% of real drummers (most do 10-20)
- $12 is the "Netflix price point"—feels like a utility, not a luxury
- Yearly: $96 (2 months free) improves cash flow and retention

#### 3. **Credits: $0.35/song (Universal Fallback)**
- Available to ALL users (free and pro)
- Free users: Buy credits instead of subscribing (casual use case)
- Pro users: Buy credits if they exceed 50/month (rare power users)
- **Bulk discounts:** 10 for $3 ($0.30/ea), 25 for $6 ($0.24/ea)

#### 4. **No "Basic" Tier**
- Simplifies pricing page (2 choices, not 3)
- Forces clear decision: "Am I casual (free/credits) or serious (Pro)?"
- Removes the "stuck in the middle" frustration

---

## Revenue Projections

### Unit Economics

| Item | Value |
|------|-------|
| Cost per song (Modal L40S) | ~$0.008 |
| Credit price | $0.35 |
| **Credit margin** | **97.7%** |
| Pro cost (50 songs) | $0.40 |
| Pro price | $12.00 |
| **Pro margin** | **96.7%** |

### Scenario: 10K MAU

| Segment | Users | Revenue | Cost | Profit |
|---------|-------|---------|------|--------|
| Free (3 songs) | 8,500 | $0 | $204 | -$204 |
| Pro subscribers | 1,200 | $14,400 | $384 | $14,016 |
| Credit-only | 300 | $315 | $8 | $307 |
| **Total** | 10,000 | **$14,715** | $596 | **$14,119** |

**Conversion assumptions:** 12% to Pro, 3% credit-only, 85% free

### Why This Beats Alternatives

| Model | 10K MAU Revenue | Issues |
|-------|-----------------|--------|
| Free/Basic/Pro | ~$10,500 | Basic tier cannibalization |
| Free/Pro Unlimited | ~$12,000 | Power user abuse, no overage capture |
| **Free/Pro 50 + Credits** | **~$14,700** | Captures all segments |
| Pure pay-per-use | ~$8,000 | Low commitment, volatile |

---

## Credit System Design

### Credit Packs

| Pack | Credits | Price | Per-Song | Savings |
|------|---------|-------|----------|---------|
| Starter | 5 | $1.75 | $0.35 | 0% |
| Value | 15 | $4.50 | $0.30 | 14% |
| Power | 40 | $10.00 | $0.25 | 29% |

### Credit Properties

1. **Never expire** - Purchased credits are permanent (builds trust)
2. **Subscription-first consumption** - Pro quota used before credits
3. **No auto-charge** - Users explicitly buy credits (avoids surprise bills)
4. **Optional auto-top-up** - Power users can enable $10 auto-buy when balance hits 0

### Purchase Flow

```
User hits quota limit
       │
       ▼
┌─────────────────────────────────────┐
│  "You've used all 3 free songs"     │
│                                     │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ Go Pro $12  │  │ Buy Credits  │  │
│  │ 50 songs/mo │  │ From $1.75   │  │
│  └─────────────┘  └──────────────┘  │
│                                     │
│  [ ] Enable auto-top-up ($10)       │
└─────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Database & Models ✅ IN PROGRESS

- [ ] Create `CreditBalance` model
- [ ] Create `CreditPurchase` model  
- [ ] Create `CreditPack` configuration
- [ ] Add Alembic migration

### Phase 2: Credit Service

- [ ] `CreditService` with balance management
- [ ] Integration with `QuotaService`
- [ ] Credit consumption logic
- [ ] Auto-top-up support

### Phase 3: Stripe Integration

- [ ] Payment Intents for one-time credit purchases
- [ ] Webhook handler for credit fulfillment
- [ ] Update checkout flow

### Phase 4: API Endpoints

- [ ] `GET /api/credits/balance` - Get user's credit balance
- [ ] `GET /api/credits/packs` - List available credit packs
- [ ] `POST /api/credits/purchase` - Create purchase session
- [ ] `GET /api/credits/history` - Purchase history

### Phase 5: Frontend

- [ ] `CreditPurchaseModal` component
- [ ] Update `QuotaDisplay` to show credits
- [ ] Update pricing page with new tiers
- [ ] Credit balance in header/nav

### Phase 6: Quota Integration

- [ ] Modify quota check to include credits
- [ ] Subscription quota → Credits fallback
- [ ] Update AI job creation flow

### Phase 7: Update Existing Pricing

- [ ] Remove Basic tier from pricing.py
- [ ] Update stripe_service.py
- [ ] Update frontend billing types
- [ ] Update pricing page

---

## Files to Create/Modify

### New Files
- `backend/app/models/credits.py`
- `backend/app/services/credits.py`
- `backend/app/api/routes/credits.py`
- `backend/tests/test_credits.py`
- `backend/tests/test_credits_routes.py`
- `frontend/src/api/credits.ts`
- `frontend/src/hooks/useCredits.ts`
- `frontend/src/components/CreditPurchaseModal.tsx`
- `frontend/src/components/CreditBalance.tsx`
- `alembic/versions/xxx_add_credits.py`

### Modified Files
- `backend/app/core/pricing.py` - New tier structure
- `backend/app/services/quota.py` - Credit integration
- `backend/app/services/stripe_service.py` - Payment Intents
- `backend/app/api/routes/billing.py` - Credit endpoints
- `backend/app/models/__init__.py` - Export new models
- `frontend/src/types/billing.ts` - Credit types
- `frontend/src/pages/PricingPage.tsx` - New pricing display
- `frontend/src/components/QuotaDisplay.tsx` - Show credits

---

## Progress Tracking

| Task | Status | Date | Notes |
|------|--------|------|-------|
| Strategy document | ✅ Complete | Dec 2 | This file |
| Credit models | ✅ Complete | Dec 2 | `backend/app/models/credits.py` |
| Credit service | ✅ Complete | Dec 2 | `backend/app/services/credits.py` |
| API endpoints | ✅ Complete | Dec 2 | `backend/app/api/routes/credits.py` |
| Stripe integration | ✅ Complete | Dec 2 | `stripe_service.py` updated |
| Alembic migration | ✅ Complete | Dec 2-3 | `005_credit_system.py` (fixed enum values) |
| Pricing.py update | ✅ Complete | Dec 2 | 2-tier + credits config |
| Quota integration | ✅ Complete | Dec 2-3 | Credit fallback in `quota.py` |
| Models init export | ✅ Complete | Dec 2 | All credit models exported |
| User relationship | ✅ Complete | Dec 2 | `credit_balance` on User |
| Router registration | ✅ Complete | Dec 2-3 | Credits router in `main.py` + `__init__.py` |
| Frontend types | ✅ Complete | Dec 2 | `frontend/src/types/credits.ts` |
| Frontend API client | ✅ Complete | Dec 2 | `frontend/src/api/credits.ts` |
| useCredits hook | ✅ Complete | Dec 2 | `frontend/src/hooks/useCredits.ts` |
| CreditPurchaseModal | ✅ Complete | Dec 2 | Modal for buying packs |
| CreditBalance component | ✅ Complete | Dec 2 | Nav bar display |
| QuotaDisplay update | ✅ Complete | Dec 2 | Shows credits + fallback |
| Billing types update | ✅ Complete | Dec 2 | 2-tier model |
| Backend tests | ✅ Complete | Dec 2-3 | `test_credits.py`, `test_credits_routes.py` |
| PricingPage update | ✅ Complete | Dec 2 | Full redesign with credits section |
| Credit success/cancel pages | ✅ Complete | Dec 2 | `CreditSuccessPage.tsx`, `CreditCancelPage.tsx` |
| App router update | ✅ Complete | Dec 2 | Routes for `/credits/success`, `/credits/cancel` |
| Nav bar credit balance | ✅ Complete | Dec 2 | Desktop + mobile menu integration |
| All backend tests | ✅ Complete | Dec 3 | 1091 tests passing |
| Test alignment (quota) | ✅ Complete | Dec 3 | Updated tests to match new pricing |
| API documentation | ✅ Complete | Dec 2-3 | Credits section in `API_REFERENCE.md` |
| Deployment guide | ✅ Complete | Dec 3 | `CREDIT_SYSTEM_DEPLOYMENT.md` |
| Frontend tests | ⏳ Optional | | Component tests (Vitest ready) |

## Deployment Checklist

Before going live, ensure:

- [ ] Run `alembic upgrade head` to create credit tables
- [ ] Create Stripe Products for credit packs in dashboard
- [ ] Update environment variables with new Stripe price IDs
- [ ] Test checkout flow end-to-end
- [ ] Verify webhook handling for credit purchases
- [ ] Update API documentation
- [ ] Add credit balance to user dashboard

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Should credits expire? | **No** - builds trust, simplifies accounting |
| Minimum purchase? | **$1.75** (5 credits) - low barrier |
| Refunds on credits? | **No** - final sale, clearly stated |
| Can Pro users buy credits? | **Yes** - for exceeding 50/month |
| Show credit balance always? | **Yes** - in nav bar if balance > 0 |

---

*Last updated: December 2, 2025*
