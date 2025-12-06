/**
 * Command Palette (⌘K)
 * 
 * A premium command palette component for quick actions and navigation.
 * Inspired by VS Code, Linear, and Raycast command palettes.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// Types
// ============================================================================

export interface CommandItem {
    id: string;
    label: string;
    description?: string;
    icon?: React.ReactNode;
    shortcut?: string[];
    section?: string;
    keywords?: string[];
    onSelect: () => void;
    disabled?: boolean;
}

export interface CommandSection {
    id: string;
    label: string;
    items: CommandItem[];
}

export interface CommandPaletteProps {
    items: CommandItem[];
    placeholder?: string;
    emptyMessage?: string;
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    recentItems?: string[];
    onRecentItemsChange?: (ids: string[]) => void;
}

// ============================================================================
// Keyboard Shortcut Display
// ============================================================================

function KeyboardShortcut({ keys }: { keys: string[] }) {
    const isMac = navigator.platform.toLowerCase().includes('mac');

    const formatKey = (key: string) => {
        const keyMap: Record<string, string> = {
            'mod': isMac ? '⌘' : 'Ctrl',
            'ctrl': isMac ? '⌃' : 'Ctrl',
            'alt': isMac ? '⌥' : 'Alt',
            'shift': '⇧',
            'enter': '↵',
            'escape': 'Esc',
            'backspace': '⌫',
            'delete': '⌦',
            'tab': '⇥',
            'up': '↑',
            'down': '↓',
            'left': '←',
            'right': '→',
        };
        return keyMap[key.toLowerCase()] || key.toUpperCase();
    };

    return (
        <span className="flex items-center gap-1">
            {keys.map((key, index) => (
                <kbd
                    key={index}
                    className={cn(
                        'inline-flex items-center justify-center',
                        'min-w-[20px] px-1.5 py-0.5',
                        'text-[10px] font-medium text-gray-400',
                        'bg-gray-800 border border-gray-700 rounded',
                        'shadow-[0_1px_0_1px_rgba(0,0,0,0.2)]'
                    )}
                >
                    {formatKey(key)}
                </kbd>
            ))}
        </span>
    );
}

// ============================================================================
// Search Icon
// ============================================================================

function SearchIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
        </svg>
    );
}

// ============================================================================
// Command Palette Component
// ============================================================================

export function CommandPalette({
    items,
    placeholder = 'Type a command or search...',
    emptyMessage = 'No results found.',
    isOpen,
    onOpenChange,
    recentItems = [],
    onRecentItemsChange,
}: CommandPaletteProps) {
    const [search, setSearch] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

    // Filter and organize items
    const { filteredItems, sections } = useMemo(() => {
        const searchLower = search.toLowerCase().trim();

        // Filter items based on search
        const filtered = items.filter(item => {
            if (item.disabled) return false;
            if (!searchLower) return true;

            const matchLabel = item.label.toLowerCase().includes(searchLower);
            const matchDescription = item.description?.toLowerCase().includes(searchLower);
            const matchKeywords = item.keywords?.some(k => k.toLowerCase().includes(searchLower));

            return matchLabel || matchDescription || matchKeywords;
        });

        // If no search, prioritize recent items
        if (!searchLower && recentItems.length > 0) {
            const recentSet = new Set(recentItems);
            filtered.sort((a, b) => {
                const aRecent = recentSet.has(a.id) ? recentItems.indexOf(a.id) : Infinity;
                const bRecent = recentSet.has(b.id) ? recentItems.indexOf(b.id) : Infinity;
                return aRecent - bRecent;
            });
        }

        // Group by section
        const sectionMap = new Map<string, CommandItem[]>();

        // Add "Recent" section for recent items
        if (!searchLower && recentItems.length > 0) {
            const recentCommands = filtered.filter(item => recentItems.includes(item.id)).slice(0, 3);
            if (recentCommands.length > 0) {
                sectionMap.set('Recent', recentCommands);
            }
        }

        // Add other sections
        filtered.forEach(item => {
            const section = item.section || 'Commands';
            // Skip if already in recent (when not searching)
            if (!searchLower && recentItems.includes(item.id)) {
                return;
            }

            if (!sectionMap.has(section)) {
                sectionMap.set(section, []);
            }
            sectionMap.get(section)!.push(item);
        });

        const sectionsArray: CommandSection[] = Array.from(sectionMap.entries()).map(
            ([label, items]) => ({
                id: label,
                label,
                items,
            })
        );

        // Flatten for keyboard navigation
        const flatItems = sectionsArray.flatMap(s => s.items);

        return { filteredItems: flatItems, sections: sectionsArray };
    }, [items, search, recentItems]);

    // Reset selection when search changes
    useEffect(() => {
        setSelectedIndex(0);
    }, [search]);

    // Scroll selected item into view
    useEffect(() => {
        if (listRef.current) {
            const selectedElement = listRef.current.querySelector('[data-selected="true"]');
            if (selectedElement) {
                selectedElement.scrollIntoView({ block: 'nearest' });
            }
        }
    }, [selectedIndex]);

    // Focus input when opened
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => inputRef.current?.focus(), 0);
        } else {
            setSearch('');
            setSelectedIndex(0);
        }
    }, [isOpen]);

    // Handle item selection
    const handleSelect = useCallback((item: CommandItem) => {
        // Add to recent items
        if (onRecentItemsChange) {
            const newRecent = [item.id, ...recentItems.filter(id => id !== item.id)].slice(0, 5);
            onRecentItemsChange(newRecent);
        }

        onOpenChange(false);
        item.onSelect();
    }, [onOpenChange, recentItems, onRecentItemsChange]);

    // Keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(i => Math.min(i + 1, filteredItems.length - 1));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(i => Math.max(i - 1, 0));
                break;
            case 'Enter':
                e.preventDefault();
                if (filteredItems[selectedIndex]) {
                    handleSelect(filteredItems[selectedIndex]);
                }
                break;
            case 'Escape':
                e.preventDefault();
                onOpenChange(false);
                break;
        }
    }, [filteredItems, selectedIndex, handleSelect, onOpenChange]);

    // Track current item index across sections
    let itemIndex = -1;

    if (!isOpen) return null;

    const content = (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => onOpenChange(false)}
                        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
                    />

                    {/* Dialog */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -20 }}
                        transition={{ duration: 0.15 }}
                        className={cn(
                            'fixed left-1/2 top-[20%] z-50 -translate-x-1/2',
                            'w-full max-w-xl p-0 overflow-hidden rounded-xl',
                            'bg-gray-950/95 backdrop-blur-xl',
                            'border border-white/10',
                            'shadow-2xl shadow-black/50',
                        )}
                        role="dialog"
                        aria-modal="true"
                        aria-label="Command Palette"
                        onKeyDown={handleKeyDown}
                    >
                        {/* Search input */}
                        <div className="flex items-center gap-3 px-4 border-b border-white/10">
                            <SearchIcon className="text-gray-500 flex-shrink-0" />
                            <input
                                ref={inputRef}
                                type="text"
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                placeholder={placeholder}
                                className={cn(
                                    'flex-1 py-4 bg-transparent text-white',
                                    'placeholder:text-gray-500 text-sm',
                                    'focus:outline-none'
                                )}
                            />
                            <KeyboardShortcut keys={['Esc']} />
                        </div>

                        {/* Results */}
                        <div
                            ref={listRef}
                            className="max-h-[400px] overflow-y-auto overscroll-contain"
                        >
                            {sections.length === 0 ? (
                                <div className="py-12 text-center text-gray-500">
                                    {emptyMessage}
                                </div>
                            ) : (
                                <motion.div
                                    key={search}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ duration: 0.1 }}
                                >
                                    {sections.map(section => (
                                        <div key={section.id} className="py-2">
                                            <div className="px-4 py-1.5 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                {section.label}
                                            </div>
                                            {section.items.map(item => {
                                                itemIndex++;
                                                const isSelected = itemIndex === selectedIndex;
                                                const currentIndex = itemIndex;

                                                return (
                                                    <motion.button
                                                        key={item.id}
                                                        data-selected={isSelected}
                                                        onClick={() => handleSelect(item)}
                                                        onMouseEnter={() => setSelectedIndex(currentIndex)}
                                                        initial={{ opacity: 0, x: -10 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        transition={{ duration: 0.1, delay: currentIndex * 0.02 }}
                                                        className={cn(
                                                            'w-full flex items-center gap-3 px-4 py-2.5',
                                                            'text-left transition-colors duration-75',
                                                            isSelected
                                                                ? 'bg-cyan-500/20 text-white'
                                                                : 'text-gray-300 hover:bg-white/5',
                                                        )}
                                                    >
                                                        {/* Icon */}
                                                        {item.icon && (
                                                            <span className={cn(
                                                                'flex-shrink-0 w-5 h-5 flex items-center justify-center',
                                                                isSelected ? 'text-cyan-400' : 'text-gray-500'
                                                            )}>
                                                                {item.icon}
                                                            </span>
                                                        )}

                                                        {/* Label & Description */}
                                                        <div className="flex-1 min-w-0">
                                                            <div className="font-medium truncate">{item.label}</div>
                                                            {item.description && (
                                                                <div className="text-xs text-gray-500 truncate">
                                                                    {item.description}
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Shortcut */}
                                                        {item.shortcut && (
                                                            <KeyboardShortcut keys={item.shortcut} />
                                                        )}
                                                    </motion.button>
                                                );
                                            })}
                                        </div>
                                    ))}
                                </motion.div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between px-4 py-2 border-t border-white/10 text-xs text-gray-500">
                            <span className="flex items-center gap-2">
                                <KeyboardShortcut keys={['↑']} />
                                <KeyboardShortcut keys={['↓']} />
                                <span>to navigate</span>
                            </span>
                            <span className="flex items-center gap-2">
                                <KeyboardShortcut keys={['↵']} />
                                <span>to select</span>
                            </span>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );

    return typeof document !== 'undefined' ? createPortal(content, document.body) : null;
}

// ============================================================================
// Hook for Command Palette
// ============================================================================

export function useCommandPalette(items: CommandItem[]) {
    const [isOpen, setIsOpen] = useState(false);
    const [recentItems, setRecentItems] = useState<string[]>(() => {
        if (typeof window !== 'undefined') {
            const stored = localStorage.getItem('beatsight-command-recent');
            return stored ? JSON.parse(stored) : [];
        }
        return [];
    });

    // Save recent items to localStorage
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem('beatsight-command-recent', JSON.stringify(recentItems));
        }
    }, [recentItems]);

    // Global keyboard shortcut
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // ⌘K or Ctrl+K
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setIsOpen(open => !open);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);

    return {
        isOpen,
        setIsOpen,
        recentItems,
        setRecentItems,
        CommandPaletteComponent: () => (
            <CommandPalette
                items={items}
                isOpen={isOpen}
                onOpenChange={setIsOpen}
                recentItems={recentItems}
                onRecentItemsChange={setRecentItems}
            />
        ),
    };
}

// ============================================================================
// Pre-built Command Icons
// ============================================================================

export const CommandIcons = {
    Search: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
        </svg>
    ),
    Settings: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
        </svg>
    ),
    User: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
        </svg>
    ),
    Music: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 18V5l12-2v13" />
            <circle cx="6" cy="18" r="3" />
            <circle cx="18" cy="16" r="3" />
        </svg>
    ),
    Home: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9,22 9,12 15,12 15,22" />
        </svg>
    ),
    Upload: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17,8 12,3 7,8" />
            <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
    ),
    Plus: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    ),
    LogOut: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16,17 21,12 16,7" />
            <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
    ),
    Help: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
    ),
};
