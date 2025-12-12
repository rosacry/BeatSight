/**
 * Navigation shell component - osu! inspired design.
 * Features:
 * - Balanced header with dropdown menus on hover
 * - Clean glassmorphism effects
 * - Smooth animations
 * - Responsive mobile menu
 */

import { useState, useEffect, useRef } from 'react'
import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { UserMenu } from './UserMenu'
import { CreditBalance } from './CreditBalance'
import { ConfirmDialog } from './ConfirmDialog'
import { GlobalSearchModal, SearchTrigger } from './GlobalSearch'
import { EXTERNAL_LINKS, getDocsLink, getCommunityLink } from '@/lib/externalLinks'
import { SKIP_LINK_TARGETS, ARIA_LABELS } from '@/lib/accessibility'
import { TRANSITION_DURATION, EASE_CURVE } from '@/components/ui/UnifiedTransitions'

interface LayoutProps {
    children: React.ReactNode
}

// =============================================================================
// Icons (smaller 4x4 for compact nav)
// =============================================================================

function HomeIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
    )
}

function BeatmapsIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
    )
}

function LeaderboardIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
    )
}

function ForumIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
        </svg>
    )
}

function MessagesIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
    )
}

function QueueIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
    )
}

function MicIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
    )
}

function LibraryIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
    )
}

function AdminIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
    )
}

function VerifyIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function ChevronDownIcon() {
    return (
        <svg className="w-3 h-3 ml-1 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
    )
}

function DocsIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
    )
}

function SupportIcon() {
    return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
    )
}

function GitHubIcon() {
    return (
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
        </svg>
    )
}

// =============================================================================
// Dropdown Menu Component (osu!-style)
// =============================================================================

interface DropdownItem {
    path?: string
    href?: string
    label: string
    icon?: React.ReactNode
    requiresAuth?: boolean
    external?: boolean
}

interface DropdownMenuProps {
    label: string
    items: DropdownItem[]
    isActive?: boolean
}

function DropdownMenu({ label, items, isActive }: DropdownMenuProps) {
    const [isOpen, setIsOpen] = useState(false)
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())

    const handleMouseEnter = () => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
        }
        setIsOpen(true)
    }

    const handleMouseLeave = () => {
        timeoutRef.current = setTimeout(() => {
            setIsOpen(false)
        }, 150)
    }

    // Filter items based on auth
    const visibleItems = items.filter(item => !item.requiresAuth || isAuthenticated)

    if (visibleItems.length === 0) return null

    return (
        <div
            className="relative"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <button
                className={`flex items-center gap-1 px-3 py-2 text-sm font-medium transition-colors ${isActive || isOpen
                    ? 'text-white'
                    : 'text-gray-400 hover:text-white'
                    }`}
            >
                {label}
                <ChevronDownIcon />
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.15, ease: 'easeOut' }}
                        className="absolute top-full left-0 mt-1 min-w-[160px] bg-dark-500 border border-white/10 rounded-lg shadow-xl overflow-hidden z-[60]"
                        style={{ pointerEvents: 'auto' }}
                    >
                        <div className="py-1">
                            {visibleItems.map((item, index) => (
                                item.external || item.href ? (
                                    <a
                                        key={index}
                                        href={item.href || item.path}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                                        onClick={() => setIsOpen(false)}
                                    >
                                        {item.icon}
                                        {item.label}
                                    </a>
                                ) : (
                                    <Link
                                        key={index}
                                        to={item.path || '/'}
                                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                                        onClick={() => setIsOpen(false)}
                                    >
                                        {item.icon}
                                        {item.label}
                                    </Link>
                                )
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

// =============================================================================
// Mobile Nav Link Component
// =============================================================================

interface MobileNavLinkProps {
    to: string
    icon: React.ReactNode
    label: string
    onClick: () => void
}

function MobileNavLink({ to, icon, label, onClick }: MobileNavLinkProps) {
    return (
        <NavLink
            to={to}
            onClick={onClick}
            className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-base font-medium transition-colors ${isActive
                    ? 'bg-white/10 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`
            }
        >
            {icon}
            {label}
        </NavLink>
    )
}
// =============================================================================
// Main Layout Component
// =============================================================================

export function Layout({ children }: LayoutProps) {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const isAdmin = useAuthStore((state) => state.isAdmin())
    const isStaff = useAuthStore((state) => state.isStaff())
    const isVerifier = useAuthStore((state) => state.isVerifier())
    const logout = useAuthStore((state) => state.logout)
    const navigate = useNavigate()
    const location = useLocation()
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
    const [isScrolled, setIsScrolled] = useState(false)
    const [showMobileSignOutConfirm, setShowMobileSignOutConfirm] = useState(false)
    const [isSearchOpen, setIsSearchOpen] = useState(false)

    // Keyboard shortcut to open search with / key
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            if (e.key === '/' && !isSearchOpen && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
                e.preventDefault()
                setIsSearchOpen(true)
            }
        }
        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [isSearchOpen])

    // Track scroll for header effects
    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 10)
        }
        window.addEventListener('scroll', handleScroll, { passive: true })
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    // Check if current path is in a dropdown group
    const isInBrowse = ['/', '/queue'].some(p => location.pathname === p || location.pathname.startsWith('/songs'))
    const isInRankings = ['/leaderboard'].some(p => location.pathname.startsWith(p))
    const isInCommunity = ['/forum', '/messages'].some(p => location.pathname.startsWith(p))

    return (
        <div className="min-h-screen bg-dark-500 flex flex-col relative overflow-x-hidden">
            {/* Skip to main content link for screen readers */}
            <a
                href={`#${SKIP_LINK_TARGETS.MAIN_CONTENT}`}
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-primary-400 focus:text-white focus:px-4 focus:py-2 focus:rounded-md focus:outline-none focus:ring-2 focus:ring-white"
            >
                Skip to main content
            </a>

            {/* Navigation - osu! inspired header with dropdowns */}
            <motion.nav
                initial={{ y: -100 }}
                animate={{ y: 0 }}
                transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${isScrolled
                    ? 'bg-dark-600/95 backdrop-blur-md shadow-lg border-b border-white/5'
                    : 'bg-dark-600/90 backdrop-blur-sm'
                    }`}
                id={SKIP_LINK_TARGETS.NAVIGATION}
                aria-label="Main navigation"
            >
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-14">
                        {/* Left: Logo + Main Navigation */}
                        <div className="flex items-center gap-1">
                            {/* Logo */}
                            <Link to="/" className="flex items-center gap-2 group mr-4">
                                <motion.div
                                    className="relative"
                                    whileHover={{ scale: 1.02 }}
                                    transition={{ type: 'spring', stiffness: 400 }}
                                >
                                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 
                                                  flex items-center justify-center overflow-hidden
                                                  shadow-md shadow-primary-500/20
                                                  group-hover:shadow-lg group-hover:shadow-primary-500/30 transition-shadow">
                                        <img
                                            src="/icons/logo-navbar.png"
                                            alt="BeatSight"
                                            className="w-6 h-6"
                                        />
                                    </div>
                                </motion.div>
                                <span className="text-lg font-bold text-white hidden sm:block 
                                               group-hover:text-primary-400 transition-colors">
                                    BeatSight
                                </span>
                            </Link>

                            {/* Desktop Navigation - Dropdown menus like osu! */}
                            <div className="hidden md:flex items-center">
                                {/* Home (direct link) */}
                                <NavLink
                                    to="/"
                                    className={({ isActive }) =>
                                        `px-3 py-2 text-sm font-medium transition-colors ${isActive && location.pathname === '/'
                                            ? 'text-white'
                                            : 'text-gray-400 hover:text-white'
                                        }`
                                    }
                                >
                                    home
                                </NavLink>

                                {/* Beatmaps dropdown */}
                                <DropdownMenu
                                    label="beatmaps"
                                    isActive={isInBrowse && location.pathname !== '/'}
                                    items={[
                                        { path: '/queue', label: 'browse', icon: <BeatmapsIcon /> },
                                        { path: '/library', label: 'my library', icon: <LibraryIcon />, requiresAuth: true },
                                    ]}
                                />

                                {/* Rankings dropdown - direct link since only one item */}
                                <NavLink
                                    to="/leaderboard"
                                    className={({ isActive }) =>
                                        `px-3 py-2 text-sm font-medium transition-colors ${isActive
                                            ? 'text-white'
                                            : 'text-gray-400 hover:text-white'
                                        }`
                                    }
                                >
                                    rankings
                                </NavLink>

                                {/* Community dropdown */}
                                <DropdownMenu
                                    label="community"
                                    isActive={isInCommunity}
                                    items={[
                                        { path: '/forum', label: 'forums', icon: <ForumIcon /> },
                                        { path: '/messages', label: 'messages', icon: <MessagesIcon />, requiresAuth: true },
                                    ]}
                                />

                                {/* Help dropdown */}
                                <DropdownMenu
                                    label="help"
                                    items={[
                                        { href: getDocsLink(), label: 'documentation', icon: <DocsIcon />, external: true },
                                        { href: getCommunityLink(), label: 'support', icon: <SupportIcon />, external: true },
                                        { href: EXTERNAL_LINKS.github.org, label: 'github', icon: <GitHubIcon />, external: true },
                                    ]}
                                />

                                {/* Staff-only items */}
                                {(isVerifier || isStaff || isAdmin) && (
                                    <DropdownMenu
                                        label="staff"
                                        items={[
                                            ...(isVerifier ? [{ path: '/verifier', label: 'verify maps', icon: <VerifyIcon /> }] : []),
                                            ...((isStaff || isAdmin) ? [{ path: '/admin', label: 'admin panel', icon: <AdminIcon /> }] : []),
                                        ]}
                                    />
                                )}
                            </div>
                        </div>

                        {/* Right: Actions */}
                        <div className="flex items-center gap-2">
                            {/* Search */}
                            <SearchTrigger onClick={() => setIsSearchOpen(true)} />

                            {/* Desktop auth section */}
                            <div className="hidden md:flex items-center gap-2">
                                {isAuthenticated ? (
                                    <>
                                        {/* Create/Upload buttons */}
                                        <div className="flex items-center gap-1 mr-1">
                                            <Link
                                                to="/record"
                                                className="flex items-center gap-1.5 px-3 py-1.5 
                                                         text-sm text-gray-400 hover:text-white
                                                         transition-colors"
                                            >
                                                <MicIcon />
                                                <span className="hidden xl:inline">Record</span>
                                            </Link>
                                            <Link
                                                to="/upload"
                                                className="flex items-center gap-1.5 px-3 py-1.5 
                                                         bg-primary-500 hover:bg-primary-400
                                                         text-white font-medium rounded-lg
                                                         shadow-sm hover:shadow-md hover:shadow-primary-500/20
                                                         transition-all duration-200"
                                            >
                                                <UploadIcon />
                                                <span>Upload</span>
                                            </Link>
                                        </div>
                                        <CreditBalance showWhenZero />
                                        <UserMenu />
                                    </>
                                ) : (
                                    <>
                                        <Link
                                            to="/login"
                                            className="text-gray-400 hover:text-white px-3 py-2 
                                                     text-sm font-medium transition-colors"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            className="px-4 py-2 bg-primary-500 hover:bg-primary-400 
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

                {/* Mobile menu */}
                <AnimatePresence>
                    {isMobileMenuOpen && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                            className="md:hidden border-t border-white/10 bg-dark-600"
                            id="mobile-menu"
                            role="menu"
                            aria-label="Mobile navigation menu"
                        >
                            <div className="px-4 py-4 space-y-1">
                                {/* Main nav links */}
                                <MobileNavLink to="/" icon={<HomeIcon />} label="Home" onClick={() => setIsMobileMenuOpen(false)} />
                                <MobileNavLink to="/queue" icon={<QueueIcon />} label="Browse Beatmaps" onClick={() => setIsMobileMenuOpen(false)} />
                                <MobileNavLink to="/leaderboard" icon={<LeaderboardIcon />} label="Rankings" onClick={() => setIsMobileMenuOpen(false)} />
                                <MobileNavLink to="/forum" icon={<ForumIcon />} label="Forums" onClick={() => setIsMobileMenuOpen(false)} />

                                {isAuthenticated && (
                                    <>
                                        <div className="border-t border-white/10 my-3" />
                                        <MobileNavLink to="/library" icon={<LibraryIcon />} label="My Library" onClick={() => setIsMobileMenuOpen(false)} />
                                        <MobileNavLink to="/messages" icon={<MessagesIcon />} label="Messages" onClick={() => setIsMobileMenuOpen(false)} />
                                        <MobileNavLink to="/record" icon={<MicIcon />} label="Record" onClick={() => setIsMobileMenuOpen(false)} />

                                        {(isVerifier || isStaff || isAdmin) && (
                                            <>
                                                <div className="border-t border-white/10 my-3" />
                                                {isVerifier && <MobileNavLink to="/verifier" icon={<VerifyIcon />} label="Verify Maps" onClick={() => setIsMobileMenuOpen(false)} />}
                                                {(isStaff || isAdmin) && <MobileNavLink to="/admin" icon={<AdminIcon />} label="Admin Panel" onClick={() => setIsMobileMenuOpen(false)} />}
                                            </>
                                        )}
                                    </>
                                )}
                            </div>

                            {/* Mobile auth section */}
                            <div className="px-4 py-4 border-t border-white/10">
                                {isAuthenticated ? (
                                    <div className="space-y-3">
                                        <Link
                                            to="/upload"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg 
                                                     bg-primary-500 text-white font-medium"
                                        >
                                            <UploadIcon />
                                            Upload Song
                                        </Link>
                                        <div className="flex items-center justify-between px-2">
                                            <CreditBalance showWhenZero />
                                        </div>
                                        <div className="flex gap-2">
                                            <Link
                                                to="/profile"
                                                onClick={() => setIsMobileMenuOpen(false)}
                                                className="flex-1 text-center px-4 py-2.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                            >
                                                Profile
                                            </Link>
                                            <Link
                                                to="/settings"
                                                onClick={() => setIsMobileMenuOpen(false)}
                                                className="flex-1 text-center px-4 py-2.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                                            >
                                                Settings
                                            </Link>
                                        </div>
                                        <button
                                            onClick={() => {
                                                setShowMobileSignOutConfirm(true)
                                                setIsMobileMenuOpen(false)
                                            }}
                                            className="w-full text-center px-4 py-2.5 rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
                                        >
                                            Sign out
                                        </button>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <Link
                                            to="/register"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block w-full px-4 py-3 rounded-lg bg-primary-500 text-white text-center font-medium"
                                        >
                                            Sign up
                                        </Link>
                                        <Link
                                            to="/login"
                                            onClick={() => setIsMobileMenuOpen(false)}
                                            className="block w-full px-4 py-3 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 text-center transition-colors"
                                        >
                                            Sign in
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
                    // Close the dialog first and let React clean it up properly
                    setShowMobileSignOutConfirm(false)
                    // Close mobile menu too
                    setIsMobileMenuOpen(false)

                    // Use requestAnimationFrame to ensure dialogs have time to unmount
                    // before we trigger the navigation and auth state change
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            logout()
                            navigate('/', { replace: true })
                        })
                    })
                }}
                title="Sign out"
                message="Are you sure you want to sign out of BeatSight?"
                confirmLabel="Sign out"
                cancelLabel="Stay signed in"
                variant="signout"
                style="popup"
            />

            {/* Global Search Modal */}
            <GlobalSearchModal
                isOpen={isSearchOpen}
                onClose={() => setIsSearchOpen(false)}
            />
        </div>
    )
}
