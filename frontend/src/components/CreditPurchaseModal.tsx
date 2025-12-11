/**
 * Credit Purchase Modal - allows users to buy credit packs.
 */

import { useState } from 'react'
import { useCreditPacks, usePurchaseCredits } from '@/hooks/useCredits'
import { CREDIT_PACKS, formatCredits, type CreditPackType } from '@/types/credits'

interface CreditPurchaseModalProps {
    isOpen: boolean
    onClose: () => void
    context?: 'quota_exceeded' | 'voluntary' | 'upgrade_prompt'
}

export function CreditPurchaseModal({
    isOpen,
    onClose,
    context = 'voluntary',
}: CreditPurchaseModalProps) {
    const [selectedPack, setSelectedPack] = useState<CreditPackType>('starter')
    const { data: packs, isLoading: loadingPacks } = useCreditPacks()
    const purchaseMutation = usePurchaseCredits()

    if (!isOpen) return null

    const displayPacks = packs ?? CREDIT_PACKS // Use local fallback if API fails

    const handlePurchase = () => {
        purchaseMutation.mutate({
            packType: selectedPack,
            successUrl: `${window.location.origin}/credits/success`,
            cancelUrl: `${window.location.origin}/credits/cancel`,
        })
    }

    const contextMessages = {
        quota_exceeded: {
            title: 'Out of Monthly Quota',
            subtitle: 'Buy credits to continue.',
        },
        voluntary: {
            title: 'Buy Credits',
            subtitle: 'Extra generations, anytime.',
        },
        upgrade_prompt: {
            title: 'Need More Songs?',
            subtitle: 'Buy credits or upgrade to Pro.',
        },
    }

    const { title, subtitle } = contextMessages[context]

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <div className="bg-dark-500 rounded-xl border border-white/10 w-full max-w-lg shadow-2xl">
                {/* Header */}
                <div className="p-6 border-b border-white/10">
                    <div className="flex justify-between items-start">
                        <div>
                            <h2 className="text-xl font-bold text-white">{title}</h2>
                            <p className="text-gray-400 text-sm mt-1">{subtitle}</p>
                        </div>
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-white transition-colors"
                            aria-label="Close"
                        >
                            <svg
                                className="w-6 h-6"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M6 18L18 6M6 6l12 12"
                                />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Pack Options */}
                <div className="p-6 space-y-3">
                    {loadingPacks ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
                        </div>
                    ) : (
                        displayPacks.map((pack) => (
                            <button
                                key={pack.type}
                                onClick={() => setSelectedPack(pack.type)}
                                className={`w-full p-4 rounded-lg border transition-all text-left ${selectedPack === pack.type
                                    ? 'border-primary-500 bg-primary-500/10'
                                    : 'border-white/10 bg-dark-400/50 hover:border-gray-600'
                                    }`}
                            >
                                <div className="flex justify-between items-center">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-white">{pack.name}</span>
                                            {pack.savings_percent > 0 && (
                                                <span className="px-2 py-0.5 text-xs font-medium bg-green-500/20 text-green-400 rounded-full">
                                                    Save {pack.savings_percent}%
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-400 mt-1">
                                            {formatCredits(pack.credits)} • ${(pack.per_credit_cents / 100).toFixed(2)}/song
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <span className="text-xl font-bold text-white">
                                            {pack.price_display}
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 space-y-4">
                    {/* Purchase button */}
                    <button
                        onClick={handlePurchase}
                        disabled={purchaseMutation.isPending}
                        className="w-full py-3 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-dark-300 
                       text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                        {purchaseMutation.isPending ? (
                            <>
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                                Processing...
                            </>
                        ) : (
                            <>
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                        d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                                </svg>
                                Buy{' '}
                                {displayPacks.find((p) => p.type === selectedPack)?.price_display ?? '$4.50'}
                            </>
                        )}
                    </button>

                    {/* Pro upgrade CTA */}
                    {context !== 'voluntary' && (
                        <div className="text-center">
                            <p className="text-sm text-gray-400">
                                Or{' '}
                                <a href="/pricing" className="text-primary-400 hover:text-primary-300 underline">
                                    upgrade to Pro
                                </a>{' '}
                                for 50 songs/month at $12/mo
                            </p>
                        </div>
                    )}

                    {/* Trust badges */}
                    <div className="flex items-center justify-center gap-4 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                            </svg>
                            Secure checkout
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            Credits never expire
                        </span>
                    </div>
                </div>
            </div>
        </div>
    )
}
