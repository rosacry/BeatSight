/**
 * Pricing Page Component.
 * Displays subscription plans and handles checkout.
 */

import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { PRICING_PLANS, type SubscriptionPlan } from '@/types/billing'
import { useSubscription, useUpgradeSubscription, useStripeConfig } from '@/hooks/useBilling'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/components/Toast'

export function PricingPage() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')

    const { isAuthenticated } = useAuthStore()
    const { data: subscription } = useSubscription()
    const { data: stripeConfig } = useStripeConfig()
    const upgradeMutation = useUpgradeSubscription()

    // Show message if cancelled checkout
    const cancelled = searchParams.get('cancelled')
    if (cancelled) {
        toast.info('Checkout cancelled. No charges were made.')
    }

    const handleSelectPlan = async (planId: SubscriptionPlan) => {
        if (!isAuthenticated()) {
            // Redirect to login with return URL
            navigate(`/login?redirect=/pricing&plan=${planId}`)
            return
        }

        if (planId === 'free') {
            // Can't purchase free, redirect to manage
            toast.info('You already have access to the free tier!')
            return
        }

        if (!stripeConfig?.is_configured) {
            toast.error('Payment system is not available. Please try again later.')
            return
        }

        // Determine if monthly or yearly
        const actualPlan: SubscriptionPlan =
            planId === 'pro_monthly' && billingCycle === 'yearly'
                ? 'pro_yearly'
                : planId

        upgradeMutation.mutate(actualPlan)
    }

    const currentPlan = subscription?.plan || 'free'

    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-950 py-16 px-4">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="text-center mb-12">
                    <h1 className="text-4xl font-bold text-white mb-4">
                        Simple, Transparent Pricing
                    </h1>
                    <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                        Choose the plan that fits your needs. Upgrade anytime.
                    </p>
                </div>

                {/* Billing Toggle */}
                <div className="flex justify-center mb-12">
                    <div className="bg-gray-800 p-1 rounded-lg flex">
                        <button
                            onClick={() => setBillingCycle('monthly')}
                            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${billingCycle === 'monthly'
                                    ? 'bg-purple-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            Monthly
                        </button>
                        <button
                            onClick={() => setBillingCycle('yearly')}
                            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${billingCycle === 'yearly'
                                    ? 'bg-purple-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            Yearly
                            <span className="ml-2 text-xs text-green-400">Save 20%</span>
                        </button>
                    </div>
                </div>

                {/* Pricing Cards */}
                <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
                    {PRICING_PLANS.map((plan) => {
                        const isCurrentPlan = currentPlan === plan.id ||
                            (currentPlan === 'pro_yearly' && plan.id === 'pro_monthly')
                        const price = billingCycle === 'yearly' && plan.priceYearly
                            ? plan.priceYearly
                            : plan.priceMonthly

                        return (
                            <div
                                key={plan.id}
                                className={`relative rounded-2xl p-8 ${plan.highlighted
                                        ? 'bg-gradient-to-b from-purple-900/50 to-gray-800 border-2 border-purple-500'
                                        : 'bg-gray-800 border border-gray-700'
                                    }`}
                            >
                                {plan.highlighted && (
                                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                                        <span className="bg-purple-600 text-white text-sm font-medium px-4 py-1 rounded-full">
                                            Most Popular
                                        </span>
                                    </div>
                                )}

                                <h3 className="text-2xl font-bold text-white mb-2">
                                    {plan.name}
                                </h3>
                                <p className="text-gray-400 mb-6">
                                    {plan.description}
                                </p>

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
                                            <span className="text-gray-300">{feature}</span>
                                        </li>
                                    ))}
                                </ul>

                                <button
                                    onClick={() => handleSelectPlan(plan.id)}
                                    disabled={isCurrentPlan || upgradeMutation.isPending}
                                    className={`w-full py-3 rounded-lg font-medium transition-colors ${isCurrentPlan
                                            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                                            : plan.highlighted
                                                ? 'bg-purple-600 hover:bg-purple-700 text-white'
                                                : 'bg-gray-700 hover:bg-gray-600 text-white'
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

                {/* FAQ Section */}
                <div className="mt-20 max-w-3xl mx-auto">
                    <h2 className="text-2xl font-bold text-white text-center mb-8">
                        Frequently Asked Questions
                    </h2>
                    <div className="space-y-6">
                        <FaqItem
                            question="What happens when I run out of AI generations?"
                            answer="Free users can wait until next month for their quota to reset. Pro users get 100 generations/month which resets on your billing date. Need more? Contact us for enterprise plans."
                        />
                        <FaqItem
                            question="Can I cancel anytime?"
                            answer="Yes! Cancel anytime from your account settings. You'll keep Pro access until the end of your billing period."
                        />
                        <FaqItem
                            question="What payment methods do you accept?"
                            answer="We accept all major credit cards (Visa, Mastercard, American Express) through our secure payment processor, Stripe."
                        />
                        <FaqItem
                            question="Is there a refund policy?"
                            answer="Yes, we offer a 7-day money-back guarantee. If you're not satisfied, contact support for a full refund."
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}

function FaqItem({ question, answer }: { question: string; answer: string }) {
    const [isOpen, setIsOpen] = useState(false)

    return (
        <div className="border border-gray-700 rounded-lg">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full px-6 py-4 text-left flex justify-between items-center"
            >
                <span className="font-medium text-white">{question}</span>
                <svg
                    className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''
                        }`}
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
            </button>
            {isOpen && (
                <div className="px-6 pb-4 text-gray-400">
                    {answer}
                </div>
            )}
        </div>
    )
}

export default PricingPage
