/**
 * HomePage - Enhanced landing page with modern rhythm game design
 * 
 * Features:
 * - Animated particle background
 * - Glassmorphism cards
 * - Micro-interactions
 * - Smooth scroll animations
 * - Premium visual effects
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getQueueLength, getQuota } from '@/api/client'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import {
    AnimatedCounter,
    TiltCard,
    SpotlightCard,
} from '@/components/ui'
import { ParticleBackground, GradientOrbs, AudioBars } from '@/components/ui/ParticleBackground'

// Animation variants
const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.1, delayChildren: 0.2 }
    }
}

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }
    }
}

const features = [
    {
        icon: (
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
        ),
        title: 'Any Audio Source',
        description: 'Upload any audio with drums: published songs, band practices, original compositions, or isolated drum tracks.',
        color: 'cyan',
    },
    {
        icon: (
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
        ),
        title: 'Fast Processing',
        description: 'Most songs are processed in 2-5 minutes using our optimized GPU pipeline with Demucs separation.',
        color: 'green',
    },
    {
        icon: (
            <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
            </svg>
        ),
        title: 'Customizable',
        description: 'Edit and customize generated beatmaps in our built-in editor. Adjust timing, add notes, and fine-tune.',
        color: 'magenta',
    },
]

const colorMap = {
    cyan: {
        bg: 'bg-cyan-500/10',
        border: 'border-cyan-500/30',
        text: 'text-cyan-400',
        glow: 'shadow-[0_0_30px_rgba(0,212,255,0.2)]',
    },
    green: {
        bg: 'bg-green-500/10',
        border: 'border-green-500/30',
        text: 'text-green-400',
        glow: 'shadow-[0_0_30px_rgba(34,197,94,0.2)]',
    },
    magenta: {
        bg: 'bg-fuchsia-500/10',
        border: 'border-fuchsia-500/30',
        text: 'text-fuchsia-400',
        glow: 'shadow-[0_0_30px_rgba(217,70,239,0.2)]',
    },
}

export function HomePage() {
    // Homepage title - similar to osu!'s "osu!" being the home title
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
        <div className="relative min-h-screen overflow-hidden">
            {/* Background Effects */}
            <div className="fixed inset-0 bg-gradient-to-b from-slate-900 via-slate-950 to-black pointer-events-none" />
            <GradientOrbs />
            <ParticleBackground
                particleCount={60}
                colors={['#00d4ff', '#ff3296', '#f59e0b']}
                speed={0.3}
                interactive={true}
            />

            {/* Content */}
            <div className="relative z-10">
                {/* Hero Section */}
                <section className="relative pt-12 pb-20 sm:pt-20 sm:pb-32 px-4">
                    <motion.div
                        className="max-w-6xl mx-auto text-center"
                        initial="hidden"
                        animate="visible"
                        variants={containerVariants}
                    >
                        {/* Main Title */}
                        <motion.h1
                            variants={itemVariants}
                            className="text-4xl sm:text-5xl lg:text-7xl font-bold mb-6 tracking-tight"
                        >
                            <span className="text-white">See the Music</span>
                            <br />
                            <span className="bg-gradient-to-r from-cyan-400 via-fuchsia-400 to-amber-400 
                                           bg-clip-text text-transparent">
                                Before You Play It
                            </span>
                        </motion.h1>

                        {/* Subtitle */}
                        <motion.p
                            variants={itemVariants}
                            className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed"
                        >
                            Practice drums to any song with visual lookahead. Discover community beatmaps, create your own from scratch, or use AI-assisted transcription.
                            <span className="text-white font-medium"> The rhythm game advantage for real drummers.</span>
                        </motion.p>

                        {/* CTA Buttons */}
                        <motion.div
                            variants={itemVariants}
                            className="flex flex-col sm:flex-row justify-center gap-4"
                        >
                            <Link
                                to="/upload"
                                className="group relative inline-flex items-center justify-center gap-2 px-8 py-4 
                                         bg-gradient-to-r from-cyan-500 to-cyan-600 
                                         hover:from-cyan-400 hover:to-cyan-500
                                         text-white font-semibold rounded-xl
                                         shadow-[0_0_30px_rgba(0,212,255,0.4)]
                                         hover:shadow-[0_0_50px_rgba(0,212,255,0.6)]
                                         transition-all duration-300 transform hover:scale-105"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                </svg>
                                Upload Song
                            </Link>

                            <Link
                                to="/queue"
                                className="group relative inline-flex items-center justify-center gap-2 px-8 py-4 
                                         bg-white/5 hover:bg-white/10
                                         border border-white/20 hover:border-white/30
                                         text-white font-semibold rounded-xl
                                         backdrop-blur-xl
                                         transition-all duration-300 hover:scale-105"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                </svg>
                                View Queue
                            </Link>
                        </motion.div>

                        {/* Audio Visualizer */}
                        <motion.div
                            variants={itemVariants}
                            className="mt-12 flex justify-center"
                        >
                            <AudioBars barCount={7} color="#00d4ff" />
                        </motion.div>
                    </motion.div>
                </section>

                {/* Stats Section */}
                <section className="relative py-12 px-4">
                    <motion.div
                        className="max-w-5xl mx-auto"
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-100px' }}
                        variants={containerVariants}
                    >
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                            {/* Jobs in Queue */}
                            <motion.div variants={itemVariants}>
                                <TiltCard className="h-full" tiltAmount={8}>
                                    <div className="relative h-full p-6 rounded-2xl bg-white/5 backdrop-blur-xl 
                                                  border border-white/10 hover:border-cyan-500/30
                                                  transition-all duration-300 text-center group">
                                        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br 
                                                      from-cyan-500/10 to-transparent opacity-0 
                                                      group-hover:opacity-100 transition-opacity" />
                                        <div className="relative">
                                            <div className="text-4xl font-bold text-cyan-400 mb-2">
                                                {queueData?.queue_length !== undefined ? (
                                                    <AnimatedCounter value={queueData.queue_length} />
                                                ) : (
                                                    <span className="text-slate-500">-</span>
                                                )}
                                            </div>
                                            <div className="text-slate-400 font-medium">Jobs in Queue</div>
                                        </div>
                                    </div>
                                </TiltCard>
                            </motion.div>

                            {/* Generations Available */}
                            <motion.div variants={itemVariants}>
                                <TiltCard className="h-full" tiltAmount={8}>
                                    <div className="relative h-full p-6 rounded-2xl bg-white/5 backdrop-blur-xl 
                                                  border border-white/10 hover:border-green-500/30
                                                  transition-all duration-300 text-center group">
                                        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br 
                                                      from-green-500/10 to-transparent opacity-0 
                                                      group-hover:opacity-100 transition-opacity" />
                                        <div className="relative">
                                            <div className="text-4xl font-bold text-green-400 mb-2">
                                                {quotaData?.remaining_today !== undefined ? (
                                                    <AnimatedCounter value={quotaData.remaining_today} />
                                                ) : (
                                                    <span className="text-slate-500">-</span>
                                                )}
                                            </div>
                                            <div className="text-slate-400 font-medium">Generations Available Today</div>
                                        </div>
                                    </div>
                                </TiltCard>
                            </motion.div>

                            {/* Processing Time */}
                            <motion.div variants={itemVariants}>
                                <TiltCard className="h-full" tiltAmount={8}>
                                    <div className="relative h-full p-6 rounded-2xl bg-white/5 backdrop-blur-xl 
                                                  border border-white/10 hover:border-fuchsia-500/30
                                                  transition-all duration-300 text-center group">
                                        <div className="absolute inset-0 rounded-2xl bg-gradient-to-br 
                                                      from-fuchsia-500/10 to-transparent opacity-0 
                                                      group-hover:opacity-100 transition-opacity" />
                                        <div className="relative">
                                            <div className="text-4xl font-bold text-fuchsia-400 mb-2">
                                                ~2-5 min
                                            </div>
                                            <div className="text-slate-400 font-medium">Average Processing Time</div>
                                        </div>
                                    </div>
                                </TiltCard>
                            </motion.div>
                        </div>
                    </motion.div>
                </section>

                {/* Features Section */}
                <section className="relative py-16 px-4">
                    <motion.div
                        className="max-w-6xl mx-auto"
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-100px' }}
                        variants={containerVariants}
                    >
                        <motion.h2
                            variants={itemVariants}
                            className="text-2xl sm:text-3xl font-bold text-white text-center mb-12"
                        >
                            Why Choose <span className="text-cyan-400">BeatSight</span>?
                        </motion.h2>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {features.map((feature, index) => {
                                const colors = colorMap[feature.color as keyof typeof colorMap]
                                return (
                                    <motion.div key={index} variants={itemVariants}>
                                        <SpotlightCard className="h-full">
                                            <div className={`h-full p-6 rounded-2xl bg-white/[0.02] backdrop-blur-xl 
                                                          border border-white/10 hover:border-white/20
                                                          transition-all duration-500 group`}>
                                                <div className={`w-14 h-14 ${colors.bg} rounded-xl 
                                                              flex items-center justify-center mb-5
                                                              ${colors.text} ${colors.glow}
                                                              group-hover:scale-110 transition-transform duration-300`}>
                                                    {feature.icon}
                                                </div>
                                                <h3 className="text-xl font-semibold text-white mb-3">
                                                    {feature.title}
                                                </h3>
                                                <p className="text-slate-400 leading-relaxed">
                                                    {feature.description}
                                                </p>
                                            </div>
                                        </SpotlightCard>
                                    </motion.div>
                                )
                            })}
                        </div>
                    </motion.div>
                </section>

                {/* How It Works Section */}
                <section className="relative py-16 px-4">
                    <motion.div
                        className="max-w-4xl mx-auto"
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-100px' }}
                        variants={containerVariants}
                    >
                        <motion.h2
                            variants={itemVariants}
                            className="text-2xl sm:text-3xl font-bold text-white text-center mb-12"
                        >
                            How It Works
                        </motion.h2>

                        <div className="relative">
                            {/* Connection Line */}
                            <div className="hidden md:block absolute top-1/2 left-0 right-0 h-0.5 
                                          bg-gradient-to-r from-transparent via-white/20 to-transparent" />

                            <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                                {[
                                    { step: 1, title: 'Upload Song', desc: 'Any MP3, WAV, or FLAC', icon: '📁' },
                                    { step: 2, title: 'AI Processing', desc: 'Drum separation & analysis', icon: '🤖' },
                                    { step: 3, title: 'Get Beatmap', desc: 'Download & practice', icon: '🎵' },
                                ].map((item, index) => (
                                    <motion.div
                                        key={index}
                                        variants={itemVariants}
                                        className="flex flex-col items-center text-center relative z-10"
                                    >
                                        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500/20 to-fuchsia-500/20 
                                                      border border-white/20 backdrop-blur-xl
                                                      flex items-center justify-center mb-4
                                                      group hover:scale-110 hover:border-cyan-500/50
                                                      transition-all duration-300 cursor-default">
                                            <span className="text-3xl">{item.icon}</span>
                                            <span className="absolute -top-2 -right-2 w-7 h-7 rounded-full 
                                                          bg-cyan-500 text-white text-sm font-bold
                                                          flex items-center justify-center shadow-lg">
                                                {item.step}
                                            </span>
                                        </div>
                                        <h3 className="text-lg font-semibold text-white mb-1">{item.title}</h3>
                                        <p className="text-slate-400 text-sm">{item.desc}</p>
                                    </motion.div>
                                ))}
                            </div>
                        </div>
                    </motion.div>
                </section>

                {/* CTA Section */}
                <section className="relative py-20 px-4">
                    <motion.div
                        className="max-w-3xl mx-auto text-center"
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true }}
                        variants={containerVariants}
                    >
                        <motion.div
                            variants={itemVariants}
                            className="p-8 sm:p-12 rounded-3xl bg-gradient-to-br from-cyan-500/10 via-fuchsia-500/5 to-transparent 
                                     border border-white/10 backdrop-blur-xl"
                        >
                            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4">
                                Ready to Start Practicing?
                            </h2>
                            <p className="text-slate-400 mb-8 max-w-lg mx-auto">
                                Join thousands of drummers who are improving their skills with AI-generated beatmaps.
                            </p>
                            <div className="flex flex-col sm:flex-row justify-center gap-4">
                                <Link
                                    to="/register"
                                    className="inline-flex items-center justify-center gap-2 px-8 py-4 
                                             bg-gradient-to-r from-cyan-500 to-fuchsia-500 
                                             text-white font-semibold rounded-xl
                                             shadow-[0_0_30px_rgba(0,212,255,0.3)]
                                             hover:shadow-[0_0_50px_rgba(0,212,255,0.5)]
                                             transition-all duration-300 transform hover:scale-105"
                                >
                                    Get Started Free
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                    </svg>
                                </Link>
                                <Link
                                    to="/pricing"
                                    className="inline-flex items-center justify-center gap-2 px-8 py-4 
                                             bg-white/5 hover:bg-white/10
                                             border border-white/20 hover:border-white/30
                                             text-white font-semibold rounded-xl
                                             transition-all duration-300"
                                >
                                    View Pricing
                                </Link>
                            </div>
                        </motion.div>
                    </motion.div>
                </section>

                {/* Community Vision Section */}
                <section className="relative py-16 px-4">
                    <motion.div
                        className="max-w-4xl mx-auto"
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-100px' }}
                        variants={containerVariants}
                    >
                        <motion.div
                            variants={itemVariants}
                            className="text-center mb-10"
                        >
                            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/30 mb-6">
                                <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <span className="text-sm font-medium text-cyan-400">Community Vision</span>
                            </div>
                            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4">
                                Building the Universal Drum Transcription Index
                            </h2>
                            <p className="text-slate-400 max-w-2xl mx-auto leading-relaxed">
                                BeatSight is more than a tool — it's the first <span className="text-white font-medium">global repository and community hub for drummers</span>,
                                similar to what <span className="text-fuchsia-400">osu!</span> built for rhythm gaming. Every beatmap you create and share contributes to a growing
                                universal index that helps drummers worldwide.
                            </p>
                        </motion.div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <motion.div variants={itemVariants}>
                                <div className="h-full p-6 rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 hover:border-cyan-500/30 transition-all">
                                    <div className="w-12 h-12 bg-cyan-500/10 rounded-xl flex items-center justify-center mb-4 text-cyan-400">
                                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-lg font-semibold text-white mb-2">Contribute</h3>
                                    <p className="text-slate-400 text-sm">Generate and verify beatmaps to earn karma and help build the index.</p>
                                </div>
                            </motion.div>

                            <motion.div variants={itemVariants}>
                                <div className="h-full p-6 rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 hover:border-fuchsia-500/30 transition-all">
                                    <div className="w-12 h-12 bg-fuchsia-500/10 rounded-xl flex items-center justify-center mb-4 text-fuchsia-400">
                                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-lg font-semibold text-white mb-2">Community</h3>
                                    <p className="text-slate-400 text-sm">Join forums, climb leaderboards, and connect with drummers globally.</p>
                                </div>
                            </motion.div>

                            <motion.div variants={itemVariants}>
                                <div className="h-full p-6 rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 hover:border-amber-500/30 transition-all">
                                    <div className="w-12 h-12 bg-amber-500/10 rounded-xl flex items-center justify-center mb-4 text-amber-400">
                                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-lg font-semibold text-white mb-2">Recognition</h3>
                                    <p className="text-slate-400 text-sm">Earn achievements and recognition as the index grows with your help.</p>
                                </div>
                            </motion.div>
                        </div>

                        <motion.div variants={itemVariants} className="text-center mt-10">
                            <Link
                                to="/leaderboard"
                                className="inline-flex items-center gap-2 text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
                            >
                                View Community Leaderboard
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                </svg>
                            </Link>
                        </motion.div>
                    </motion.div>
                </section>
            </div>
        </div>
    )
}
