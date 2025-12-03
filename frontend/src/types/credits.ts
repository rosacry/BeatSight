/**
 * Credit system type definitions.
 * Must match backend app/models/credits.py and app/services/credits.py
 */

export type CreditPackType = 'starter' | 'standard' | 'bulk' | 'mega'
export type CreditTransactionType = 'purchase' | 'consumption' | 'refund' | 'bonus' | 'expiration' | 'auto_topup'

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

// Credit pack definitions (must match backend/app/services/credits.py)
export const CREDIT_PACKS: CreditPack[] = [
    {
        type: 'starter',
        name: 'Starter Pack',
        credits: 5,
        price_cents: 175,
        price_display: '$1.75',
        per_credit_cents: 35,
        savings_percent: 0,
    },
    {
        type: 'standard',
        name: 'Standard Pack',
        credits: 15,
        price_cents: 450,
        price_display: '$4.50',
        per_credit_cents: 30,
        savings_percent: 14,
    },
    {
        type: 'bulk',
        name: 'Bulk Pack',
        credits: 40,
        price_cents: 1000,
        price_display: '$10.00',
        per_credit_cents: 25,
        savings_percent: 29,
    },
    {
        type: 'mega',
        name: 'Mega Pack',
        credits: 100,
        price_cents: 2000,
        price_display: '$20.00',
        per_credit_cents: 20,
        savings_percent: 43,
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
