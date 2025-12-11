import type { QuotaStatus } from '@/types/api'
import { useCreditCount } from '@/hooks/useCredits'

interface QuotaDisplayProps {
    quota: QuotaStatus
    className?: string
    onBuyCredits?: () => void
}

export function QuotaDisplay({ quota, className, onBuyCredits }: QuotaDisplayProps) {
    const { credits, isLoading: loadingCredits } = useCreditCount()

    const monthPercent = quota.limit_month > 0
        ? Math.round((quota.used_this_month / quota.limit_month) * 100)
        : 0
    const dayPercent = quota.limit_day > 0
        ? Math.round((quota.used_today / quota.limit_day) * 100)
        : 0

    const quotaExhausted = quota.remaining_month <= 0 || quota.remaining_today <= 0
    const isLow = quota.remaining_month <= 2 || quota.remaining_today <= 1
    const hasCreditsAsBackup = credits > 0

    return (
        <div className={`card ${className}`}>
            <h3 className="text-lg font-medium text-white mb-4">Your Quota</h3>

            <div className="space-y-4">
                {/* Monthly quota */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Monthly</span>
                        <span className="text-white">
                            {quota.used_this_month} / {quota.limit_month}
                        </span>
                    </div>
                    <div className="w-full bg-dark-300 rounded-full h-2">
                        <div
                            className={`h-full rounded-full transition-all ${monthPercent > 90 ? 'bg-red-500' : monthPercent > 70 ? 'bg-yellow-500' : 'bg-primary-500'
                                }`}
                            style={{ width: `${Math.min(monthPercent, 100)}%` }}
                        />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                        {quota.remaining_month} remaining
                    </p>
                </div>

                {/* Daily quota */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Today</span>
                        <span className="text-white">
                            {quota.used_today} / {quota.limit_day}
                        </span>
                    </div>
                    <div className="w-full bg-dark-300 rounded-full h-2">
                        <div
                            className={`h-full rounded-full transition-all ${dayPercent > 90 ? 'bg-red-500' : dayPercent > 70 ? 'bg-yellow-500' : 'bg-primary-500'
                                }`}
                            style={{ width: `${Math.min(dayPercent, 100)}%` }}
                        />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                        {quota.remaining_today} remaining today
                    </p>
                </div>

                {/* Credits balance */}
                <div className="pt-2 border-t border-white/10">
                    <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-400">Credits</span>
                        {loadingCredits ? (
                            <span className="text-sm text-gray-500">...</span>
                        ) : (
                            <span className={`text-sm font-medium ${credits > 0 ? 'text-primary-400' : 'text-gray-500'}`}>
                                {credits} {credits === 1 ? 'credit' : 'credits'}
                            </span>
                        )}
                    </div>
                    {credits > 0 && quotaExhausted && (
                        <p className="text-xs text-primary-400 mt-1">
                            ✓ Credits will be used when quota runs out
                        </p>
                    )}
                </div>

                {/* Plan info */}
                <div className="pt-2 border-t border-white/10">
                    <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-400">Plan</span>
                        <span className="text-sm font-medium text-primary-400">
                            {quota.plan ? quota.plan.charAt(0).toUpperCase() + quota.plan.slice(1) : 'Free'}
                        </span>
                    </div>
                    {quota.resets_at && (
                        <p className="text-xs text-gray-500 mt-1">
                            Resets {new Date(quota.resets_at).toLocaleDateString()}
                        </p>
                    )}
                </div>

                {/* Warning - adapted for credit system */}
                {isLow && !hasCreditsAsBackup && (
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                        <p className="text-sm text-yellow-400 mb-2">
                            ⚠️ You're running low on quota.
                        </p>
                        {onBuyCredits && (
                            <button
                                onClick={onBuyCredits}
                                className="text-sm text-primary-400 hover:text-primary-300 underline"
                            >
                                Buy credits to continue →
                            </button>
                        )}
                    </div>
                )}

                {/* Quota exhausted but has credits */}
                {quotaExhausted && hasCreditsAsBackup && (
                    <div className="p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
                        <p className="text-sm text-primary-400">
                            💳 Using credits for extra songs ({credits} available)
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}
