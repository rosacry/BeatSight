/**
 * Navigation shell component.
 * Full-featured app shell with responsive navigation.
 * Enhanced with glassmorphism and smooth animations.
 */

import { useState, useEffect } from 'react'
import { Link, useLocation, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { UserMenu } from './UserMenu'
import { CreditBalance } from './CreditBalance'
import { ConfirmDialog } from './ConfirmDialog'
import { EXTERNAL_LINKS, getDocsLink, getCommunityLink } from '@/lib/externalLinks'
import { SKIP_LINK_TARGETS, ARIA_LABELS } from '@/lib/accessibility'

interface LayoutProps {
    children: React.ReactNode
}

interface NavItem {
    path: string
    label: string
    requiresAuth?: boolean
    icon?: React.ReactNode
}

const navItems: NavItem[] = [
    { path: '/', label: 'Home', icon: <HomeIcon /> },
    { path: '/queue', label: 'Queue', icon: <QueueIcon /> },
    { path: '/forum', label: 'Forum', icon: <ForumIcon /> },
    { path: '/leaderboard', label: 'Leaderboard', icon: <LeaderboardIcon /> },
    { path: '/record', label: 'Record', requiresAuth: true, icon: <MicIcon /> },
    { path: '/library', label: 'Library', requiresAuth: true, icon: <LibraryIcon /> },
]

function LeaderboardIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
    )
}

function HomeIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
    )
}

function ForumIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
        </svg>
    )
}

function QueueIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
    )
}

function MicIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
    )
}

function LibraryIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
        </svg>
    )
}

function MenuIcon() {
    return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
    )
}

function CloseIcon() {
    return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

function UploadIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
    )
}

function AdminIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
    )
}

function VerifyIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

export function Layout({ children }: LayoutProps) {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const isAdmin = useAuthStore((state) => state.isAdmin())
    const isStaff = useAuthStore((state) => state.isStaff())
    const isVerifier = useAuthStore((state) => state.isVerifier())
    const logout = useAuthStore((state) => state.logout)
    const navigate = useNavigate()
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
    const [isScrolled, setIsScrolled] = useState(false)
    const [showMobileSignOutConfirm, setShowMobileSignOutConfirm] = useState(false)

    // Track scroll for header effects
    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 10)
        }
        window.addEventListener('scroll', handleScroll, { passive: true })
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    // Build nav items dynamically based on roles
    const visibleNavItems: NavItem[] = [
        ...navItems.filter((item) => !item.requiresAuth || isAuthenticated),
        // Add verifier dashboard for verifiers, staff, and admins
        ...(isVerifier ? [{ path: '/verifier', label: 'Verify', requiresAuth: true, icon: <VerifyIcon /> }] : []),
        // Add admin dashboard for staff and admins
        ...(isStaff || isAdmin ? [{ path: '/admin', label: 'Admin', requiresAuth: true, icon: <AdminIcon /> }] : []),
    ]

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-black flex flex-col relative">
            {/* Skip to main content link for screen readers */}
            <a
                href={`#${SKIP_LINK_TARGETS.MAIN_CONTENT}`}
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-cyan-500 focus:text-white focus:px-4 focus:py-2 focus:rounded-md focus:outline-none focus:ring-2 focus:ring-white"
            >
                Skip to main content
            </a>

            {/* Desktop Navigation - Glass effect with scroll awareness */}
            <motion.nav
                initial={{ y: -100 }}
                animate={{ y: 0 }}
                transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled
                    ? 'bg-slate-900/95 backdrop-blur-xl shadow-lg shadow-black/50'
                    : 'bg-slate-900/80 backdrop-blur-md'
                    }`}
                id={SKIP_LINK_TARGETS.NAVIGATION}
                aria-label="Main navigation"
            >
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        {/* Logo and main nav */}
                        <div className="flex items-center">
                            <Link to="/" className="flex items-center gap-2.5 group">
                                {/* Logo with enhanced blend effect */}
                                <motion.div
                                    className="relative"
                                    whileHover={{ scale: 1.05 }}
                                    transition={{ type: 'spring', stiffness: 400 }}
                                >
                                    <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/30 to-fuchsia-500/20 rounded-xl blur-lg opacity-0 group-hover:opacity-100 transition-opacity" />
                                    <div className="relative w-9 h-9 rounded-xl 
                                                  bg-slate-900/95
                                                  border border-white/10 flex items-center justify-center
                                                  group-hover:border-cyan-500/40 transition-all
                                                  shadow-lg shadow-black/30 group-hover:shadow-cyan-500/20
                                                  overflow-hidden">
                                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 via-transparent to-fuchsia-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                                        <img
                                            src="/icons/logo-navbar.png"
                                            alt="BeatSight"
                                            className="w-6 h-6 relative z-10 
                                                     [mix-blend-mode:screen] brightness-[1.4] saturate-[1.2]
                                                     drop-shadow-[0_0_6px_rgba(0,212,255,0.3)] 
                                                     group-hover:drop-shadow-[0_0_10px_rgba(0,212,255,0.5)] 
                                                     transition-all"
                                        />
                                    </div>
                                </motion.div>
                                <span className="text-xl font-bold text-white hidden sm:block 
                                               group-hover:text-cyan-400 transition-colors">
                                    BeatSight
                                </span>
                            </Link>

                            {/* Desktop nav links */}
                            <div className="hidden md:flex ml-6 items-center gap-0.5">
                                {visibleNavItems.map((item) => (
                                    <NavLink
                                        key={item.path}
                                        to={item.path}
                                        className={({ isActive }) =>
                                            `relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap ${isActive
                                                ? 'text-white'
                                                : 'text-slate-400 hover:text-white'
                                            }`
                                        }
                                    >
                                        {({ isActive }) => (
                                            <>
                                                {isActive && (
                                                    <motion.span
                                                        layoutId="activeNavBg"
                                                        className="absolute inset-0 bg-white/10 rounded-lg"
                                                        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                                                    />
                                                )}
                                                <span className="relative flex items-center gap-1.5">
                                                    {item.icon}
                                                    <span className="hidden lg:inline">{item.label}</span>
                                                </span>
                                            </>
                                        )}
                                    </NavLink>
                                ))}
                            </div>
                        </div>

                        {/* Right side actions */}
                        <div className="flex items-center gap-3">
                            {/* Desktop auth section */}
                            <div className="hidden md:flex items-center gap-3">
                                {isAuthenticated ? (
                                    <>
                                        <Link
                                            to="/upload"
                                            className="group relative flex items-center gap-2 px-4 py-2 
                                                     bg-gradient-to-r from-cyan-500 to-cyan-600 
                                                     hover:from-cyan-400 hover:to-cyan-500
                                                     text-white font-medium rounded-xl
                                                     shadow-[0_0_20px_rgba(0,212,255,0.3)]
                                                     hover:shadow-[0_0_30px_rgba(0,212,255,0.5)]
                                                     transition-all duration-300 whitespace-nowrap"
                                        >
                                            <UploadIcon />
                                            <span className="hidden xl:inline">Upload</span>
                                        </Link>
                                        <CreditBalance showWhenZero />
                                        <UserMenu />
                                    </>
                                ) : (
                                    <>
                                        <Link
                                            to="/login"
                                            className="text-slate-400 hover:text-white px-4 py-2 rounded-lg 
                                                     text-sm font-medium transition-colors"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-fuchsia-500 
                                                     text-white font-medium rounded-xl
                                                     shadow-[0_0_20px_rgba(0,212,255,0.3)]
                                                     hover:shadow-[0_0_30px_rgba(0,212,255,0.5)]
                                                     transition-all duration-300"
                                        >
                                            Sign up
                                        </Link>
                                    </>
                                )}
                            </div>

                            {/* Mobile menu button */}
                            <button
                                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                                className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white 
                                         hover:bg-white/10 transition-all duration-200"
                                aria-expanded={isMobileMenuOpen}
                                aria-controls="mobile-menu"
                                aria-label={isMobileMenuOpen ? ARIA_LABELS.MENU_CLOSE : ARIA_LABELS.MENU}
                            >
                                {isMobileMenuOpen ? <CloseIcon /> : <MenuIcon />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Mobile menu - Animated slide down */}
                <AnimatePresence>
                    {isMobileMenuOpen && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
                            className="md:hidden border-t border-white/10 bg-slate-900/95 backdrop-blur-xl"
                            id="mobile-menu"
                            role="menu"
                            aria-label="Mobile navigation menu"
                        >
                            <div className="px-2 pt-2 pb-3 space-y-1">
                                {visibleNavItems.map((item, index) => (
                                    <motion.div
                                        key={item.path}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: index * 0.05 }}
                                    >
                                        <NavLink
                                            to={item.path}
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className={({ isActive }) =>
                                                `flex items-center gap-3 px-4 py-3 rounded-xl text-base font-medium transition-all duration-200 ${isActive
                                                    ? 'bg-white/10 text-white'
                                                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                                                }`
                                            }
                                        >
                                            {item.icon}
                                            {item.label}
                                        </NavLink>
                                    </motion.div>
                                ))}
                            </div>

                            {/* Mobile auth section */}
                            <div className="px-2 pt-2 pb-4 border-t border-white/10">
                                {isAuthenticated ? (
                                    <div className="space-y-2">
                                        <Link
                                            to="/upload"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="flex items-center gap-3 px-4 py-3 rounded-xl text-base font-medium 
                                                 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white"
                                        >
                                            <UploadIcon />
                                            Upload Song
                                        </Link>
                                        <div className="px-4 py-3">
                                            <CreditBalance showWhenZero />
                                        </div>
                                        <Link
                                            to="/profile"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-xl text-base font-medium text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                                        >
                                            Profile
                                        </Link>
                                        <Link
                                            to="/settings"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-xl text-base font-medium text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                                        >
                                            Settings
                                        </Link>
                                        <button
                                            onClick={() => {
                                                setShowMobileSignOutConfirm(true)
                                                setIsMobileMenuOpen(false)
                                            }}
                                            className="block w-full text-left px-4 py-3 rounded-xl text-base font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
                                        >
                                            Sign out
                                        </button>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <Link
                                            to="/login"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-xl text-base font-medium text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-xl text-base font-medium 
                                                 bg-gradient-to-r from-cyan-500 to-fuchsia-500 text-white text-center"
                                        >
                                            Sign up
                                        </Link>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.nav>

            {/* Spacer for fixed nav */}
            <div className="h-16" />

            {/* Breadcrumb (for nested pages) */}
            <Breadcrumb />

            {/* Main content */}
            <main
                id={SKIP_LINK_TARGETS.MAIN_CONTENT}
                className="flex-1 w-full"
                tabIndex={-1}
            >
                {children}
            </main>

            {/* Footer - Glass effect */}
            <footer className="relative z-20 bg-slate-900/50 backdrop-blur-xl border-t border-white/10 mt-auto" role="contentinfo">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                        {/* Logo and copyright */}
                        <div className="flex items-center gap-3">
                            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-slate-800/90 to-slate-900/90 
                                          border border-white/10 flex items-center justify-center
                                          shadow-lg shadow-black/20 overflow-hidden relative">
                                <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-fuchsia-500/5" />
                                <img src="/icons/logo-navbar.png" alt="" className="w-4 h-4 relative z-10 brightness-105 contrast-110 drop-shadow-[0_0_4px_rgba(0,212,255,0.2)]" />
                            </div>
                            <p className="text-slate-500 text-sm">
                                © 2025 BeatSight. See the music before you play it.
                            </p>
                        </div>

                        {/* Links - ensure they're clickable */}
                        <nav className="flex items-center gap-8" aria-label="Footer navigation">
                            <a
                                href={getDocsLink()}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-500 hover:text-cyan-400 text-sm transition-colors cursor-pointer"
                            >
                                Documentation
                                <span className="sr-only"> (opens in new tab)</span>
                            </a>
                            <a
                                href={getCommunityLink()}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-500 hover:text-cyan-400 text-sm transition-colors cursor-pointer"
                            >
                                Support
                                <span className="sr-only"> (opens in new tab)</span>
                            </a>
                            <a
                                href={EXTERNAL_LINKS.github.org}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-500 hover:text-cyan-400 text-sm transition-colors cursor-pointer"
                            >
                                GitHub
                                <span className="sr-only"> (opens in new tab)</span>
                            </a>
                        </nav>
                    </div>
                </div>
            </footer>

            {/* Mobile sign out confirmation dialog */}
            <ConfirmDialog
                isOpen={showMobileSignOutConfirm}
                onClose={() => setShowMobileSignOutConfirm(false)}
                onConfirm={() => {
                    document.body.style.overflow = ''
                    document.body.style.pointerEvents = ''
                    setShowMobileSignOutConfirm(false)
                    setTimeout(() => {
                        logout()
                        navigate('/', { replace: true })
                    }, 150)
                }}
                title="Sign out"
                message="Are you sure you want to sign out of BeatSight?"
                confirmLabel="Sign out"
                cancelLabel="Stay signed in"
                variant="signout"
                style="popup"
            />
        </div>
    )
}

/**
 * Breadcrumb component for nested routes.
 */
function Breadcrumb() {
    const location = useLocation()

    // Don't show breadcrumb on home page
    if (location.pathname === '/') {
        return null
    }

    // Define breadcrumb mappings for dynamic routes
    const getBreadcrumbs = (): { path: string; label: string }[] => {
        const path = location.pathname
        const crumbs: { path: string; label: string }[] = [
            { path: '/', label: 'Home' },
        ]

        if (path.startsWith('/jobs/')) {
            crumbs.push({ path: '/queue', label: 'Job Queue' })
            crumbs.push({ path: path, label: 'Job Details' })
        } else if (path === '/queue') {
            crumbs.push({ path: '/queue', label: 'Job Queue' })
        } else if (path === '/upload') {
            crumbs.push({ path: '/upload', label: 'Upload Song' })
        } else if (path === '/library') {
            crumbs.push({ path: '/library', label: 'My Library' })
        } else if (path === '/login') {
            crumbs.push({ path: '/login', label: 'Sign In' })
        } else if (path === '/register') {
            crumbs.push({ path: '/register', label: 'Sign Up' })
        } else if (path === '/profile') {
            crumbs.push({ path: '/profile', label: 'Profile' })
        } else if (path === '/settings') {
            crumbs.push({ path: '/settings', label: 'Settings' })
        }

        return crumbs
    }

    const breadcrumbs = getBreadcrumbs()

    if (breadcrumbs.length <= 1) {
        return null
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/30 backdrop-blur-sm border-b border-white/5"
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
                <nav className="flex items-center gap-2 text-sm">
                    {breadcrumbs.map((crumb, index) => (
                        <span key={crumb.path} className="flex items-center gap-2">
                            {index > 0 && (
                                <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                            )}
                            {index === breadcrumbs.length - 1 ? (
                                <span className="text-slate-400">{crumb.label}</span>
                            ) : (
                                <Link
                                    to={crumb.path}
                                    className="text-slate-500 hover:text-cyan-400 transition-colors"
                                >
                                    {crumb.label}
                                </Link>
                            )}
                        </span>
                    ))}
                </nav>
            </div>
        </motion.div>
    )
}
