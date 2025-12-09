/**
 * Main forum page showing all categories and forums.
 * Redesigned to match BeatSight's cyan/magenta design language.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { getForumCategories, getRecentTopics } from '@/api/forum'
import { ForumCategoryList, TopicList } from '@/components/forum'
import { useAuthStore } from '@/stores/authStore'
import { GradientOrbs, ParticleBackground } from '@/components/ui/ParticleBackground'
import { AnimatedCounter } from '@/components/ui'
import type { Forum } from '@/types/forum'

// Animation variants
const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.08, delayChildren: 0.1 }
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

const modalVariants = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: { opacity: 1, scale: 1, transition: { duration: 0.2 } },
    exit: { opacity: 0, scale: 0.95, transition: { duration: 0.15 } }
}

export function ForumPage() {
    const user = useAuthStore((state) => state.user)
    const navigate = useNavigate()
    const [showForumSelector, setShowForumSelector] = useState(false)

    const {
        data: categories,
        isLoading: categoriesLoading,
        error: categoriesError,
    } = useQuery({
        queryKey: ['forumCategories'],
        queryFn: getForumCategories,
    })

    const { data: recentTopics } = useQuery({
        queryKey: ['recentTopics'],
        queryFn: () => getRecentTopics({ pageSize: 5 }),
    })

    // Get all forums that allow topics
    const allForums: Forum[] = categories?.flatMap(c =>
        c.forums.filter(f => f.is_visible && f.allow_topics)
    ) || []

    const handleForumSelect = (forum: Forum) => {
        setShowForumSelector(false)
        navigate(`/forum/${forum.id}?new=true`)
    }

    // Calculate stats
    const totalTopics = categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.topic_count, 0), 0) || 0
    const totalPosts = categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.post_count, 0), 0) || 0
    const totalForums = categories?.reduce((acc, c) => acc + c.forums.length, 0) || 0

    return (
        <div className="relative min-h-screen overflow-hidden">
            {/* Background Effects */}
            <div className="fixed inset-0 bg-gradient-to-b from-slate-900 via-slate-950 to-black pointer-events-none" />
            <GradientOrbs />
            <ParticleBackground
                particleCount={30}
                colors={['#00d4ff', '#ff3296', '#f59e0b']}
                speed={0.15}
                interactive={false}
            />

            {/* Content */}
            <div className="relative z-10 max-w-6xl mx-auto px-4 py-8">
                <motion.div
                    initial="hidden"
                    animate="visible"
                    variants={containerVariants}
                    className="space-y-8"
                >
                    {/* Header */}
                    <motion.div variants={itemVariants}>
                        <div className="relative overflow-hidden rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 p-8">
                            <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                                <div>
                                    <h1 className="text-4xl font-bold text-white mb-2">
                                        Community <span className="text-cyan-400">Forums</span>
                                    </h1>
                                    <p className="text-slate-300 text-lg">
                                        Discuss beatmaps, strategies, and connect with other drummers
                                    </p>
                                </div>

                                {/* Action buttons */}
                                <div className="flex items-center gap-3">
                                    {/* New Topic Button */}
                                    {user && (
                                        <button
                                            onClick={() => setShowForumSelector(true)}
                                            className="group flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-cyan-600 
                                                     hover:from-cyan-400 hover:to-cyan-500 rounded-xl text-white font-medium
                                                     transition-all duration-200 hover:scale-[1.02] shadow-lg shadow-cyan-500/25"
                                        >
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                                            </svg>
                                            New Topic
                                        </button>
                                    )}

                                    {/* Search */}
                                    <Link
                                        to="/forum/search"
                                        className="flex items-center gap-2 px-5 py-2.5 bg-white/10 hover:bg-white/20 
                                                 rounded-xl text-white transition-all duration-200 backdrop-blur-sm border border-white/10"
                                    >
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                        </svg>
                                        Search
                                    </Link>
                                </div>
                            </div>

                            {/* Background decoration */}
                            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl" />
                            <div className="absolute bottom-0 left-0 w-48 h-48 bg-magenta-500/10 rounded-full blur-3xl" />
                        </div>
                    </motion.div>

                    {/* Quick stats */}
                    <motion.div variants={itemVariants}>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                            {user && (
                                <div className="group p-5 rounded-2xl bg-gradient-to-br from-magenta-500/20 to-magenta-600/10
                                              border border-magenta-500/30 hover:border-magenta-400/50 transition-all duration-300">
                                    <div className="text-3xl font-bold text-magenta-400">
                                        <AnimatedCounter value={user.karma_score || 0} />
                                    </div>
                                    <div className="text-sm text-slate-400 mt-1">Your Karma</div>
                                </div>
                            )}
                            <div className="group p-5 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-cyan-600/10
                                          border border-cyan-500/30 hover:border-cyan-400/50 transition-all duration-300">
                                <div className="text-3xl font-bold text-cyan-400">
                                    <AnimatedCounter value={totalTopics} />
                                </div>
                                <div className="text-sm text-slate-400 mt-1">Total Topics</div>
                            </div>
                            <div className="group p-5 rounded-2xl bg-gradient-to-br from-fuchsia-500/20 to-fuchsia-600/10
                                          border border-fuchsia-500/30 hover:border-fuchsia-400/50 transition-all duration-300">
                                <div className="text-3xl font-bold text-fuchsia-400">
                                    <AnimatedCounter value={totalPosts} />
                                </div>
                                <div className="text-sm text-slate-400 mt-1">Total Posts</div>
                            </div>
                            <div className="group p-5 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-600/10
                                          border border-amber-500/30 hover:border-amber-400/50 transition-all duration-300">
                                <div className="text-3xl font-bold text-amber-400">
                                    <AnimatedCounter value={totalForums} />
                                </div>
                                <div className="text-sm text-slate-400 mt-1">Forums</div>
                            </div>
                        </div>
                    </motion.div>

                    {/* Recent Topics */}
                    {recentTopics && recentTopics.items.length > 0 && (
                        <motion.div variants={itemVariants}>
                            <div className="rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 overflow-hidden">
                                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-magenta-500 flex items-center justify-center">
                                            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </div>
                                        <h2 className="text-xl font-bold text-white">Recent Topics</h2>
                                    </div>
                                    <Link
                                        to="/forum/recent"
                                        className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
                                    >
                                        View all →
                                    </Link>
                                </div>
                                <div className="p-5">
                                    <TopicList
                                        topics={recentTopics.items}
                                        showForum={true}
                                        emptyMessage="No recent topics"
                                    />
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* Error state */}
                    {categoriesError && (
                        <motion.div variants={itemVariants}>
                            <div className="rounded-2xl bg-red-500/10 border border-red-500/30 p-6 text-red-400">
                                <div className="flex items-center gap-3">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                    <span>Failed to load forums. Please try again later.</span>
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {/* Categories and Forums */}
                    <motion.div variants={itemVariants}>
                        <ForumCategoryList
                            categories={categories || []}
                            isLoading={categoriesLoading}
                        />
                    </motion.div>

                    {/* Login prompt for non-logged in users */}
                    {!user && (
                        <motion.div variants={itemVariants}>
                            <div className="rounded-2xl bg-gradient-to-r from-cyan-500/10 to-magenta-500/10 
                                          border border-cyan-500/30 p-8 text-center">
                                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-cyan-500 to-magenta-500 
                                              flex items-center justify-center">
                                    <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-bold text-white mb-2">Join the Conversation</h3>
                                <p className="text-slate-400 mb-6">Sign in to create topics, reply to discussions, and earn karma</p>
                                <div className="flex items-center justify-center gap-4">
                                    <Link
                                        to="/login"
                                        className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500
                                                 rounded-xl text-white font-medium transition-all duration-200"
                                    >
                                        Sign In
                                    </Link>
                                    <Link
                                        to="/register"
                                        className="px-6 py-2.5 bg-white/10 hover:bg-white/20 rounded-xl text-white font-medium
                                                 transition-all duration-200 border border-white/10"
                                    >
                                        Create Account
                                    </Link>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </motion.div>
            </div>

            {/* Forum Selector Modal */}
            <AnimatePresence>
                {showForumSelector && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setShowForumSelector(false)}
                            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
                        />

                        {/* Modal */}
                        <motion.div
                            initial="hidden"
                            animate="visible"
                            exit="exit"
                            variants={modalVariants}
                            className="fixed inset-0 z-50 flex items-center justify-center p-4"
                        >
                            <div className="w-full max-w-lg bg-slate-900 rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
                                {/* Modal Header */}
                                <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                                    <h2 className="text-xl font-bold text-white">Select a Forum</h2>
                                    <button
                                        onClick={() => setShowForumSelector(false)}
                                        className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                                    >
                                        <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>

                                {/* Forum List */}
                                <div className="max-h-96 overflow-y-auto p-4 space-y-2">
                                    {categories?.map(category => (
                                        <div key={category.id}>
                                            <div className="px-3 py-2 text-sm font-medium text-slate-500 uppercase tracking-wider">
                                                {category.name}
                                            </div>
                                            {category.forums
                                                .filter(f => f.is_visible && f.allow_topics)
                                                .map(forum => (
                                                    <button
                                                        key={forum.id}
                                                        onClick={() => handleForumSelect(forum)}
                                                        className="w-full p-4 rounded-xl bg-white/5 hover:bg-white/10 
                                                                 border border-transparent hover:border-cyan-500/30
                                                                 text-left transition-all duration-200 group"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/30 to-magenta-500/20 
                                                                          flex items-center justify-center group-hover:from-cyan-500/40 group-hover:to-magenta-500/30">
                                                                <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                                                                </svg>
                                                            </div>
                                                            <div className="flex-1 min-w-0">
                                                                <div className="font-medium text-white group-hover:text-cyan-400 transition-colors">
                                                                    {forum.name}
                                                                </div>
                                                                {forum.description && (
                                                                    <div className="text-sm text-slate-400 truncate">
                                                                        {forum.description}
                                                                    </div>
                                                                )}
                                                            </div>
                                                            <svg className="w-5 h-5 text-slate-500 group-hover:text-cyan-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                                            </svg>
                                                        </div>
                                                    </button>
                                                ))}
                                        </div>
                                    ))}

                                    {allForums.length === 0 && (
                                        <div className="text-center py-8 text-slate-400">
                                            No forums available for posting
                                        </div>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    )
}
