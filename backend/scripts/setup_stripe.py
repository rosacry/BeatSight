#!/usr/bin/env python3
"""
Stripe Product Setup Script

Creates all required products and prices in your Stripe account.
Run this once during initial setup or when adding new products.

Usage:
    # Set your Stripe secret key first
    export STRIPE_SECRET_KEY=sk_test_...
    
    # Run the script
    python -m scripts.setup_stripe

    # Or with Poetry
    cd backend && poetry run python -m scripts.setup_stripe
"""

import os
import sys
from dataclasses import dataclass

import stripe


@dataclass
class ProductConfig:
    """Configuration for a Stripe product."""
    name: str
    description: str
    prices: list[dict]


# Products to create
PRODUCTS = [
    ProductConfig(
        name="BeatSight Pro (Monthly)",
        description="AI-powered drum transcription - 50 songs/month, priority processing, V5 Full model",
        prices=[
            {
                "nickname": "Pro Monthly",
                "unit_amount": 1200,  # $12.00
                "currency": "usd",
                "recurring": {"interval": "month"},
            }
        ],
    ),
    ProductConfig(
        name="BeatSight Pro (Yearly)",
        description="AI-powered drum transcription - 50 songs/month, priority processing, V5 Full model",
        prices=[
            {
                "nickname": "Pro Yearly",
                "unit_amount": 9600,  # $96.00 (2 months free)
                "currency": "usd",
                "recurring": {"interval": "year"},
            }
        ],
    ),
    ProductConfig(
        name="BeatSight Credits - Starter Pack",
        description="10 AI transcription credits",
        prices=[
            {
                "nickname": "Starter (10 credits)",
                "unit_amount": 350,  # $3.50
                "currency": "usd",
            }
        ],
    ),
    ProductConfig(
        name="BeatSight Credits - Value Pack",
        description="30 AI transcription credits (15% savings)",
        prices=[
            {
                "nickname": "Value (30 credits)",
                "unit_amount": 900,  # $9.00
                "currency": "usd",
            }
        ],
    ),
    ProductConfig(
        name="BeatSight Credits - Bundle Pack",
        description="100 AI transcription credits (29% savings)",
        prices=[
            {
                "nickname": "Bundle (100 credits)",
                "unit_amount": 2500,  # $25.00
                "currency": "usd",
            }
        ],
    ),
    ProductConfig(
        name="BeatSight Credits - Studio Pack",
        description="250 AI transcription credits (43% savings)",
        prices=[
            {
                "nickname": "Studio (250 credits)",
                "unit_amount": 5000,  # $50.00
                "currency": "usd",
            }
        ],
    ),
]


def create_products_and_prices():
    """Create all products and prices in Stripe."""
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    
    if not api_key:
        print("❌ Error: STRIPE_SECRET_KEY environment variable not set")
        print("\nSet it with:")
        print("  export STRIPE_SECRET_KEY=sk_test_...")
        sys.exit(1)
    
    stripe.api_key = api_key
    
    # Check if we're in test or live mode
    mode = "LIVE" if api_key.startswith("sk_live_") else "TEST"
    print(f"\n🔑 Running in {mode} mode\n")
    
    if mode == "LIVE":
        confirm = input("⚠️  You're in LIVE mode. Continue? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    created_prices = {}
    
    for product_config in PRODUCTS:
        print(f"📦 Creating product: {product_config.name}")
        
        # Create product
        product = stripe.Product.create(
            name=product_config.name,
            description=product_config.description,
            metadata={
                "created_by": "beatsight_setup_script",
            },
        )
        print(f"   ✅ Product created: {product.id}")
        
        # Create prices for this product
        for price_config in product_config.prices:
            price = stripe.Price.create(
                product=product.id,
                **price_config,
                metadata={
                    "created_by": "beatsight_setup_script",
                },
            )
            print(f"   💰 Price created: {price.id} ({price_config['nickname']})")
            created_prices[price_config["nickname"]] = price.id
    
    print("\n" + "=" * 60)
    print("✅ All products and prices created successfully!")
    print("=" * 60)
    print("\n📋 Add these to your .env file:\n")
    
    # Print environment variables
    env_mapping = {
        "Pro Monthly": "STRIPE_PRO_MONTHLY_PRICE_ID",
        "Pro Yearly": "STRIPE_PRO_YEARLY_PRICE_ID",
        "Starter (10 credits)": "STRIPE_CREDIT_STARTER_PRICE_ID",
        "Value (30 credits)": "STRIPE_CREDIT_VALUE_PRICE_ID",
        "Bundle (100 credits)": "STRIPE_CREDIT_BUNDLE_PRICE_ID",
        "Studio (250 credits)": "STRIPE_CREDIT_STUDIO_PRICE_ID",
    }
    
    for nickname, env_var in env_mapping.items():
        if nickname in created_prices:
            print(f"{env_var}={created_prices[nickname]}")
    
    print("\n🔗 View in Stripe Dashboard:")
    if mode == "TEST":
        print("   https://dashboard.stripe.com/test/products")
    else:
        print("   https://dashboard.stripe.com/products")


def list_existing_products():
    """List existing products and prices."""
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    
    if not api_key:
        print("❌ Error: STRIPE_SECRET_KEY not set")
        sys.exit(1)
    
    stripe.api_key = api_key
    
    print("\n📦 Existing Products:\n")
    
    products = stripe.Product.list(active=True, limit=100)
    
    for product in products.data:
        print(f"  {product.name}")
        print(f"    ID: {product.id}")
        
        prices = stripe.Price.list(product=product.id, active=True)
        for price in prices.data:
            amount = price.unit_amount / 100 if price.unit_amount else 0
            interval = f"/{price.recurring.interval}" if price.recurring else " (one-time)"
            print(f"    💰 ${amount:.2f}{interval} - {price.id}")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stripe setup script for BeatSight")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing products instead of creating new ones",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_existing_products()
    else:
        create_products_and_prices()
