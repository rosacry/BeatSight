/**
 * Pricing Page Component.
 * Displays subscription plans (2-tier: Free + Pro) and credit packs.
 * See docs/MONETIZATION_STRATEGY.md for pricing rationale.
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { PRICING_PLANS, type SubscriptionPlan } from '@/types/billing'
import { CREDIT_PACKS, formatCredits } from '@/types/credits'
import { useSubscription, useUpgradeSubscription, useStripeConfig } from '@/hooks/useBilling'
import { usePurchaseCredits, useCreditBalance } from '@/hooks/useCredits'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/components/Toast'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import {
    tabContentVariants as unifiedTabContentVariants
} from '@/components/ui/UnifiedTransitions'

export function PricingPage() {
    useDocumentTitle('pricing')
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
    const [showCredits, setShowCredits] = useState(false)

    // Track if we're collapsing (vs expanding) for scroll preservation
    const isCollapsingRef = useRef<boolean>(false)
    const savedScrollRef = useRef<number>(0)
    const creditsSectionRef = useRef<HTMLDivElement>(null)
    const animationFrameRef = useRef<number | null>(null)

    const { isAuthenticated } = useAuthStore()
    const { data: subscription } = useSubscription()
    const { data: creditBalance } = useCreditBalance()
    const { data: stripeConfig } = useStripeConfig()
    const upgradeMutation = useUpgradeSubscription()
    const purchaseCreditsMutation = usePurchaseCredits()

    // Cleanup animation frame on unmount
    useEffect(() => {
        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current)
            }
        }
    }, [])

    // Handle credits toggle with scroll preservation
    const handleCreditsToggle = useCallback(() => {
        if (showCredits) {
            // About to collapse - mark it and save scroll position
            isCollapsingRef.current = true
            savedScrollRef.current = window.scrollY

            // Use RAF loop to aggressively maintain scroll position during collapse
            const maintainScroll = () => {
                if (isCollapsingRef.current) {
                    window.scrollTo(0, savedScrollRef.current)
                    animationFrameRef.current = requestAnimationFrame(maintainScroll)
                }
            }
            animationFrameRef.current = requestAnimationFrame(maintainScroll)
        } else {
            isCollapsingRef.current = false
        }
        setShowCredits(prev => !prev)
    }, [showCredits])

    // Show message if cancelled checkout
    const cancelled = searchParams.get('cancelled')
    if (cancelled) {
        toast.info('Checkout cancelled. No charges were made.')
    }

    const handleSelectPlan = async (planId: SubscriptionPlan) => {
        if (!isAuthenticated()) {
            navigate(`/login?redirect=/pricing&plan=${planId}`)
            return
        }

        if (planId === 'free') {
            toast.info('You already have access to the free tier!')
            return
        }

        if (!stripeConfig?.is_configured) {
            toast.error('Payment unavailable. Try again later.')
            return
        }

        const actualPlan: SubscriptionPlan =
            planId === 'pro_monthly' && billingCycle === 'yearly'
                ? 'pro_yearly'
                : planId

        upgradeMutation.mutate(actualPlan)
    }

    const handleBuyCredits = (packType: string) => {
        if (!isAuthenticated()) {
            navigate(`/login?redirect=/pricing`)
            return
        }

        if (!stripeConfig?.is_configured) {
            toast.error('Payment unavailable. Try again later.')
            return
        }

        purchaseCreditsMutation.mutate({
            packType: packType as 'starter' | 'value' | 'power',
            successUrl: `${window.location.origin}/credits/success`,
            cancelUrl: `${window.location.origin}/pricing?cancelled=true`,
        })
    }

    const currentPlan = subscription?.plan || 'free'

    return (
        <div className="min-h-screen bg-dark-500 py-8 sm:py-16 px-4">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="text-center mb-8 sm:mb-12">
                    <h1 className="text-2xl sm:text-4xl font-bold text-white mb-3 sm:mb-4">
                        Pricing
                    </h1>
                    <p className="text-base sm:text-xl text-gray-400 max-w-2xl mx-auto">
                        Pro for regular use, or pay-per-song with credits.
                    </p>
                    <p className="text-xs sm:text-sm text-primary-400 mt-3 sm:mt-4">
                        Playing, manual mapping, and verification always free.
                    </p>
                </div>

                {/* Billing Toggle */}
                <div className="flex justify-center mb-8 sm:mb-12">
                    <div className="bg-dark-400 p-1 rounded-lg flex">
                        <button
                            onClick={() => setBillingCycle('monthly')}
                            className={`px-4 sm:px-6 py-2 rounded-md text-sm font-medium transition-colors ${billingCycle === 'monthly'
                                ? 'bg-primary-500 text-white'
                                : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            Monthly
                        </button>
                        <button
                            onClick={() => setBillingCycle('yearly')}
                            className={`px-4 sm:px-6 py-2 rounded-md text-sm font-medium transition-colors ${billingCycle === 'yearly'
                                ? 'bg-primary-500 text-white'
                                : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            Yearly
                            <span className="ml-1 sm:ml-2 text-xs text-green-400">Save 33%</span>
                        </button>
                    </div>
                </div>

                {/* Pricing Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8 max-w-4xl mx-auto mb-12 sm:mb-16">
                    {PRICING_PLANS.map((plan) => {
                        const isCurrentPlan = currentPlan === plan.id ||
                            (currentPlan === 'pro_yearly' && plan.id === 'pro_monthly')
                        const price = billingCycle === 'yearly' && plan.priceYearly
                            ? plan.priceYearly
                            : plan.priceMonthly

                        return (
                            <div
                                key={plan.id}
                                className={`relative rounded-xl p-8 ${plan.highlighted
                                    ? 'bg-dark-400 border-2 border-primary-500'
                                    : 'bg-dark-400 border border-dark-300'
                                    }`}
                            >
                                {plan.highlighted && (
                                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                                        <span className="bg-primary-500 text-white text-sm font-medium px-4 py-1 rounded-full">
                                            Best Value
                                        </span>
                                    </div>
                                )}

                                <h3 className="text-2xl font-bold text-white mb-2">
                                    {plan.name}
                                </h3>
                                <p className="text-gray-400 mb-4">
                                    {plan.description}
                                </p>

                                {/* Quota badge */}
                                {plan.monthlyQuota && (
                                    <div className="inline-block px-3 py-1 bg-dark-500 rounded-full text-sm text-gray-300 mb-4">
                                        {plan.monthlyQuota} songs/month
                                    </div>
                                )}

                                <div className="mb-6">
                                    <span className="text-4xl font-bold text-white">
                                        ${price}
                                    </span>
                                    {price > 0 && (
                                        <span className="text-gray-400">/month</span>
                                    )}
                                    {billingCycle === 'yearly' && plan.priceYearly && (
                                        <p className="text-sm text-gray-500 mt-1">
                                            Billed annually (${plan.priceYearly * 12}/year)
                                        </p>
                                    )}
                                </div>

                                <ul className="space-y-4 mb-8">
                                    {plan.features.map((feature, idx) => (
                                        <li key={idx} className="flex items-start gap-3">
                                            <svg
                                                className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5"
                                                fill="none"
                                                stroke="currentColor"
                                                viewBox="0 0 24 24"
                                            >
                                                <path
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeWidth={2}
                                                    d="M5 13l4 4L19 7"
                                                />
                                            </svg>
                                            <span className="text-gray-300 break-words">{feature}</span>
                                        </li>
                                    ))}
                                </ul>

                                <button
                                    onClick={() => handleSelectPlan(plan.id)}
                                    disabled={isCurrentPlan || upgradeMutation.isPending}
                                    className={`w-full py-3 rounded-lg font-medium transition-colors ${isCurrentPlan
                                        ? 'bg-dark-500 text-gray-400 cursor-not-allowed'
                                        : plan.highlighted
                                            ? 'bg-primary-500 hover:bg-primary-600 text-white'
                                            : 'bg-dark-500 hover:bg-dark-300 text-white'
                                        }`}
                                >
                                    {isCurrentPlan
                                        ? 'Current Plan'
                                        : upgradeMutation.isPending
                                            ? 'Redirecting...'
                                            : plan.cta}
                                </button>
                            </div>
                        )
                    })}
                </div>

                {/* Credits Section */}
                <div className="max-w-4xl mx-auto mt-16">
                    <div className="text-center mb-8">
                        <motion.button
                            onClick={handleCreditsToggle}
                            className="group inline-flex items-center gap-2 px-6 py-3 rounded-xl
                                     bg-dark-400 hover:bg-dark-300
                                     border border-dark-300 hover:border-primary-500/50
                                     text-gray-300 hover:text-white
                                     transition-all duration-200"
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            <span className="text-lg font-medium">
                                Or pay per song with Credits
                            </span>
                            <motion.svg
                                animate={{ rotate: showCredits ? 180 : 0 }}
                                transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                                className="w-5 h-5 text-primary-400"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </motion.svg>
                        </motion.button>
                        <p className="text-gray-500 text-sm mt-3">
                            Credits never expire • Use anytime • Available to all users
                        </p>
                        {creditBalance && creditBalance.total_credits > 0 && (
                            <p className="text-primary-400 text-sm mt-1">
                                You have {creditBalance.total_credits} credits
                            </p>
                        )}
                    </div>

                    <div ref={creditsSectionRef} style={{ overflowAnchor: 'none' }}>
                        <AnimatePresence initial={false}>
                            {showCredits && (
                                <motion.div
                                    key="credits-container"
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{
                                        height: 'auto',
                                        opacity: 1,
                                        transition: {
                                            height: { duration: 0.35, ease: [0.33, 1, 0.68, 1] },
                                            opacity: { duration: 0.25, delay: 0.08 }
                                        }
                                    }}
                                    exit={{
                                        height: 0,
                                        opacity: 0,
                                        transition: {
                                            opacity: { duration: 0.15, ease: 'easeOut' },
                                            height: { duration: 0.3, ease: [0.33, 1, 0.68, 1], delay: 0.05 }
                                        }
                                    }}
                                    className="overflow-hidden"
                                    style={{
                                        willChange: 'height, opacity',
                                        overflowAnchor: 'none',
                                        contain: 'layout'
                                    }}
                                    onAnimationComplete={() => {
                                        // Stop the RAF loop and reset state
                                        if (animationFrameRef.current) {
                                            cancelAnimationFrame(animationFrameRef.current)
                                            animationFrameRef.current = null
                                        }
                                        isCollapsingRef.current = false
                                    }}
                                >
                                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-3xl mx-auto pb-4 pt-6">
                                        {CREDIT_PACKS.map((pack) => (
                                            <div
                                                key={pack.type}
                                                className="bg-dark-400 border border-dark-300 rounded-xl p-6 hover:border-primary-500/50 transition-colors duration-200"
                                            >
                                                <div className="flex justify-between items-start mb-3">
                                                    <h4 className="font-semibold text-white">{pack.name}</h4>
                                                    {pack.savings_percent > 0 && (
                                                        <span className="px-2 py-0.5 text-xs font-medium bg-green-500/20 text-green-400 rounded-full">
                                                            -{pack.savings_percent}%
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-3xl font-bold text-white mb-1">
                                                    {pack.price_display}
                                                </p>
                                                <p className="text-sm text-gray-400 mb-4">
                                                    {formatCredits(pack.credits)} • ${(pack.per_credit_cents / 100).toFixed(2)}/song
                                                </p>
                                                <button
                                                    onClick={() => handleBuyCredits(pack.type)}
                                                    disabled={purchaseCreditsMutation.isPending}
                                                    className="w-full py-2 bg-dark-500 hover:bg-dark-300 text-white text-sm font-medium rounded-lg transition-colors duration-200 disabled:opacity-50"
                                                >
                                                    {purchaseCreditsMutation.isPending ? 'Processing...' : 'Buy Now'}
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>

                {/* FAQ Section */}
                <div className="mt-20 max-w-3xl mx-auto">
                    <h2 className="text-2xl font-bold text-white text-center mb-8">
                        Frequently Asked Questions
                    </h2>
                    <div className="space-y-6">
                        <FaqItem
                            question="What happens when I run out of monthly songs?"
                            answer="You can purchase credits to continue generating beatmaps. Credits work for both Free and Pro users and never expire. Just buy what you need!"
                        />
                        <FaqItem
                            question="What's the difference between Free and Pro?"
                            answer="Free gives you 3 songs/month with our V5-Distilled model. Pro gives you 50 songs/month with our premium V5-Full model, plus priority processing and cloud sync."
                        />
                        <FaqItem
                            question="Do credits expire?"
                            answer="No! Credits never expire. Buy them once and use them whenever you need extra songs beyond your monthly quota."
                        />
                        <FaqItem
                            question="Can Pro users buy credits too?"
                            answer="Yes! If you're a power user who needs more than 50 songs/month, you can purchase credits for the extra generations."
                        />
                        <FaqItem
                            question="Can I cancel anytime?"
                            answer="Yes! Cancel anytime from your account settings. You'll keep Pro access until the end of your billing period. Your credits remain yours forever."
                        />
                        <FaqItem
                            question="What payment methods do you accept?"
                            answer="We accept all major credit cards (Visa, Mastercard, American Express) through our secure payment processor, Stripe."
                        />
                    </div>
                </div>

                {/* Trust badges */}
                <div className="mt-16 text-center">
                    <div className="flex flex-wrap justify-center gap-8 text-gray-500 text-sm">
                        <div className="flex items-center gap-2">
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                            </svg>
                            <span>Secure payments via Stripe</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v4a2 2 0 002 2V6h10a2 2 0 00-2-2H4zm2 6a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-4zm6 4a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                            </svg>
                            <span>7-day money-back guarantee</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                            </svg>
                            <span>Cancel anytime</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

function FaqItem({ question, answer }: { question: string; answer: string }) {
    const [isOpen, setIsOpen] = useState(false)

    return (
        <motion.div
            className="border border-dark-300 rounded-xl overflow-hidden bg-dark-400"
            initial={false}
            whileHover={{ borderColor: 'rgba(255, 102, 171, 0.3)' }}
            transition={{ duration: 0.2 }}
        >
            <motion.button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full px-6 py-5 text-left flex justify-between items-center gap-4 group"
                whileTap={{ scale: 0.995 }}
                transition={{ duration: 0.15 }}
            >
                <span className="font-medium text-white group-hover:text-primary-400 transition-colors duration-200">
                    {question}
                </span>
                <motion.div
                    animate={{ rotate: isOpen ? 180 : 0 }}
                    transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                    className="flex-shrink-0"
                >
                    <svg
                        className="w-5 h-5 text-gray-400 group-hover:text-primary-400 transition-colors duration-200"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                        />
                    </svg>
                </motion.div>
            </motion.button>
            <AnimatePresence initial={false}>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                        className="overflow-hidden"
                    >
                        <div className="px-6 pb-5 text-gray-400 leading-relaxed border-t border-dark-300 pt-4">
                            {answer}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    )
}

export default PricingPage
