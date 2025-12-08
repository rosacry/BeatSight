/**
 * User menu dropdown component.
 * Shows user info and logout option with smooth animations.
 */

import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { ConfirmDialog } from './ConfirmDialog'

export function UserMenu() {
    const { user, logout } = useAuthStore()
    const [isOpen, setIsOpen] = useState(false)
    const [showSignOutConfirm, setShowSignOutConfirm] = useState(false)
    const menuRef = useRef<HTMLDivElement>(null)

    // Close menu when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    if (!user) {
        return null
    }

    const handleLogout = () => {
        setShowSignOutConfirm(true)
        setIsOpen(false)
    }

    const confirmLogout = () => {
        logout()
        setShowSignOutConfirm(false)
    }

    // Get initials for avatar
    const initials = user.display_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)

    const menuItems = [
        { to: '/profile', label: 'Your Profile' },
        { to: '/settings', label: 'Settings' },
        { to: '/library', label: 'My Library' },
    ]

    return (
        <div className="relative" ref={menuRef}>
            <motion.button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 rounded-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-800"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={{ duration: 0.15 }}
            >
                <div className="w-9 h-9 bg-primary-600 rounded-full flex items-center justify-center transition-shadow hover:shadow-lg hover:shadow-primary-500/25">
                    <span className="text-white text-sm font-medium">{initials}</span>
                </div>
            </motion.button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -10 }}
                        transition={{ duration: 0.15, ease: [0.4, 0, 0.2, 1] }}
                        className="absolute right-0 mt-2 w-56 bg-gray-800/95 backdrop-blur-xl rounded-xl shadow-xl border border-gray-700/50 py-1 z-50 overflow-hidden"
                    >
                        {/* User info */}
                        <div className="px-4 py-3 border-b border-gray-700/50">
                            <p className="text-sm font-medium text-white truncate">{user.display_name}</p>
                            <p className="text-xs text-gray-400 truncate">{user.email}</p>
                        </div>

                        {/* Menu items */}
                        <div className="py-1">
                            {menuItems.map((item, index) => (
                                <motion.div
                                    key={item.to}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05, duration: 0.15 }}
                                >
                                    <Link
                                        to={item.to}
                                        onClick={() => setIsOpen(false)}
                                        className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700/50 hover:text-white transition-colors"
                                    >
                                        {item.label}
                                    </Link>
                                </motion.div>
                            ))}
                        </div>

                        {/* Karma display */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.15 }}
                            className="px-4 py-2 border-t border-gray-700/50"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-gray-400">Karma</span>
                                <span className="text-sm font-medium text-primary-400">{user.karma_score}</span>
                            </div>
                        </motion.div>

                        {/* Logout */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.2 }}
                            className="border-t border-gray-700/50 py-1"
                        >
                            <button
                                onClick={handleLogout}
                                className="block w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors"
                            >
                                Sign out
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Sign out confirmation dialog */}
            <ConfirmDialog
                isOpen={showSignOutConfirm}
                onClose={() => setShowSignOutConfirm(false)}
                onConfirm={confirmLogout}
                title="Sign out?"
                message="Are you sure you want to sign out of BeatSight?"
                confirmLabel="Sign out"
                cancelLabel="Stay signed in"
                variant="warning"
            />
        </div>
    )
}
