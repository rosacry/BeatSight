/**
 * Credit Purchase Success Page.
 * Shown after successful credit purchase via Stripe checkout.
 */

import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useRefreshCreditBalance, useCreditBalance } from '@/hooks/useCredits'
import { useToast } from '@/components/Toast'

export function CreditSuccessPage() {
    const [searchParams] = useSearchParams()
    const refreshBalance = useRefreshCreditBalance()
    const { data: balance, isLoading } = useCreditBalance()
    const { success } = useToast()
    const hasShownToast = useRef(false)

    // Refresh balance on mount to get updated credit count
    useEffect(() => {
        refreshBalance()
    }, [refreshBalance])

    // Show success toast once when balance loads
    useEffect(() => {
        if (balance && !hasShownToast.current) {
            success('Credits Added!', `Your account now has ${balance.balance} credits`)
            hasShownToast.current = true
        }
    }, [balance, success])

    const sessionId = searchParams.get('session_id')

    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-950 flex items-center justify-center px-4">
            <div className="max-w-md w-full text-center">
                {/* Success icon */}
                <div className="mx-auto w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-6">
                    <svg
                        className="w-10 h-10 text-green-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                        />
                    </svg>
                </div>

                <h1 className="text-3xl font-bold text-white mb-4">
                    Payment Successful!
                </h1>

                <p className="text-gray-400 mb-6">
                    Your credits have been added to your account.
                </p>

                {/* Credit balance display */}
                <div className="bg-gray-800 rounded-xl p-6 mb-8 border border-gray-700">
                    <p className="text-sm text-gray-400 mb-2">Your Credit Balance</p>
                    {isLoading ? (
                        <div className="animate-pulse h-10 bg-gray-700 rounded w-24 mx-auto" />
                    ) : (
                        <p className="text-4xl font-bold text-primary-400">
                            {balance?.balance ?? 0}
                            <span className="text-lg font-normal text-gray-400 ml-2">credits</span>
                        </p>
                    )}
                </div>

                {/* Action buttons */}
                <div className="space-y-3">
                    <Link
                        to="/upload"
                        className="block w-full py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-lg transition-colors"
                    >
                        Generate a Beatmap
                    </Link>
                    <Link
                        to="/library"
                        className="block w-full py-3 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
                    >
                        Go to My Library
                    </Link>
                </div>

                {/* Receipt note */}
                <p className="text-sm text-gray-500 mt-8">
                    A receipt has been sent to your email address.
                    {sessionId && (
                        <span className="block mt-1 text-xs text-gray-600">
                            Reference: {sessionId.slice(0, 20)}...
                        </span>
                    )}
                </p>
            </div>
        </div>
    )
}

export default CreditSuccessPage
