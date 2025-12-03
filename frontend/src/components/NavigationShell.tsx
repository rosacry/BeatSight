/**
 * Navigation shell component.
 * Full-featured app shell with responsive navigation.
 */

import { useState } from 'react'
import { Link, useLocation, NavLink } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { UserMenu } from './UserMenu'
import { CreditBalance } from './CreditBalance'

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
    { path: '/queue', label: 'Job Queue', icon: <QueueIcon /> },
    { path: '/record', label: 'Record', requiresAuth: true, icon: <MicIcon /> },
    { path: '/library', label: 'My Library', requiresAuth: true, icon: <LibraryIcon /> },
]

function HomeIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
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

export function Layout({ children }: LayoutProps) {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

    // Filter nav items based on auth state
    const visibleNavItems = navItems.filter(
        (item) => !item.requiresAuth || isAuthenticated
    )

    return (
        <div className="min-h-screen bg-gray-900 flex flex-col">
            {/* Desktop Navigation */}
            <nav className="bg-gray-800 border-b border-gray-700">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        {/* Logo and main nav */}
                        <div className="flex items-center">
                            <Link to="/" className="flex items-center gap-2">
                                <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                                    <span className="text-white font-bold">B</span>
                                </div>
                                <span className="text-xl font-bold text-white hidden sm:block">BeatSight</span>
                            </Link>

                            {/* Desktop nav links */}
                            <div className="hidden md:flex ml-10 items-center gap-1">
                                {visibleNavItems.map((item) => (
                                    <NavLink
                                        key={item.path}
                                        to={item.path}
                                        className={({ isActive }) =>
                                            `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive
                                                ? 'bg-gray-700 text-white'
                                                : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
                                            }`
                                        }
                                    >
                                        {item.icon}
                                        {item.label}
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
                                            className="btn btn-primary flex items-center gap-2"
                                        >
                                            <UploadIcon />
                                            <span className="hidden lg:inline">Upload Song</span>
                                        </Link>
                                        <CreditBalance />
                                        <UserMenu />
                                    </>
                                ) : (
                                    <>
                                        <Link
                                            to="/login"
                                            className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
                                        >
                                            Sign in
                                        </Link>
                                        <Link
                                            to="/register"
                                            className="btn btn-primary"
                                        >
                                            Sign up
                                        </Link>
                                    </>
                                )}
                            </div>

                            {/* Mobile menu button */}
                            <button
                                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                                className="md:hidden p-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            >
                                {isMobileMenuOpen ? <CloseIcon /> : <MenuIcon />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Mobile menu */}
                {isMobileMenuOpen && (
                    <div className="md:hidden border-t border-gray-700">
                        <div className="px-2 pt-2 pb-3 space-y-1">
                            {visibleNavItems.map((item) => (
                                <NavLink
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className={({ isActive }) =>
                                        `flex items-center gap-3 px-3 py-2 rounded-md text-base font-medium ${isActive
                                            ? 'bg-gray-700 text-white'
                                            : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
                                        }`
                                    }
                                >
                                    {item.icon}
                                    {item.label}
                                </NavLink>
                            ))}
                        </div>

                        {/* Mobile auth section */}
                        <div className="px-2 pt-2 pb-4 border-t border-gray-700">
                            {isAuthenticated ? (
                                <div className="space-y-2">
                                    <Link
                                        to="/upload"
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className="flex items-center gap-3 px-3 py-2 rounded-md text-base font-medium bg-primary-500 text-white"
                                    >
                                        <UploadIcon />
                                        Upload Song
                                    </Link>
                                    <div className="px-3 py-2">
                                        <CreditBalance showWhenZero />
                                    </div>
                                    <Link
                                        to="/profile"
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className="block px-3 py-2 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-gray-700/50"
                                    >
                                        Profile
                                    </Link>
                                    <Link
                                        to="/settings"
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className="block px-3 py-2 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-gray-700/50"
                                    >
                                        Settings
                                    </Link>
                                    <button
                                        onClick={() => {
                                            useAuthStore.getState().logout()
                                            setIsMobileMenuOpen(false)
                                        }}
                                        className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-red-400 hover:text-red-300 hover:bg-gray-700/50"
                                    >
                                        Sign out
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <Link
                                        to="/login"
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className="block px-3 py-2 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-gray-700/50"
                                    >
                                        Sign in
                                    </Link>
                                    <Link
                                        to="/register"
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className="block px-3 py-2 rounded-md text-base font-medium bg-primary-500 text-white text-center"
                                    >
                                        Sign up
                                    </Link>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </nav>

            {/* Breadcrumb (for nested pages) */}
            <Breadcrumb />

            {/* Main content */}
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>

            {/* Footer */}
            <footer className="bg-gray-800 border-t border-gray-700 mt-auto">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                        <p className="text-gray-400 text-sm">
                            © 2025 BeatSight. AI-powered drum beatmap generation.
                        </p>
                        <div className="flex items-center gap-6">
                            <a href="/docs" className="text-gray-400 hover:text-white text-sm">
                                Documentation
                            </a>
                            <a href="/support" className="text-gray-400 hover:text-white text-sm">
                                Support
                            </a>
                            <a href="https://github.com/beatsight" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white text-sm">
                                GitHub
                            </a>
                        </div>
                    </div>
                </div>
            </footer>
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
        <div className="bg-gray-850 border-b border-gray-700/50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
                <nav className="flex items-center gap-2 text-sm">
                    {breadcrumbs.map((crumb, index) => (
                        <span key={crumb.path} className="flex items-center gap-2">
                            {index > 0 && (
                                <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                            )}
                            {index === breadcrumbs.length - 1 ? (
                                <span className="text-gray-300">{crumb.label}</span>
                            ) : (
                                <Link
                                    to={crumb.path}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    {crumb.label}
                                </Link>
                            )}
                        </span>
                    ))}
                </nav>
            </div>
        </div>
    )
}
