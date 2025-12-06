/**
 * Credit system type definitions.
 * Must match backend app/models/credits.py and app/services/credits.py
 *
 * Credit packs (as of June 2025):
 * - Starter: 15 credits @ $5 ($0.33/credit)
 * - Value: 30 credits @ $10 ($0.33/credit)
 * - Power: 75 credits @ $25 ($0.33/credit, best value)
 */

export type CreditPackType = 'starter' | 'value' | 'power'
export type CreditTransactionType = 'purchase' | 'consumption' | 'refund' | 'bonus' | 'subscription_grant' | 'expiry'

export interface CreditBalance {
    balance: number
    lifetime_purchased: number
    lifetime_consumed: number
    auto_topup_enabled: boolean
    auto_topup_threshold: number | null
    auto_topup_pack: CreditPackType | null
}

export interface CreditPack {
    type: CreditPackType
    name: string
    credits: number
    price_cents: number
    price_display: string
    per_credit_cents: number
    savings_percent: number
}

export interface CreditPurchase {
    id: string
    pack_type: CreditPackType
    credits_amount: number
    price_cents: number
    status: 'pending' | 'completed' | 'failed'
    created_at: string
    completed_at: string | null
}

export interface CreditTransaction {
    id: string
    transaction_type: CreditTransactionType
    amount: number
    balance_before: number
    balance_after: number
    description: string | null
    created_at: string
}

export interface CreditCheckoutResponse {
    session_id: string
    checkout_url: string
}

export interface AutoTopupConfig {
    enabled: boolean
    threshold: number
    pack_type: CreditPackType
}

/**
 * Credit pack definitions.
 * These MUST match the backend configuration in backend/app/services/credits.py
 * and the Stripe products/prices.
 *
 * Stripe Price IDs (LIVE):
 * - starter: price_1SbCCh013gobhhgaqvNvxsUh
 * - value: price_1SbCD1013gobhhgaRr7Eqy2M
 * - power: price_1SbCDF013gobhhgaENw5U7Tp
 */
export const CREDIT_PACKS: CreditPack[] = [
    {
        type: 'starter',
        name: 'Starter Pack',
        credits: 15,
        price_cents: 500,
        price_display: '$5',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
    {
        type: 'value',
        name: 'Value Pack',
        credits: 30,
        price_cents: 1000,
        price_display: '$10',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
    {
        type: 'power',
        name: 'Power Pack',
        credits: 75,
        price_cents: 2500,
        price_display: '$25',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
]

// Helper functions
export function formatCredits(credits: number): string {
    return `${credits} credit${credits !== 1 ? 's' : ''}`
}

export function formatCreditPrice(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`
}

export function getPackByType(type: CreditPackType): CreditPack | undefined {
    return CREDIT_PACKS.find(pack => pack.type === type)
}
