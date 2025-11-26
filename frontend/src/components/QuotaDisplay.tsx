import type { QuotaStatus } from '@/types/api'

interface QuotaDisplayProps {
    quota: QuotaStatus
    className?: string
}

export function QuotaDisplay({ quota, className }: QuotaDisplayProps) {
    const monthPercent = quota.limit_month > 0
        ? Math.round((quota.used_this_month / quota.limit_month) * 100)
        : 0
    const dayPercent = quota.limit_day > 0
        ? Math.round((quota.used_today / quota.limit_day) * 100)
        : 0

    const isLow = quota.remaining_month <= 2 || quota.remaining_today <= 1

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
                    <div className="w-full bg-gray-700 rounded-full h-2">
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
                    <div className="w-full bg-gray-700 rounded-full h-2">
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

                {/* Plan info */}
                <div className="pt-2 border-t border-gray-700">
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

                {/* Warning */}
                {isLow && (
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                        <p className="text-sm text-yellow-400">
                            ⚠️ You're running low on quota. Consider upgrading for more generations.
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}
