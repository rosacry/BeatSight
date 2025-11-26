/**
 * User menu dropdown component.
 * Shows user info and logout option.
 */

import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

export function UserMenu() {
    const { user, logout } = useAuthStore()
    const [isOpen, setIsOpen] = useState(false)
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
        logout()
        setIsOpen(false)
    }

    // Get initials for avatar
    const initials = user.display_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)

    return (
        <div className="relative" ref={menuRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 rounded-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-800"
            >
                <div className="w-9 h-9 bg-primary-600 rounded-full flex items-center justify-center">
                    <span className="text-white text-sm font-medium">{initials}</span>
                </div>
            </button>

            {isOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-gray-800 rounded-lg shadow-xl border border-gray-700 py-1 z-50">
                    {/* User info */}
                    <div className="px-4 py-3 border-b border-gray-700">
                        <p className="text-sm font-medium text-white truncate">{user.display_name}</p>
                        <p className="text-xs text-gray-400 truncate">{user.email}</p>
                    </div>

                    {/* Menu items */}
                    <div className="py-1">
                        <Link
                            to="/profile"
                            onClick={() => setIsOpen(false)}
                            className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white"
                        >
                            Your Profile
                        </Link>
                        <Link
                            to="/settings"
                            onClick={() => setIsOpen(false)}
                            className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white"
                        >
                            Settings
                        </Link>
                        <Link
                            to="/library"
                            onClick={() => setIsOpen(false)}
                            className="block px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white"
                        >
                            My Library
                        </Link>
                    </div>

                    {/* Karma display */}
                    <div className="px-4 py-2 border-t border-gray-700">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-gray-400">Karma</span>
                            <span className="text-sm font-medium text-primary-400">{user.karma_score}</span>
                        </div>
                    </div>

                    {/* Logout */}
                    <div className="border-t border-gray-700 py-1">
                        <button
                            onClick={handleLogout}
                            className="block w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-gray-700 hover:text-red-300"
                        >
                            Sign out
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
