/**
 * Navigation shell component.
 * Full-featured app shell with responsive navigation.
 * Enhanced with glassmorphism and smooth animations.
 */

import { useState, useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { UserMenu } from './UserMenu'
import { CreditBalance } from './CreditBalance'
import { ConfirmDialog } from './ConfirmDialog'
import { EXTERNAL_LINKS, getDocsLink, getCommunityLink } from '@/lib/externalLinks'
import { SKIP_LINK_TARGETS, ARIA_LABELS } from '@/lib/accessibility'
import { forceUnlockBodyScroll } from '@/lib/bodyScrollLock'

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
        <div className="min-h-screen bg-dark-500 flex flex-col relative overflow-x-hidden">
            {/* Skip to main content link for screen readers */}
            <a
                href={`#${SKIP_LINK_TARGETS.MAIN_CONTENT}`}
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-primary-400 focus:text-white focus:px-4 focus:py-2 focus:rounded-md focus:outline-none focus:ring-2 focus:ring-white"
            >
                Skip to main content
            </a>

            {/* Navigation - osu! inspired clean header */}
            <motion.nav
                initial={{ y: -100 }}
                animate={{ y: 0 }}
                transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${isScrolled
                    ? 'bg-dark-600/95 backdrop-blur-md shadow-lg border-b border-white/5'
                    : 'bg-dark-600/80 backdrop-blur-sm'
                    }`}
                id={SKIP_LINK_TARGETS.NAVIGATION}
                aria-label="Main navigation"
            >
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-14">
                        {/* Logo and main nav */}
                        <div className="flex items-center">
                            <Link to="/" className="flex items-center gap-2 group">
                                {/* Logo - clean, no excessive effects */}
                                <motion.div
                                    className="relative"
                                    whileHover={{ scale: 1.02 }}
                                    transition={{ type: 'spring', stiffness: 400 }}
                                >
                                    <div className="w-8 h-8 rounded-lg bg-dark-400 border border-white/10 
                                                  flex items-center justify-center overflow-hidden
                                                  group-hover:border-primary-400/40 transition-colors">
                                        <img
                                            src="/icons/logo-navbar.png"
                                            alt="BeatSight"
                                            className="w-5 h-5"
                                        />
                                    </div>
                                </motion.div>
                                <span className="text-lg font-bold text-white hidden sm:block 
                                               group-hover:text-primary-400 transition-colors">
                                    BeatSight
                                </span>
                            </Link>

                            {/* Desktop nav links - clean, minimal */}
                            <LayoutGroup id="desktop-nav">
                                <div className="hidden md:flex ml-8 items-center gap-1">
                                    {visibleNavItems.map((item) => (
                                        <NavLink
                                            key={item.path}
                                            to={item.path}
                                            className={({ isActive }) =>
                                                `relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive
                                                    ? 'text-white bg-white/10'
                                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                                                }`
                                            }
                                        >
                                            {({ isActive }) => (
                                                <>
                                                    {isActive && (
                                                        <motion.span
                                                            layoutId="activeNavBg"
                                                            className="absolute inset-0 bg-white/10 rounded-lg"
                                                            initial={false}
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
                            </LayoutGroup>
                        </div>

                        {/* Right side actions */}
                        <div className="flex items-center gap-3">
                            {/* Desktop auth section */}
                            <div className="hidden md:flex items-center gap-3">
                                {isAuthenticated ? (
                                    <>
                                        <Link
                                            to="/upload"
                                            className="flex items-center gap-2 px-4 py-2 
                                                     bg-primary-400 hover:bg-primary-500
                                                     text-white font-medium rounded-lg
                                                     shadow-sm hover:shadow-glow-sm
                                                     transition-all duration-200"
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
                                            className="text-gray-400 hover:text-white px-3 py-2 rounded-lg 
                                                     text-sm font-medium transition-colors"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            className="px-4 py-2 bg-primary-400 hover:bg-primary-500 
                                                     text-white font-medium rounded-lg
                                                     transition-all duration-200"
                                        >
                                            Sign up
                                        </Link>
                                    </>
                                )}
                            </div>

                            {/* Mobile menu button */}
                            <button
                                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                                className="md:hidden p-2 rounded-lg text-gray-400 hover:text-white 
                                         hover:bg-white/10 transition-colors"
                                aria-expanded={isMobileMenuOpen}
                                aria-controls="mobile-menu"
                                aria-label={isMobileMenuOpen ? ARIA_LABELS.MENU_CLOSE : ARIA_LABELS.MENU}
                            >
                                {isMobileMenuOpen ? <CloseIcon /> : <MenuIcon />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Mobile menu - osu! style slide down */}
                <AnimatePresence>
                    {isMobileMenuOpen && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
                            className="md:hidden border-t border-white/10 bg-dark-600"
                            id="mobile-menu"
                            role="menu"
                            aria-label="Mobile navigation menu"
                        >
                            <div className="px-3 pt-3 pb-4 space-y-1">
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
                                                `flex items-center gap-3 px-4 py-3 rounded-lg text-base font-medium transition-colors ${isActive
                                                    ? 'bg-white/10 text-white'
                                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
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
                            <div className="px-3 pt-3 pb-4 border-t border-white/10">
                                {isAuthenticated ? (
                                    <div className="space-y-2">
                                        <Link
                                            to="/upload"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="flex items-center gap-3 px-4 py-3 rounded-lg 
                                                     bg-primary-400 text-white font-medium"
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
                                            className="block px-4 py-3 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                        >
                                            Profile
                                        </Link>
                                        <Link
                                            to="/settings"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                        >
                                            Settings
                                        </Link>
                                        <button
                                            onClick={() => {
                                                setShowMobileSignOutConfirm(true)
                                                setIsMobileMenuOpen(false)
                                            }}
                                            className="block w-full text-left px-4 py-3 rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
                                        >
                                            Sign out
                                        </button>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <Link
                                            to="/login"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block px-4 py-3 rounded-lg bg-primary-400 text-white text-center font-medium"
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
            <div className="h-14" />

            {/* Main content */}
            <main
                id={SKIP_LINK_TARGETS.MAIN_CONTENT}
                className="flex-1 w-full overflow-x-hidden"
                tabIndex={-1}
            >
                {children}
            </main>

            {/* Footer - osu! inspired clean footer */}
            <footer className="relative z-20 bg-dark-600 border-t border-white/5 mt-auto" role="contentinfo">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                        {/* Logo and copyright */}
                        <div className="flex flex-col sm:flex-row items-center gap-3">
                            <div className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded bg-dark-400 border border-white/10 
                                              flex items-center justify-center overflow-hidden">
                                    <img src="/icons/logo-navbar.png" alt="" className="w-4 h-4" />
                                </div>
                                <span className="text-gray-500 text-sm">
                                    © 2025 BeatSight
                                </span>
                            </div>
                            <span className="hidden sm:inline text-gray-600">•</span>
                            <span className="text-gray-600 text-xs">
                                The global index for drum transcriptions
                            </span>
                        </div>

                        {/* Links */}
                        <nav className="flex items-center gap-6" aria-label="Footer navigation">
                            <a
                                href={getDocsLink()}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-gray-500 hover:text-primary-400 text-sm transition-colors"
                            >
                                Docs
                            </a>
                            <a
                                href={getCommunityLink()}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-gray-500 hover:text-primary-400 text-sm transition-colors"
                            >
                                Support
                            </a>
                            <a
                                href={EXTERNAL_LINKS.github.org}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-gray-500 hover:text-primary-400 text-sm transition-colors"
                            >
                                GitHub
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
                    forceUnlockBodyScroll()
                    setShowMobileSignOutConfirm(false)
                    logout()
                    navigate('/', { replace: true })
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
