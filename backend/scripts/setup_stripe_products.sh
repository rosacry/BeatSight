#!/bin/bash
# =============================================================================
# BeatSight Stripe Setup Script
# =============================================================================
# This script creates all the products and prices in Stripe needed for BeatSight.
# Run this once in your Stripe test mode, then again in live mode for production.
#
# Prerequisites:
#   - Stripe CLI installed: brew install stripe/stripe-cli/stripe
#   - Logged in: stripe login
#
# Usage:
#   chmod +x setup_stripe_products.sh
#   ./setup_stripe_products.sh
#
# After running, copy the price IDs to your Railway environment variables.
# =============================================================================

set -e

echo "🎵 BeatSight Stripe Product Setup"
echo "================================="
echo ""

# Check if Stripe CLI is installed
if ! command -v stripe &> /dev/null; then
    echo "❌ Stripe CLI not found. Install it first:"
    echo "   brew install stripe/stripe-cli/stripe"
    echo "   OR"
    echo "   Download from: https://stripe.com/docs/stripe-cli"
    exit 1
fi

# Check if logged in
if ! stripe config --list &> /dev/null; then
    echo "❌ Not logged in to Stripe. Run: stripe login"
    exit 1
fi

echo "Creating products and prices..."
echo ""

# =============================================================================
# Pro Subscription Plan
# =============================================================================
echo "📦 Creating Pro subscription product..."

PRO_PRODUCT=$(stripe products create \
    --name="BeatSight Pro" \
    --description="50 AI drum transcriptions per month with highest accuracy V5 model" \
    --metadata[tier]="pro" \
    --format=json | jq -r '.id')

echo "   Product ID: $PRO_PRODUCT"

# Pro Monthly - $12/month
PRO_MONTHLY=$(stripe prices create \
    --product="$PRO_PRODUCT" \
    --currency=usd \
    --unit-amount=1200 \
    --recurring[interval]=month \
    --metadata[plan]="pro_monthly" \
    --format=json | jq -r '.id')

echo "   ✓ Pro Monthly: $PRO_MONTHLY ($12/month)"

# Pro Yearly - $96/year ($8/month, 2 months free)
PRO_YEARLY=$(stripe prices create \
    --product="$PRO_PRODUCT" \
    --currency=usd \
    --unit-amount=9600 \
    --recurring[interval]=year \
    --metadata[plan]="pro_yearly" \
    --format=json | jq -r '.id')

echo "   ✓ Pro Yearly: $PRO_YEARLY ($96/year)"
echo ""

# =============================================================================
# Credit Packs (One-time purchases)
# =============================================================================
echo "💳 Creating credit pack products..."

# Starter Pack - 15 credits @ $5.25 ($0.35/credit)
CREDITS_15_PRODUCT=$(stripe products create \
    --name="BeatSight Credits - Starter Pack" \
    --description="15 AI transcription credits" \
    --metadata[type]="credits" \
    --metadata[credits]="15" \
    --format=json | jq -r '.id')

CREDITS_15=$(stripe prices create \
    --product="$CREDITS_15_PRODUCT" \
    --currency=usd \
    --unit-amount=525 \
    --format=json | jq -r '.id')

echo "   ✓ 15 Credits: $CREDITS_15 ($5.25)"

# Value Pack - 30 credits @ $9.00 ($0.30/credit, 14% savings)
CREDITS_30_PRODUCT=$(stripe products create \
    --name="BeatSight Credits - Value Pack" \
    --description="30 AI transcription credits - Best value!" \
    --metadata[type]="credits" \
    --metadata[credits]="30" \
    --format=json | jq -r '.id')

CREDITS_30=$(stripe prices create \
    --product="$CREDITS_30_PRODUCT" \
    --currency=usd \
    --unit-amount=900 \
    --format=json | jq -r '.id')

echo "   ✓ 30 Credits: $CREDITS_30 ($9.00)"

# Studio Pack - 75 credits @ $18.75 ($0.25/credit, 29% savings)
CREDITS_75_PRODUCT=$(stripe products create \
    --name="BeatSight Credits - Studio Pack" \
    --description="75 AI transcription credits - Maximum savings!" \
    --metadata[type]="credits" \
    --metadata[credits]="75" \
    --format=json | jq -r '.id')

CREDITS_75=$(stripe prices create \
    --product="$CREDITS_75_PRODUCT" \
    --currency=usd \
    --unit-amount=1875 \
    --format=json | jq -r '.id')

echo "   ✓ 75 Credits: $CREDITS_75 ($18.75)"
echo ""

# =============================================================================
# Summary - Copy these to Railway!
# =============================================================================
echo "=============================================="
echo "🎉 Setup Complete! Add these to Railway:"
echo "=============================================="
echo ""
echo "STRIPE_PRO_MONTHLY_PRICE_ID=$PRO_MONTHLY"
echo "STRIPE_PRO_YEARLY_PRICE_ID=$PRO_YEARLY"
echo "STRIPE_CREDITS_15_PRICE_ID=$CREDITS_15"
echo "STRIPE_CREDITS_30_PRICE_ID=$CREDITS_30"
echo "STRIPE_CREDITS_75_PRICE_ID=$CREDITS_75"
echo ""
echo "Also add from Stripe Dashboard (https://dashboard.stripe.com/apikeys):"
echo "STRIPE_SECRET_KEY=sk_test_... or sk_live_..."
echo "STRIPE_PUBLISHABLE_KEY=pk_test_... or pk_live_..."
echo ""
echo "For webhook secret, create a webhook endpoint:"
echo "  URL: https://api.beatsight.io/api/billing/webhook"
echo "  Events: checkout.session.completed, customer.subscription.*, invoice.*"
echo "STRIPE_WEBHOOK_SECRET=whsec_..."
echo ""
