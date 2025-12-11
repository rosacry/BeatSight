/**
 * Landing Page Component.
 * Marketing page with hero, features, pricing preview, and CTA.
 */

import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PRICING_PLANS } from '@/types/billing'
import { LandingDemo } from '@/components/LandingDemo'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { PageContentWrapper } from '@/components/ui/UnifiedTransitions'
import {
    EXTERNAL_LINKS,
    getCommunityLink,
    getDocsLink,
    getApiDocsLink,
    getDownloadLink
} from '@/lib/externalLinks'

export function LandingPage() {
    useDocumentTitle(undefined) // Just "BeatSight"
    const { isAuthenticated } = useAuthStore()

    return (
        <PageContentWrapper className="min-h-screen bg-dark-500">
            {/* Hero Section */}
            <section className="relative overflow-hidden">
                <div className="relative max-w-5xl mx-auto px-4 py-20 sm:py-28">
                    <div className="text-center">
                        {/* Badge */}
                        <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-400/10 
                                      border border-primary-400/30 rounded-full mb-6">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary-400" />
                            </span>
                            <span className="text-primary-300 text-sm font-medium">
                                The Drum Transcription Library
                            </span>
                        </div>

                        <h1 className="text-4xl sm:text-6xl font-bold text-white mb-5 tracking-tight">
                            See the Music
                            <br />
                            <span className="text-primary-400">
                                Before You Play It
                            </span>
                        </h1>

                        <p className="text-lg text-gray-400 max-w-xl mx-auto mb-8">
                            Practice drums to any song with visual lookahead. Discover community beatmaps,
                            create your own, or use AI-assisted transcription.
                        </p>

                        <div className="flex flex-col sm:flex-row gap-3 justify-center">
                            {isAuthenticated() ? (
                                <Link
                                    to="/upload"
                                    className="px-6 py-3 bg-primary-400 hover:bg-primary-500 text-white font-semibold rounded-lg transition-colors"
                                >
                                    Create Your First Beatmap
                                </Link>
                            ) : (
                                <>
                                    <Link
                                        to="/register"
                                        className="px-6 py-3 bg-primary-400 hover:bg-primary-500 text-white font-semibold rounded-lg transition-colors"
                                    >
                                        Get Started Free
                                    </Link>
                                    <Link
                                        to="/login"
                                        className="px-6 py-3 bg-dark-400 hover:bg-dark-300 text-white font-semibold rounded-lg transition-colors border border-white/10"
                                    >
                                        Sign In
                                    </Link>
                                </>
                            )}
                        </div>

                        {/* Stats */}
                        <div className="mt-12 grid grid-cols-3 gap-6 max-w-sm mx-auto">
                            <StatItem value="21" label="Drum Classes" />
                            <StatItem value="85%" label="Accuracy" />
                            <StatItem value="<2min" label="Processing" />
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="bg-dark-400 py-20 border-t border-white/5">
                <div className="max-w-5xl mx-auto px-4">
                    <div className="text-center mb-12">
                        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                            How It Works
                        </h2>
                        <p className="text-gray-400 max-w-xl mx-auto">
                            From audio file to playable beatmap in three simple steps
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-6">
                        <FeatureCard
                            step={1}
                            icon={<PlayIcon />}
                            title="Discover & Practice"
                            description="Browse community beatmaps or search for your favorite songs. Practice with visual lookahead."
                        />
                        <FeatureCard
                            step={2}
                            icon={<UploadIcon />}
                            title="Create & Share"
                            description="Build beatmaps from scratch, use AI-assisted transcription, or refine existing maps."
                        />
                        <FeatureCard
                            step={3}
                            icon={<AIIcon />}
                            title="Learn & Improve"
                            description="Slow down sections, isolate drum tracks, and track your progress as you master each song."
                        />
                    </div>
                </div>
            </section>

            {/* Technology Section */}
            <section className="bg-dark-500 py-20">
                <div className="max-w-5xl mx-auto px-4">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4">
                                Built for Real Drummers
                            </h2>
                            <p className="text-gray-400 mb-6">
                                Visual lookahead helps your brain pre-plan movements instead of reacting.
                                Research shows this accelerates motor skill acquisition.
                            </p>
                            <ul className="space-y-4">
                                <TechFeature
                                    title="Visual Lookahead"
                                    description="See notes before you play them"
                                />
                                <TechFeature
                                    title="Tempo Control"
                                    description="Slow sections down, speed up as you learn"
                                />
                                <TechFeature
                                    title="Stem Isolation"
                                    description="Practice with just drums or full mix"
                                />
                                <TechFeature
                                    title="Community Library"
                                    description="Access beatmaps created by drummers"
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
            <section className="bg-dark-400 py-20 border-t border-white/5">
                <div className="max-w-4xl mx-auto px-4">
                    <div className="text-center mb-12">
                        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                            Simple, Fair Pricing
                        </h2>
                        <p className="text-gray-400">
                            Start free, upgrade when you need more
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
                        {PRICING_PLANS.map((plan) => (
                            <div
                                key={plan.id}
                                className={`rounded-xl p-6 ${plan.highlighted
                                    ? 'bg-dark-300 border-2 border-primary-400/50'
                                    : 'bg-dark-300 border border-white/5'
                                    }`}
                            >
                                <h3 className="text-xl font-bold text-white mb-2">{plan.name}</h3>
                                <div className="mb-4">
                                    <span className="text-3xl font-bold text-white">${plan.priceMonthly}</span>
                                    {plan.priceMonthly > 0 && <span className="text-gray-400">/month</span>}
                                </div>
                                <ul className="space-y-2 mb-4">
                                    {plan.features.slice(0, 4).map((feature, idx) => (
                                        <li key={idx} className="flex items-center gap-2 text-gray-300 text-sm">
                                            <svg className="w-4 h-4 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>

                    <div className="text-center mt-6">
                        <Link
                            to="/pricing"
                            className="text-primary-400 hover:text-primary-300 font-medium"
                        >
                            View full pricing details →
                        </Link>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="bg-dark-500 py-16">
                <div className="max-w-2xl mx-auto px-4 text-center">
                    <div className="p-8 rounded-xl bg-dark-400 border border-white/5">
                        <h2 className="text-2xl font-bold text-white mb-3">
                            Ready to Create Your First Beatmap?
                        </h2>
                        <p className="text-gray-400 mb-6">
                            Join drummers using BeatSight to practice and improve.
                        </p>
                        <Link
                            to={isAuthenticated() ? "/upload" : "/register"}
                            className="inline-block px-6 py-3 bg-primary-400 hover:bg-primary-500 text-white font-semibold rounded-lg transition-colors"
                        >
                            {isAuthenticated() ? "Start Creating" : "Get Started Free"}
                        </Link>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="bg-dark-500 border-t border-white/5 py-10">
                <div className="max-w-5xl mx-auto px-4">
                    <div className="grid md:grid-cols-4 gap-8">
                        <div>
                            <h3 className="text-white font-bold mb-3">BeatSight</h3>
                            <p className="text-gray-500 text-sm">
                                The global drum transcription library.
                            </p>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-3 text-sm">Product</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                                <li><a href={getDownloadLink()} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Desktop App</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-3 text-sm">Resources</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><a href={getDocsLink()} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Documentation</a></li>
                                <li><a href={getApiDocsLink()} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">API Reference</a></li>
                                <li><a href={getCommunityLink()} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Community</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="text-white font-semibold mb-3 text-sm">Legal</h4>
                            <ul className="space-y-2 text-gray-400 text-sm">
                                <li><Link to={EXTERNAL_LINKS.legal.privacy} className="hover:text-white transition-colors">Privacy Policy</Link></li>
                                <li><Link to={EXTERNAL_LINKS.legal.terms} className="hover:text-white transition-colors">Terms of Service</Link></li>
                                <li><a href={EXTERNAL_LINKS.legal.contact} className="hover:text-white transition-colors">Contact</a></li>
                            </ul>
                        </div>
                    </div>
                    <div className="mt-8 pt-6 border-t border-white/5 text-center text-gray-500 text-sm">
                        © {new Date().getFullYear()} BeatSight. All rights reserved.
                    </div>
                </div>
            </footer>
        </PageContentWrapper>
    )
}

// Helper Components

function StatItem({ value, label }: { value: string; label: string }) {
    return (
        <div className="text-center">
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-gray-500 text-xs">{label}</div>
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
        <div className="relative p-6 bg-dark-300 rounded-xl border border-white/5 
                      hover:border-primary-400/20 transition-colors">
            <div className="absolute -top-3 left-6">
                <span className="inline-flex items-center justify-center w-6 h-6 
                              bg-primary-400 text-white text-xs font-bold rounded-full">
                    {step}
                </span>
            </div>
            <div className="w-10 h-10 bg-primary-400/10 rounded-lg flex items-center justify-center mb-3 mt-1">
                {icon}
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
            <p className="text-gray-400 text-sm">{description}</p>
        </div>
    )
}

function TechFeature({ title, description }: { title: string; description: string }) {
    return (
        <li className="flex items-start gap-3">
            <svg className="w-5 h-5 text-primary-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
                <span className="text-white font-medium text-sm">{title}</span>
                <p className="text-gray-500 text-sm">{description}</p>
            </div>
        </li>
    )
}

// Icons

function UploadIcon() {
    return (
        <svg className="w-5 h-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
    )
}

function AIIcon() {
    return (
        <svg className="w-5 h-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
    )
}

function PlayIcon() {
    return (
        <svg className="w-5 h-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

export default LandingPage
