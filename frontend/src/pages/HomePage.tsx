/**
 * HomePage - Clean, osu!-inspired landing page
 * 
 * Features:
 * - Clean dark backgrounds
 * - Subtle accent colors (pink/purple like osu!)
 * - Smooth but restrained animations
 * - Clear visual hierarchy
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getQueueLength, getQuota } from '@/api/client'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { AnimatedCounter } from '@/components/ui'

// Animation variants - subtle and smooth
const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.08, delayChildren: 0.1 }
    }
}

const itemVariants = {
    hidden: { opacity: 0, y: 15 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }
    }
}

const features = [
    {
        icon: (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
        ),
        title: '21 Drum Classes',
        description: 'The most detailed drum detection: rimshots, ghost notes, hi-hat variations, ride bell, cymbal chokes, and more.',
    },
    {
        icon: (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
        ),
        title: 'Technique Detection',
        description: 'Goes beyond notes — detects how you play: flams, drags, rolls, ghost notes, and velocity dynamics.',
    },
    {
        icon: (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
        ),
        title: 'Community Library',
        description: 'Building the universal index for drum transcriptions. Every map you create and verify grows the collection.',
    },
]

export function HomePage() {
    useDocumentTitle('See the Music Before You Play It')

    const { data: queueData } = useQuery({
        queryKey: ['queueLength'],
        queryFn: getQueueLength,
        refetchInterval: 30000,
    })

    const { data: quotaData } = useQuery({
        queryKey: ['quota'],
        queryFn: getQuota,
    })

    return (
        <div className="min-h-screen bg-dark-500">
            {/* Hero Section */}
            <section className="relative pt-16 pb-20 px-4">
                {/* Subtle gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-b from-primary-400/5 via-transparent to-transparent pointer-events-none" />

                <motion.div
                    className="max-w-5xl mx-auto text-center relative z-10"
                    initial="hidden"
                    animate="visible"
                    variants={containerVariants}
                >
                    {/* Main Title */}
                    <motion.h1
                        variants={itemVariants}
                        className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 tracking-tight"
                    >
                        <span className="text-white">See the Music</span>
                        <br />
                        <span className="text-primary-400">Before You Play It</span>
                    </motion.h1>

                    {/* Subtitle */}
                    <motion.p
                        variants={itemVariants}
                        className="text-lg text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed"
                    >
                        The global repository for drummers. Discover beatmaps, create your own,
                        or use AI transcription. <span className="text-white">Practice any song with visual lookahead.</span>
                    </motion.p>

                    {/* CTA Buttons */}
                    <motion.div
                        variants={itemVariants}
                        className="flex flex-col sm:flex-row justify-center gap-4"
                    >
                        <Link
                            to="/upload"
                            className="inline-flex items-center justify-center gap-2 px-8 py-3.5 
                                     bg-primary-400 hover:bg-primary-500
                                     text-white font-semibold rounded-lg
                                     shadow-lg hover:shadow-glow-pink
                                     transition-all duration-200"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                            </svg>
                            Upload Song
                        </Link>

                        <Link
                            to="/queue"
                            className="inline-flex items-center justify-center gap-2 px-8 py-3.5 
                                     bg-dark-300 hover:bg-dark-200
                                     border border-white/10 hover:border-white/20
                                     text-white font-semibold rounded-lg
                                     transition-all duration-200"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            View Queue
                        </Link>
                    </motion.div>
                </motion.div>
            </section>

            {/* Stats Section */}
            <section className="py-12 px-4 border-t border-white/5">
                <motion.div
                    className="max-w-4xl mx-auto"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-50px' }}
                    variants={containerVariants}
                >
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                        {/* Jobs in Queue */}
                        <motion.div variants={itemVariants}>
                            <div className="p-6 rounded-xl bg-dark-400 border border-white/5 text-center
                                          hover:border-primary-400/20 transition-colors">
                                <div className="text-3xl font-bold text-primary-400 mb-1">
                                    {queueData?.queue_length !== undefined ? (
                                        <AnimatedCounter value={queueData.queue_length} />
                                    ) : (
                                        <span className="text-gray-500">-</span>
                                    )}
                                </div>
                                <div className="text-gray-500 text-sm font-medium">Jobs in Queue</div>
                            </div>
                        </motion.div>

                        {/* Generations Available */}
                        <motion.div variants={itemVariants}>
                            <div className="p-6 rounded-xl bg-dark-400 border border-white/5 text-center
                                          hover:border-green-500/20 transition-colors">
                                <div className="text-3xl font-bold text-green-400 mb-1">
                                    {quotaData?.remaining_today !== undefined ? (
                                        <AnimatedCounter value={quotaData.remaining_today} />
                                    ) : (
                                        <span className="text-gray-500">-</span>
                                    )}
                                </div>
                                <div className="text-gray-500 text-sm font-medium">Available Today</div>
                            </div>
                        </motion.div>

                        {/* Processing Time */}
                        <motion.div variants={itemVariants}>
                            <div className="p-6 rounded-xl bg-dark-400 border border-white/5 text-center
                                          hover:border-accent-400/20 transition-colors">
                                <div className="text-3xl font-bold text-accent-400 mb-1">
                                    ~2-5 min
                                </div>
                                <div className="text-gray-500 text-sm font-medium">Processing Time</div>
                            </div>
                        </motion.div>
                    </div>
                </motion.div>
            </section>

            {/* Features Section */}
            <section className="py-16 px-4">
                <motion.div
                    className="max-w-5xl mx-auto"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-50px' }}
                    variants={containerVariants}
                >
                    <motion.h2
                        variants={itemVariants}
                        className="text-2xl sm:text-3xl font-bold text-white text-center mb-3"
                    >
                        Why <span className="text-primary-400">BeatSight</span>?
                    </motion.h2>

                    <motion.p
                        variants={itemVariants}
                        className="text-gray-400 text-center max-w-xl mx-auto mb-12"
                    >
                        Most tools detect 6-8 drum classes. We detect <span className="text-white font-medium">21</span>,
                        trained on <span className="text-white font-medium">14+ million samples</span>.
                    </motion.p>

                    <div className="grid md:grid-cols-3 gap-6">
                        {features.map((feature, index) => (
                            <motion.div
                                key={feature.title}
                                variants={itemVariants}
                                className="p-6 rounded-xl bg-dark-400 border border-white/5
                                          hover:border-primary-400/20 transition-colors group"
                            >
                                <div className="w-12 h-12 rounded-lg bg-primary-400/10 
                                              flex items-center justify-center mb-4
                                              text-primary-400 group-hover:bg-primary-400/20 transition-colors">
                                    {feature.icon}
                                </div>
                                <h3 className="text-lg font-semibold text-white mb-2">
                                    {feature.title}
                                </h3>
                                <p className="text-gray-400 text-sm leading-relaxed">
                                    {feature.description}
                                </p>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>
            </section>

            {/* How It Works Section */}
            <section className="py-16 px-4 border-t border-white/5">
                <motion.div
                    className="max-w-4xl mx-auto"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-50px' }}
                    variants={containerVariants}
                >
                    <motion.h2
                        variants={itemVariants}
                        className="text-2xl font-bold text-white text-center mb-10"
                    >
                        How It Works
                    </motion.h2>

                    <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                        {[
                            { step: 1, title: 'Upload Song', desc: 'Any MP3, WAV, or FLAC', icon: '📁' },
                            { step: 2, title: 'AI Processing', desc: 'Drum separation & analysis', icon: '🎯' },
                            { step: 3, title: 'Get Beatmap', desc: 'Download & practice', icon: '🎵' },
                        ].map((item, index) => (
                            <motion.div
                                key={index}
                                variants={itemVariants}
                                className="flex flex-col items-center text-center"
                            >
                                <div className="relative w-16 h-16 rounded-xl bg-dark-400 border border-white/10
                                              flex items-center justify-center mb-3
                                              hover:border-primary-400/30 transition-colors">
                                    <span className="text-2xl">{item.icon}</span>
                                    <span className="absolute -top-2 -right-2 w-6 h-6 rounded-full 
                                                  bg-primary-400 text-white text-xs font-bold
                                                  flex items-center justify-center">
                                        {item.step}
                                    </span>
                                </div>
                                <h3 className="font-semibold text-white mb-1">{item.title}</h3>
                                <p className="text-gray-500 text-sm">{item.desc}</p>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>
            </section>

            {/* CTA Section */}
            <section className="py-16 px-4">
                <motion.div
                    className="max-w-2xl mx-auto text-center"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true }}
                    variants={containerVariants}
                >
                    <motion.div
                        variants={itemVariants}
                        className="p-8 rounded-xl bg-dark-400 border border-white/5"
                    >
                        <h2 className="text-2xl font-bold text-white mb-3">
                            Ready to Start?
                        </h2>
                        <p className="text-gray-400 mb-6">
                            Join drummers improving with AI-generated beatmaps.
                        </p>
                        <div className="flex flex-col sm:flex-row justify-center gap-3">
                            <Link
                                to="/register"
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 
                                         bg-primary-400 hover:bg-primary-500
                                         text-white font-semibold rounded-lg
                                         transition-all duration-200"
                            >
                                Get Started Free
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                </svg>
                            </Link>
                            <Link
                                to="/pricing"
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 
                                         bg-dark-300 hover:bg-dark-200
                                         border border-white/10
                                         text-white font-semibold rounded-lg
                                         transition-all duration-200"
                            >
                                View Pricing
                            </Link>
                        </div>
                    </motion.div>
                </motion.div>
            </section>

            {/* Comparison Table */}
            <section className="py-16 px-4 border-t border-white/5">
                <motion.div
                    className="max-w-4xl mx-auto"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-50px' }}
                    variants={containerVariants}
                >
                    <motion.div variants={itemVariants} className="text-center mb-8">
                        <span className="inline-block px-3 py-1 rounded-full bg-green-500/10 
                                       border border-green-500/30 text-green-400 text-xs font-medium mb-4">
                            Technical Comparison
                        </span>
                        <h2 className="text-2xl font-bold text-white mb-2">
                            Why BeatSight Leads
                        </h2>
                        <p className="text-gray-400 text-sm">
                            Compared to other transcription tools
                        </p>
                    </motion.div>

                    <motion.div variants={itemVariants}>
                        <div className="rounded-xl bg-dark-400 border border-white/5 overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-white/10">
                                            <th className="px-4 py-3 text-left text-gray-400 font-medium">Feature</th>
                                            <th className="px-4 py-3 text-center text-primary-400 font-bold">BeatSight</th>
                                            <th className="px-4 py-3 text-center text-gray-400 font-medium">Others</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Drum Classes</td>
                                            <td className="px-4 py-3 text-center text-primary-400 font-medium">21</td>
                                            <td className="px-4 py-3 text-center text-gray-500">6-8</td>
                                        </tr>
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Training Samples</td>
                                            <td className="px-4 py-3 text-center text-primary-400 font-medium">14.6M</td>
                                            <td className="px-4 py-3 text-center text-gray-500">Limited</td>
                                        </tr>
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Snare Articulations</td>
                                            <td className="px-4 py-3 text-center text-green-400">✓</td>
                                            <td className="px-4 py-3 text-center text-gray-500">✗</td>
                                        </tr>
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Hi-Hat Variations</td>
                                            <td className="px-4 py-3 text-center text-green-400">5 types</td>
                                            <td className="px-4 py-3 text-center text-gray-500">2 types</td>
                                        </tr>
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Cymbal Chokes</td>
                                            <td className="px-4 py-3 text-center text-green-400">✓</td>
                                            <td className="px-4 py-3 text-center text-gray-500">✗</td>
                                        </tr>
                                        <tr className="hover:bg-white/5 transition-colors">
                                            <td className="px-4 py-3 text-white">Community Library</td>
                                            <td className="px-4 py-3 text-center text-green-400">✓</td>
                                            <td className="px-4 py-3 text-center text-gray-500">✗</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </motion.div>
                </motion.div>
            </section>

            {/* Community Section */}
            <section className="py-16 px-4">
                <motion.div
                    className="max-w-4xl mx-auto"
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-50px' }}
                    variants={containerVariants}
                >
                    <motion.div variants={itemVariants} className="text-center mb-10">
                        <span className="inline-block px-3 py-1 rounded-full bg-primary-400/10 
                                       border border-primary-400/30 text-primary-400 text-xs font-medium mb-4">
                            Community
                        </span>
                        <h2 className="text-2xl font-bold text-white mb-2">
                            Build the Universal Drum Library
                        </h2>
                        <p className="text-gray-400 max-w-2xl mx-auto">
                            Like osu! for rhythm games, we're building the go-to place for drum transcriptions.
                            Every map you contribute helps drummers worldwide.
                        </p>
                    </motion.div>

                    <div className="grid md:grid-cols-3 gap-4">
                        {[
                            { icon: '➕', title: 'Create & Share', desc: 'Generate AI maps or create from scratch' },
                            { icon: '✓', title: 'Verify & Refine', desc: 'Improve maps and earn karma' },
                            { icon: '👥', title: 'Grow Together', desc: 'Connect with drummers globally' },
                        ].map((item, index) => (
                            <motion.div
                                key={index}
                                variants={itemVariants}
                                className="p-5 rounded-xl bg-dark-400 border border-white/5
                                          hover:border-primary-400/20 transition-colors"
                            >
                                <span className="text-2xl mb-3 block">{item.icon}</span>
                                <h3 className="font-semibold text-white mb-1">{item.title}</h3>
                                <p className="text-gray-500 text-sm">{item.desc}</p>
                            </motion.div>
                        ))}
                    </div>

                    <motion.div variants={itemVariants} className="text-center mt-8">
                        <Link
                            to="/leaderboard"
                            className="inline-flex items-center gap-2 text-primary-400 hover:text-primary-300 
                                     font-medium transition-colors"
                        >
                            View Leaderboard
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                        </Link>
                    </motion.div>
                </motion.div>
            </section>
        </div>
    )
}
