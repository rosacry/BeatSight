/**
 * Credit Purchase Cancel Page.
 * Shown when user cancels the Stripe checkout.
 */

import { Link } from 'react-router-dom'

export function CreditCancelPage() {
    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-950 flex items-center justify-center px-4">
            <div className="max-w-md w-full text-center">
                {/* Cancel icon */}
                <div className="mx-auto w-20 h-20 bg-gray-700/50 rounded-full flex items-center justify-center mb-6">
                    <svg
                        className="w-10 h-10 text-gray-400"
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
                </div>

                <h1 className="text-3xl font-bold text-white mb-4">
                    Purchase Cancelled
                </h1>

                <p className="text-gray-400 mb-8">
                    No worries! Your card was not charged. You can try again anytime.
                </p>

                {/* Info box */}
                <div className="bg-gray-800/50 rounded-xl p-6 mb-8 border border-gray-700 text-left">
                    <h3 className="font-medium text-white mb-3">Why buy credits?</h3>
                    <ul className="space-y-2 text-sm text-gray-400">
                        <li className="flex items-start gap-2">
                            <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <span>Credits never expire - use them whenever</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <span>Pay only for what you need</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <span>Bulk packs save up to 43%</span>
                        </li>
                    </ul>
                </div>

                {/* Action buttons */}
                <div className="space-y-3">
                    <Link
                        to="/pricing"
                        className="block w-full py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-lg transition-colors"
                    >
                        View Pricing Options
                    </Link>
                    <Link
                        to="/"
                        className="block w-full py-3 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
                    >
                        Back to Home
                    </Link>
                </div>

                {/* Help text */}
                <p className="text-sm text-gray-500 mt-8">
                    Having trouble? <a href="mailto:support@beatsight.app" className="text-primary-400 hover:underline">Contact support</a>
                </p>
            </div>
        </div>
    )
}

export default CreditCancelPage
