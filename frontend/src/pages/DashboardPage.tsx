/**
 * Dashboard Page - User's personalized home page (shown when logged in)
 * 
 * Similar to osu!'s dashboard, this page shows:
 * - Recent activity
 * - User stats
 * - News/announcements
 * - Quick actions
 * - Community activity
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { listJobs } from '@/api/client'
import type { AIJob } from '@/types/api'
import { getRecentTopics } from '@/api/forum'
import { AnimatedCounter, TiltCard } from '@/components/ui'
import { ParticleBackground, GradientOrbs } from '@/components/ui/ParticleBackground'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

// Animation variants
const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.1, delayChildren: 0.1 }
    }
}

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }
    }
}

export function DashboardPage() {
    const user = useAuthStore((state) => state.user)

    // Set page title
    useDocumentTitle('dashboard')

    // Fetch recent jobs (user's own jobs)
    const { data: recentJobs } = useQuery({
        queryKey: ['myRecentJobs'],
        queryFn: () => listJobs({ pageSize: 5 }),
        enabled: !!user,
    })

    // Fetch recent forum activity
    const { data: recentTopics } = useQuery({
        queryKey: ['recentTopics'],
        queryFn: () => getRecentTopics({ pageSize: 5 }),
    })

    if (!user) {
        return null
    }

    return (
        <div className="relative min-h-screen overflow-hidden">
            {/* Background Effects */}
            <div className="fixed inset-0 bg-gradient-to-b from-slate-900 via-slate-950 to-black pointer-events-none" />
            <GradientOrbs />
            <ParticleBackground
                particleCount={40}
                colors={['#00d4ff', '#ff3296', '#f59e0b']}
                speed={0.2}
                interactive={false}
            />

            {/* Content */}
            <div className="relative z-10 max-w-7xl mx-auto px-4 py-8">
                <motion.div
                    initial="hidden"
                    animate="visible"
                    variants={containerVariants}
                >
                    {/* Welcome Header */}
                    <motion.div variants={itemVariants} className="mb-8">
                        <h1 className="text-3xl font-bold text-white">
                            Welcome back, <span className="text-cyan-400">{user.display_name}</span>
                        </h1>
                        <p className="text-slate-400 mt-2">
                            Here's what's happening in your BeatSight world
                        </p>
                    </motion.div>

                    <div className="grid lg:grid-cols-3 gap-6">
                        {/* Main Content - Left Column (2 cols) */}
                        <div className="lg:col-span-2 space-y-6">
                            {/* Quick Actions */}
                            <motion.div variants={itemVariants}>
                                <div className="grid sm:grid-cols-3 gap-4">
                                    <Link
                                        to="/upload"
                                        className="group relative p-5 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-cyan-600/10
                                                 border border-cyan-500/30 hover:border-cyan-400/50
                                                 transition-all duration-300 hover:scale-[1.02]"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                                                <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="font-semibold text-white">Upload Song</p>
                                                <p className="text-xs text-cyan-300/80">Create a beatmap</p>
                                            </div>
                                        </div>
                                    </Link>

                                    <Link
                                        to="/library"
                                        className="group relative p-5 rounded-2xl bg-gradient-to-br from-fuchsia-500/20 to-fuchsia-600/10
                                                 border border-fuchsia-500/30 hover:border-fuchsia-400/50
                                                 transition-all duration-300 hover:scale-[1.02]"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-xl bg-fuchsia-500/20 flex items-center justify-center">
                                                <svg className="w-5 h-5 text-fuchsia-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="font-semibold text-white">My Library</p>
                                                <p className="text-xs text-fuchsia-300/80">View your maps</p>
                                            </div>
                                        </div>
                                    </Link>

                                    <Link
                                        to="/forum"
                                        className="group relative p-5 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-600/10
                                                 border border-amber-500/30 hover:border-amber-400/50
                                                 transition-all duration-300 hover:scale-[1.02]"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
                                                <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="font-semibold text-white">Community</p>
                                                <p className="text-xs text-amber-300/80">Join discussions</p>
                                            </div>
                                        </div>
                                    </Link>
                                </div>
                            </motion.div>

                            {/* Recent Activity / News */}
                            <motion.div variants={itemVariants}>
                                <div className="rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 overflow-hidden">
                                    <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                                        <h2 className="text-lg font-semibold text-white">Recent Forum Activity</h2>
                                        <Link to="/forum" className="text-sm text-cyan-400 hover:text-cyan-300">
                                            View all →
                                        </Link>
                                    </div>
                                    <div className="divide-y divide-white/5">
                                        {recentTopics?.items?.slice(0, 5).map((topic) => (
                                            <Link
                                                key={topic.id}
                                                to={`/forum/topics/${topic.id}`}
                                                className="block px-6 py-4 hover:bg-white/5 transition-colors"
                                            >
                                                <div className="flex items-start gap-4">
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-white font-medium truncate">{topic.title}</p>
                                                        <p className="text-sm text-slate-400 mt-1">
                                                            {topic.post_count} posts • {new Date(topic.created_at).toLocaleDateString()}
                                                        </p>
                                                    </div>
                                                </div>
                                            </Link>
                                        ))}
                                        {(!recentTopics?.items || recentTopics.items.length === 0) && (
                                            <div className="px-6 py-8 text-center text-slate-400">
                                                No recent forum activity
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </motion.div>

                            {/* Recent Jobs */}
                            <motion.div variants={itemVariants}>
                                <div className="rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 overflow-hidden">
                                    <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                                        <h2 className="text-lg font-semibold text-white">Your Recent Jobs</h2>
                                        <Link to="/queue" className="text-sm text-cyan-400 hover:text-cyan-300">
                                            View queue →
                                        </Link>
                                    </div>
                                    <div className="divide-y divide-white/5">
                                        {recentJobs?.slice(0, 5).map((job: AIJob) => (
                                            <Link
                                                key={job.id}
                                                to={`/jobs/${job.id}`}
                                                className="block px-6 py-4 hover:bg-white/5 transition-colors"
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-white font-medium truncate">
                                                            Job #{job.id.slice(0, 8)}
                                                        </p>
                                                        <p className="text-sm text-slate-400 mt-1">
                                                            {new Date(job.created_at).toLocaleDateString()}
                                                        </p>
                                                    </div>
                                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${job.state === 'complete' ? 'bg-green-500/20 text-green-400' :
                                                        job.state === 'processing' ? 'bg-yellow-500/20 text-yellow-400' :
                                                            job.state === 'failed' ? 'bg-red-500/20 text-red-400' :
                                                                'bg-blue-500/20 text-blue-400'
                                                        }`}>
                                                        {job.state}
                                                    </span>
                                                </div>
                                            </Link>
                                        ))}
                                        {(!recentJobs || recentJobs.length === 0) && (
                                            <div className="px-6 py-8 text-center text-slate-400">
                                                <p>No recent jobs</p>
                                                <Link to="/upload" className="text-cyan-400 hover:text-cyan-300 mt-2 inline-block">
                                                    Upload your first song →
                                                </Link>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        </div>

                        {/* Sidebar - Right Column */}
                        <div className="space-y-6">
                            {/* User Stats Card */}
                            <motion.div variants={itemVariants}>
                                <TiltCard tiltAmount={5}>
                                    <div className="p-6 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-xl border border-white/10">
                                        <div className="flex items-center gap-4 mb-6">
                                            {user.avatar_url ? (
                                                <img
                                                    src={user.avatar_url}
                                                    alt={user.display_name}
                                                    className="w-16 h-16 rounded-full border-2 border-cyan-500/50"
                                                />
                                            ) : (
                                                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500 to-fuchsia-500 flex items-center justify-center text-2xl font-bold text-white">
                                                    {user.display_name?.[0]?.toUpperCase() || '?'}
                                                </div>
                                            )}
                                            <div>
                                                <p className="font-bold text-white text-lg">{user.display_name}</p>
                                                <p className="text-sm text-slate-400">{user.email}</p>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="text-center p-3 rounded-xl bg-white/5">
                                                <p className="text-2xl font-bold text-cyan-400">
                                                    <AnimatedCounter value={user.karma_score || 0} />
                                                </p>
                                                <p className="text-xs text-slate-400 mt-1">Karma</p>
                                            </div>
                                            <div className="text-center p-3 rounded-xl bg-white/5">
                                                <p className="text-2xl font-bold text-fuchsia-400">
                                                    <AnimatedCounter value={recentJobs?.length || 0} />
                                                </p>
                                                <p className="text-xs text-slate-400 mt-1">Maps</p>
                                            </div>
                                        </div>

                                        <Link
                                            to="/profile"
                                            className="mt-4 block text-center py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm font-medium transition-colors"
                                        >
                                            View Profile
                                        </Link>
                                    </div>
                                </TiltCard>
                            </motion.div>

                            {/* Quick Links */}
                            <motion.div variants={itemVariants}>
                                <div className="p-5 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10">
                                    <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Quick Links</h3>
                                    <div className="space-y-2">
                                        <Link to="/pricing" className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors">
                                            <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            <span className="text-white text-sm">View Pricing</span>
                                        </Link>
                                        <Link to="/settings" className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors">
                                            <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                            </svg>
                                            <span className="text-white text-sm">Settings</span>
                                        </Link>
                                        <a href="https://docs.beatsight.io" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors">
                                            <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                            </svg>
                                            <span className="text-white text-sm">Documentation</span>
                                        </a>
                                    </div>
                                </div>
                            </motion.div>

                            {/* Support BeatSight */}
                            <motion.div variants={itemVariants}>
                                <Link
                                    to="/pricing"
                                    className="block p-5 rounded-2xl bg-gradient-to-br from-cyan-500/20 via-fuchsia-500/10 to-amber-500/20 border border-white/10 hover:border-cyan-500/30 transition-colors"
                                >
                                    <div className="flex items-center gap-3 mb-3">
                                        <svg className="w-6 h-6 text-pink-400" fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
                                        </svg>
                                        <span className="font-semibold text-white">Support BeatSight</span>
                                    </div>
                                    <p className="text-sm text-slate-300">
                                        Get Pro for unlimited maps, priority processing, and support development!
                                    </p>
                                </Link>
                            </motion.div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </div>
    )
}
