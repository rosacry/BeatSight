/**
 * Global Search Component - osu! inspired unified search experience.
 * 
 * Searches across:
 * - Users (players)
 * - Beatmaps
 * - Forum topics
 * - Documentation (via docs link)
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useGlobalSearch } from '@/api/searchHooks'
import { Avatar } from '@/components/ui/Avatar'
import type { UserSearchItem, MapSearchItem, ForumSearchItem } from '@/api/search'

// =============================================================================
// Icons
// =============================================================================

function SearchIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
    )
}

function CloseIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

function UserIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
    )
}

function MapIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
    )
}

function ForumIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
        </svg>
    )
}

function DocsIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
    )
}

function ChevronRightIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
    )
}

function StarIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
    )
}

function VerifiedIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 24 24">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
        </svg>
    )
}

// =============================================================================
// Search Trigger Button (for header)
// =============================================================================

interface SearchTriggerProps {
    onClick: () => void
}

export function SearchTrigger({ onClick }: SearchTriggerProps) {
    return (
        <button
            onClick={onClick}
            className="flex items-center gap-2 px-3 py-1.5 bg-dark-400 hover:bg-dark-300 
                     border border-white/10 rounded-lg text-gray-400 hover:text-white
                     transition-all duration-200 group"
            aria-label="Open search"
        >
            <SearchIcon className="w-4 h-4" />
            <span className="hidden sm:inline text-sm">Search</span>
            <kbd className="hidden md:inline-flex items-center px-1.5 py-0.5 text-xs 
                          bg-dark-500 rounded border border-white/10 text-gray-500
                          group-hover:text-gray-400 transition-colors">
                /
            </kbd>
        </button>
    )
}

// =============================================================================
// Global Search Modal
// =============================================================================

interface GlobalSearchModalProps {
    isOpen: boolean
    onClose: () => void
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
    const [query, setQuery] = useState('')
    const inputRef = useRef<HTMLInputElement>(null)
    const navigate = useNavigate()

    const { data: searchResults, isLoading } = useGlobalSearch(query, query.length >= 1)

    // Focus input when modal opens
    useEffect(() => {
        if (isOpen) {
            // Small delay to ensure modal is rendered
            setTimeout(() => inputRef.current?.focus(), 50)
        } else {
            setQuery('')
        }
    }, [isOpen])

    // Keyboard shortcut to open search
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            // Open search with / key
            if (e.key === '/' && !isOpen && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
                e.preventDefault()
                // Parent component should handle this
            }
            // Close with Escape
            if (e.key === 'Escape' && isOpen) {
                onClose()
            }
        }

        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, onClose])

    // Handle clicking a result
    const handleResultClick = useCallback(() => {
        onClose()
    }, [onClose])

    // Handle "view more" navigation
    const handleViewMore = (type: 'users' | 'maps' | 'forum') => {
        onClose()
        navigate(`/search?q=${encodeURIComponent(query)}&tab=${type}`)
    }

    if (!isOpen) return null

    return (
        <AnimatePresence>
            {/* Backdrop - click to close */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={onClose}
                className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50"
            />

            {/* Modal - centered like osu! */}
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.15, ease: 'easeOut' }}
                className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4 pointer-events-none"
            >
                <div className="bg-dark-500 border border-white/10 rounded-xl shadow-2xl overflow-hidden w-full max-w-2xl pointer-events-auto">
                    {/* Search Input - osu! style centered */}
                    <div className="flex items-center gap-3 px-5 py-4 border-b border-white/5">
                        <SearchIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search for users, beatmaps, forums..."
                            className="flex-1 bg-transparent text-white text-lg placeholder-gray-500 
                                     focus:outline-none"
                            autoComplete="off"
                            spellCheck={false}
                        />
                        <button
                            onClick={onClose}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 
                                     transition-colors"
                            aria-label="Close search"
                        >
                            <CloseIcon className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Results */}
                    <div className="max-h-[60vh] overflow-y-auto">
                        {/* Loading State */}
                        {isLoading && query.length >= 1 && (
                            <div className="flex items-center justify-center p-8">
                                <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                            </div>
                        )}

                        {/* Empty State */}
                        {!isLoading && query.length >= 1 && searchResults &&
                            searchResults.users.length === 0 &&
                            searchResults.maps.length === 0 &&
                            searchResults.forum_topics.length === 0 && (
                                <div className="p-8 text-center text-gray-400">
                                    <SearchIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p className="text-lg">No results found</p>
                                    <p className="text-sm mt-1">Try a different search term</p>
                                </div>
                            )}

                        {/* Initial State */}
                        {query.length === 0 && (
                            <div className="p-6">
                                <p className="text-gray-400 text-sm mb-4">Quick Links</p>
                                <div className="grid grid-cols-2 gap-2">
                                    <Link
                                        to="/queue"
                                        onClick={handleResultClick}
                                        className="flex items-center gap-3 p-3 rounded-lg bg-dark-400 hover:bg-dark-300 transition-colors"
                                    >
                                        <MapIcon className="w-5 h-5 text-primary-400" />
                                        <span className="text-white">Browse Maps</span>
                                    </Link>
                                    <Link
                                        to="/leaderboard"
                                        onClick={handleResultClick}
                                        className="flex items-center gap-3 p-3 rounded-lg bg-dark-400 hover:bg-dark-300 transition-colors"
                                    >
                                        <UserIcon className="w-5 h-5 text-yellow-400" />
                                        <span className="text-white">Leaderboards</span>
                                    </Link>
                                    <Link
                                        to="/forum"
                                        onClick={handleResultClick}
                                        className="flex items-center gap-3 p-3 rounded-lg bg-dark-400 hover:bg-dark-300 transition-colors"
                                    >
                                        <ForumIcon className="w-5 h-5 text-accent-400" />
                                        <span className="text-white">Forum</span>
                                    </Link>
                                    <a
                                        href="https://docs.beatsight.io"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={handleResultClick}
                                        className="flex items-center gap-3 p-3 rounded-lg bg-dark-400 hover:bg-dark-300 transition-colors"
                                    >
                                        <DocsIcon className="w-5 h-5 text-green-400" />
                                        <span className="text-white">Documentation</span>
                                    </a>
                                </div>
                            </div>
                        )}

                        {/* Search Results */}
                        {!isLoading && searchResults && query.length >= 1 && (
                            <div className="divide-y divide-white/5">
                                {/* Beatmap Results */}
                                {searchResults.maps.length > 0 && (
                                    <SearchSection
                                        title="Beatmap"
                                        icon={<MapIcon className="w-4 h-4" />}
                                        totalCount={searchResults.maps_total}
                                        onViewMore={() => handleViewMore('maps')}
                                    >
                                        {searchResults.maps.map((map) => (
                                            <MapResultItem
                                                key={map.id}
                                                map={map}
                                                onClick={handleResultClick}
                                            />
                                        ))}
                                    </SearchSection>
                                )}

                                {/* User Results */}
                                {searchResults.users.length > 0 && (
                                    <SearchSection
                                        title="Player"
                                        icon={<UserIcon className="w-4 h-4" />}
                                        totalCount={searchResults.users_total}
                                        onViewMore={() => handleViewMore('users')}
                                    >
                                        {searchResults.users.map((user) => (
                                            <UserResultItem
                                                key={user.id}
                                                user={user}
                                                onClick={handleResultClick}
                                            />
                                        ))}
                                    </SearchSection>
                                )}

                                {/* Forum Results */}
                                {searchResults.forum_topics.length > 0 && (
                                    <SearchSection
                                        title="Forum"
                                        icon={<ForumIcon className="w-4 h-4" />}
                                        totalCount={searchResults.forum_topics_total}
                                        onViewMore={() => handleViewMore('forum')}
                                    >
                                        {searchResults.forum_topics.map((topic) => (
                                            <ForumResultItem
                                                key={topic.id}
                                                topic={topic}
                                                onClick={handleResultClick}
                                            />
                                        ))}
                                    </SearchSection>
                                )}

                                {/* Docs Link */}
                                <SearchSection
                                    title="Other"
                                    icon={<DocsIcon className="w-4 h-4" />}
                                >
                                    <a
                                        href={`https://docs.beatsight.io/search?q=${encodeURIComponent(query)}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={handleResultClick}
                                        className="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors"
                                    >
                                        <DocsIcon className="w-5 h-5 text-green-400 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-white font-medium">Search Documentation</p>
                                            <p className="text-sm text-gray-400 truncate">
                                                Find "{query}" in docs
                                            </p>
                                        </div>
                                        <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                                    </a>
                                </SearchSection>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="px-4 py-3 border-t border-white/10 bg-dark-600/50">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                            <div className="flex items-center gap-4">
                                <span className="flex items-center gap-1">
                                    <kbd className="px-1.5 py-0.5 bg-dark-400 rounded border border-white/10">↵</kbd>
                                    to select
                                </span>
                                <span className="flex items-center gap-1">
                                    <kbd className="px-1.5 py-0.5 bg-dark-400 rounded border border-white/10">esc</kbd>
                                    to close
                                </span>
                            </div>
                            <span>Powered by BeatSight Search</span>
                        </div>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    )
}

// =============================================================================
// Search Section Component
// =============================================================================

interface SearchSectionProps {
    title: string
    icon: React.ReactNode
    totalCount?: number
    onViewMore?: () => void
    children: React.ReactNode
}

function SearchSection({ title, icon, totalCount, onViewMore, children }: SearchSectionProps) {
    return (
        <div className="py-3">
            {/* Section Header */}
            <div className="flex items-center justify-between px-4 mb-2">
                <div className="flex items-center gap-2 text-sm font-medium text-primary-400">
                    {icon}
                    <span>{title} Search Results</span>
                </div>
                {totalCount !== undefined && totalCount > 5 && onViewMore && (
                    <button
                        onClick={onViewMore}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-primary-400 transition-colors"
                    >
                        <span>More {title} Search Results</span>
                        <span className="px-1.5 py-0.5 bg-dark-400 rounded text-gray-500">
                            {totalCount.toLocaleString()}
                        </span>
                        <ChevronRightIcon className="w-3 h-3" />
                    </button>
                )}
            </div>

            {/* Results */}
            <div className="px-2">{children}</div>
        </div>
    )
}

// =============================================================================
// Result Item Components
// =============================================================================

interface UserResultItemProps {
    user: UserSearchItem
    onClick?: () => void
}

function UserResultItem({ user, onClick }: UserResultItemProps) {
    return (
        <Link
            to={`/user/${user.id}`}
            onClick={onClick}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors"
        >
            <Avatar
                src={user.avatar_url || undefined}
                alt={user.display_name}
                size="sm"
            />
            <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{user.display_name}</p>
            </div>
            <div className="flex items-center gap-1 text-yellow-400 text-sm">
                <StarIcon className="w-3.5 h-3.5" />
                <span>{user.karma_score.toLocaleString()}</span>
            </div>
        </Link>
    )
}

interface MapResultItemProps {
    map: MapSearchItem
    onClick?: () => void
}

function MapResultItem({ map, onClick }: MapResultItemProps) {
    return (
        <Link
            to={`/songs/${map.song_id}`}
            onClick={onClick}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors"
        >
            {/* Cover Image */}
            <div className="w-12 h-12 rounded-lg bg-dark-400 overflow-hidden flex-shrink-0">
                {map.cover_url ? (
                    <img
                        src={map.cover_url}
                        alt={map.title}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center">
                        <MapIcon className="w-5 h-5 text-gray-500" />
                    </div>
                )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <p className="text-white font-medium truncate">{map.title}</p>
                    {map.is_verified && (
                        <span className="flex items-center gap-0.5 px-1.5 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                            <VerifiedIcon className="w-3 h-3" />
                        </span>
                    )}
                </div>
                <p className="text-sm text-gray-400 truncate">
                    {map.artist} • mapped by <span className="text-primary-400">{map.creator_name}</span>
                </p>
            </div>
        </Link>
    )
}

interface ForumResultItemProps {
    topic: ForumSearchItem
    onClick?: () => void
}

function ForumResultItem({ topic, onClick }: ForumResultItemProps) {
    return (
        <Link
            to={`/forum/${topic.forum_slug}/${topic.id}`}
            onClick={onClick}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5 transition-colors"
        >
            <div className="w-10 h-10 rounded-lg bg-dark-400 flex items-center justify-center flex-shrink-0">
                <ForumIcon className="w-5 h-5 text-accent-400" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{topic.title}</p>
                <p className="text-sm text-gray-400 truncate">
                    {topic.forum_name} • by {topic.author_name}
                </p>
            </div>
            <div className="text-xs text-gray-500">
                {topic.post_count} posts
            </div>
        </Link>
    )
}

export default GlobalSearchModal
