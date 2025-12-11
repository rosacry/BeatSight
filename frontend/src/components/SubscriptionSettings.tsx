/**
 * Subscription management component for Settings page.
 * Displays current plan and provides upgrade/manage options.
 */

import { useSubscription, useManageSubscription, useStripeConfig } from '@/hooks/useBilling'
import { PRICING_PLANS } from '@/types/billing'
import { Link } from 'react-router-dom'
import { Skeleton } from '@/components/Skeleton'

export function SubscriptionSettings() {
    const { data: subscription, isLoading: subLoading } = useSubscription()
    const { data: stripeConfig } = useStripeConfig()
    const manageMutation = useManageSubscription()

    if (subLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-24 w-full" />
            </div>
        )
    }

    const currentPlanId = subscription?.plan || 'free'
    const currentPlan = PRICING_PLANS.find(
        p => p.id === currentPlanId ||
            (currentPlanId === 'pro_yearly' && p.id === 'pro_monthly')
    ) || PRICING_PLANS[0]

    const isPro = currentPlanId === 'pro_monthly' || currentPlanId === 'pro_yearly'

    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-lg font-semibold text-white mb-4">
                    Subscription
                </h3>

                {/* Current Plan Card */}
                <div className="bg-dark-400 rounded-lg p-6 border border-white/10">
                    <div className="flex items-start justify-between">
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <h4 className="text-xl font-bold text-white">
                                    {currentPlan.name}
                                </h4>
                                {isPro && (
                                    <span className="px-2 py-0.5 bg-primary-500/20 text-primary-400 text-xs font-medium rounded">
                                        PRO
                                    </span>
                                )}
                            </div>
                            <p className="text-gray-400 text-sm mb-4">
                                {currentPlan.description}
                            </p>

                            {/* Status */}
                            <div className="flex items-center gap-4 text-sm">
                                <div className="flex items-center gap-2">
                                    <span className={`w-2 h-2 rounded-full ${subscription?.is_active
                                            ? 'bg-green-400'
                                            : 'bg-yellow-400'
                                        }`} />
                                    <span className="text-gray-300 capitalize">
                                        {subscription?.status || 'Active'}
                                    </span>
                                </div>

                                {subscription?.current_period_end && (
                                    <span className="text-gray-500">
                                        Renews {new Date(subscription.current_period_end).toLocaleDateString()}
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Price */}
                        <div className="text-right">
                            <div className="text-2xl font-bold text-white">
                                ${currentPlanId === 'pro_yearly'
                                    ? currentPlan.priceYearly
                                    : currentPlan.priceMonthly}
                            </div>
                            {currentPlan.priceMonthly > 0 && (
                                <span className="text-gray-400 text-sm">/month</span>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* AI Quota */}
            <div>
                <h3 className="text-lg font-semibold text-white mb-4">
                    AI Generation Quota
                </h3>
                <div className="bg-dark-400 rounded-lg p-6 border border-white/10">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-gray-300">Remaining this period</span>
                        <span className="text-white font-bold text-xl">
                            {subscription?.ai_quota_remaining ?? 3}
                        </span>
                    </div>
                    <div className="w-full bg-dark-300 rounded-full h-2">
                        <div
                            className="bg-primary-500 h-2 rounded-full transition-all"
                            style={{
                                width: `${Math.min(100, ((subscription?.ai_quota_remaining ?? 3) / (isPro ? 100 : 3)) * 100)}%`
                            }}
                        />
                    </div>
                    <p className="text-gray-500 text-sm mt-2">
                        {isPro ? '100' : '3'} total per month
                    </p>
                </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
                {isPro && stripeConfig?.is_configured && (
                    <button
                        onClick={() => manageMutation.mutate()}
                        disabled={manageMutation.isPending}
                        className="px-4 py-2 bg-dark-300 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
                    >
                        {manageMutation.isPending ? 'Loading...' : 'Manage Subscription'}
                    </button>
                )}

                {!isPro && (
                    <Link
                        to="/pricing"
                        className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors"
                    >
                        Upgrade to Pro
                    </Link>
                )}
            </div>

            {/* Payment Method Notice */}
            {isPro && (
                <p className="text-gray-500 text-sm">
                    Manage payment methods, view invoices, and cancel subscription through the billing portal.
                </p>
            )}
        </div>
    )
}

export default SubscriptionSettings
