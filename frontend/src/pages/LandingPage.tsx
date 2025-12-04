/**
 * Landing Page Component.
 * Marketing page with hero, features, pricing preview, and CTA.
 */

import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PRICING_PLANS } from '@/types/billing'
import { LandingDemo } from '@/components/LandingDemo'

export function LandingPage() {
    const { isAuthenticated } = useAuthStore()

    return (
        <div className="min-h-screen bg-gray-950">
            {/* Hero Section */}
            <section className="relative overflow-hidden">
                {/* Gradient background */}
                <div className="absolute inset-0 bg-gradient-to-br from-purple-900/30 via-gray-900 to-gray-950" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-600/20 via-transparent to-transparent" />

                <div className="relative max-w-7xl mx-auto px-4 py-24 sm:py-32">
                    <div className="text-center">
                        {/* Badge */}
                        <div className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600/10 border border-purple-500/30 rounded-full mb-8">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
                            </span>
                            <span className="text-purple-300 text-sm font-medium">
                                AI-Powered Drum Transcription
                            </span>
                        </div>

                        <h1 className="text-5xl sm:text-7xl font-bold text-white mb-6 tracking-tight">
                            Turn Any Song Into
                            <br />
                            <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                                Playable Beatmaps
                            </span>
                        </h1>

                        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10">
                            BeatSight uses advanced AI to transcribe drums from any audio track
                            and generate rhythm game beatmaps you can actually play.
                        </p>

                        <div className="flex flex-col sm:flex-row gap-4 justify-center">
                            {isAuthenticated() ? (
                                <Link
                                    to="/upload"
                                    className="px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-colors text-lg"
                                >
                                    Create Your First Beatmap
                                </Link>
                            ) : (
                                <>
                                    <Link
                                        to="/register"
                                        className="px-8 py-4 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-colors text-lg"
                                    >
                                        Get Started Free
                                    </Link>
                                    <Link
                                        to="/login"
                                        className="px-8 py-4 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-lg transition-colors text-lg border border-gray-700"
                                    >
                                        Sign In
                                    </Link>
                                </>
                            )}
                        </div>

                        {/* Stats */}
                        <div className="mt-16 grid grid-cols-3 gap-8 max-w-lg mx-auto">
                            <StatItem value="19" label="Drum Classes" />
                            <StatItem value="85%" label="Accuracy" />
                            <StatItem value="<2min" label="Processing" />
                        </div>
                    </div>
                </div>

                {/* Wave divider */}
                <div className="absolute bottom-0 left-0 right-0">
                    <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M0 120L60 110C120 100 240 80 360 70C480 60 600 60 720 65C840 70 960 80 1080 85C1200 90 1320 90 1380 90L1440 90V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0V120Z" fill="#111827" />
                    </svg>
                </div>
            </section>

            {/* Features Section */}
            <section className="bg-gray-900 py-24">
                <div className="max-w-7xl mx-auto px-4">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                            How It Works
                        </h2>
                        <p className="text-gray-400 text-lg max-w-2xl mx-auto">
                            From audio file to playable beatmap in three simple steps
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        <FeatureCard
                            step={1}
                            icon={<UploadIcon />}
                            title="Upload Your Track"
                            description="Upload any audio file (MP3, WAV, FLAC). Our AI handles the rest."
                        />
                        <FeatureCard
                            step={2}
                            icon={<AIIcon />}
                            title="AI Transcription"
                            description="Advanced neural networks detect and classify 19 different drum sounds."
                        />
                        <FeatureCard
                            step={3}
                            icon={<PlayIcon />}
                            title="Play & Enjoy"
                            description="Export to osu! format or play directly in the BeatSight desktop app."
                        />
                    </div>
                </div>
            </section>

            {/* Technology Section */}
            <section className="bg-gray-950 py-24">
                <div className="max-w-7xl mx-auto px-4">
                    <div className="grid lg:grid-cols-2 gap-16 items-center">
                        <div>
                            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
                                Powered by State-of-the-Art AI
                            </h2>
                            <p className="text-gray-400 text-lg mb-8">
                                Our proprietary neural network is trained on over 16 million drum samples,
                                enabling unprecedented accuracy in drum transcription.
                            </p>
                            <ul className="space-y-4">
                                <TechFeature
                                    title="19 Drum Classes"
                                    description="From kicks and snares to hi-hats, toms, and cymbals"
                                />
                                <TechFeature
                                    title="Source Separation"
                                    description="Demucs-based separation isolates drums from the mix"
                                />
                                <TechFeature
                                    title="Onset Detection"
                                    description="Precise timing with sub-10ms accuracy"
                                />
                                <TechFeature
                                    title="Velocity Estimation"
                                    description="Dynamic range preserved for expressive beatmaps"
                                />
                            </ul>
                        </div>
                        <div className="relative">
                            <LandingDemo />
                        </div>
                    </div>
                </div>
            </section>

            {/* Pricing Preview */}
            <section className="bg-gray-900 py-24">
                <div className="max-w-7xl mx-auto px-4">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                            Simple, Fair Pricing
                        </h2>
                        <p className="text-gray-400 text-lg">
                            Start free, upgrade when you need more
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
                        {PRICING_PLANS.map((plan) => (
                            <div
                                key={plan.id}
                                className={`rounded-2xl p-8 ${plan.highlighted
                                    ? 'bg-gradient-to-b from-purple-900/50 to-gray-800 border-2 border-purple-500'
                                    : 'bg-gray-800 border border-gray-700'
                                    }`}
                            >
                                <h3 className="text-2xl font-bold text-white mb-2">{plan.name}</h3>
                                <div className="mb-4">
                                    <span className="text-4xl font-bold text-white">${plan.priceMonthly}</span>
                                    {plan.priceMonthly > 0 && <span className="text-gray-400">/month</span>}
                                </div>
                                <ul className="space-y-3 mb-6">
                                    {plan.features.slice(0, 4).map((feature, idx) => (
                                        <li key={idx} className="flex items-center gap-2 text-gray-300">
                                            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>

                    <div className="text-center mt-8">
                        <Link
                            to="/pricing"
                            className="text-purple-400 hover:text-purple-300 font-medium"
                        >
                            View full pricing details →
                        </Link>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="bg-gradient-to-r from-purple-900 to-pink-900 py-20">
                <div className="max-w-4xl mx-auto px-4 text-center">
                    <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
                        Ready to Create Your First Beatmap?
                    </h2>
                    <p className="text-purple-200 text-lg mb-8">
                        Join thousands of drummers and rhythm game enthusiasts using BeatSight.
                    </p>
                    <Link
                        to={isAuthenticated() ? "/upload" : "/register"}
                        className="inline-block px-8 py-4 bg-white text-purple-900 font-semibold rounded-lg hover:bg-gray-100 transition-colors text-lg"
                    >
                        {isAuthenticated() ? "Start Creating" : "Get Started Free"}
                    </Link>
                </div>
            </section>

            {/* Footer */}
            <footer className="bg-gray-950 border-t border-gray-800 py-12">
                <div className="max-w-7xl mx-auto px-4">
                    <div className="grid md:grid-cols-4 gap-8">
                        <div>
                            <h3 className="text-white font-bold text-lg mb-4">BeatSight</h3>
                            <p className="text-gray-400 text-sm">
                                AI-powered drum transcription and beatmap generation.
                            </p>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-4">Product</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><Link to="/pricing" className="hover:text-white">Pricing</Link></li>
                                <li><a href="#features" className="hover:text-white">Features</a></li>
                                <li><a href="#" className="hover:text-white">Desktop App</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-4">Resources</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><a href="#" className="hover:text-white">Documentation</a></li>
                                <li><a href="#" className="hover:text-white">API Reference</a></li>
                                <li><a href="#" className="hover:text-white">Community</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-4">Legal</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><a href="#" className="hover:text-white">Privacy Policy</a></li>
                                <li><a href="#" className="hover:text-white">Terms of Service</a></li>
                                <li><a href="#" className="hover:text-white">Contact</a></li>
                            </ul>
                        </div>
                    </div>
                    <div className="mt-12 pt-8 border-t border-gray-800 text-center text-gray-500 text-sm">
                        © {new Date().getFullYear()} BeatSight. All rights reserved.
                    </div>
                </div>
            </footer>
        </div>
    )
}

// Helper Components

function StatItem({ value, label }: { value: string; label: string }) {
    return (
        <div>
            <div className="text-3xl font-bold text-white">{value}</div>
            <div className="text-gray-400 text-sm">{label}</div>
        </div>
    )
}

function FeatureCard({
    step,
    icon,
    title,
    description
}: {
    step: number
    icon: React.ReactNode
    title: string
    description: string
}) {
    return (
        <div className="relative p-8 bg-gray-800 rounded-2xl border border-gray-700 hover:border-purple-500/50 transition-colors">
            <div className="absolute -top-4 left-8">
                <span className="inline-flex items-center justify-center w-8 h-8 bg-purple-600 text-white text-sm font-bold rounded-full">
                    {step}
                </span>
            </div>
            <div className="w-12 h-12 bg-purple-600/20 rounded-lg flex items-center justify-center mb-4 mt-2">
                {icon}
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">{title}</h3>
            <p className="text-gray-400">{description}</p>
        </div>
    )
}

function TechFeature({ title, description }: { title: string; description: string }) {
    return (
        <li className="flex items-start gap-3">
            <svg className="w-6 h-6 text-purple-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
                <span className="text-white font-medium">{title}</span>
                <p className="text-gray-400 text-sm">{description}</p>
            </div>
        </li>
    )
}

// Icons

function UploadIcon() {
    return (
        <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
    )
}

function AIIcon() {
    return (
        <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
    )
}

function PlayIcon() {
    return (
        <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

export default LandingPage
