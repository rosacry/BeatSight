/**
 * Keyboard shortcuts hook and context.
 */

import { useEffect, useCallback, createContext, useContext, useState, ReactNode } from 'react';

export interface Shortcut {
    key: string;
    ctrl?: boolean;
    shift?: boolean;
    alt?: boolean;
    meta?: boolean;
    description: string;
    action: () => void;
    scope?: string;
}

interface KeyboardShortcutsContextValue {
    shortcuts: Shortcut[];
    registerShortcut: (shortcut: Shortcut) => () => void;
    unregisterShortcut: (key: string) => void;
    isHelpOpen: boolean;
    toggleHelp: () => void;
}

const KeyboardShortcutsContext = createContext<KeyboardShortcutsContextValue | null>(null);

// eslint-disable-next-line react-refresh/only-export-components
export function useKeyboardShortcuts() {
    const context = useContext(KeyboardShortcutsContext);
    if (!context) {
        throw new Error('useKeyboardShortcuts must be used within a KeyboardShortcutsProvider');
    }
    return context;
}

interface KeyboardShortcutsProviderProps {
    children: ReactNode;
}

export function KeyboardShortcutsProvider({ children }: KeyboardShortcutsProviderProps) {
    const [shortcuts, setShortcuts] = useState<Shortcut[]>([]);
    const [isHelpOpen, setIsHelpOpen] = useState(false);

    const registerShortcut = useCallback((shortcut: Shortcut) => {
        setShortcuts((prev) => [...prev, shortcut]);
        return () => {
            setShortcuts((prev) => prev.filter((s) => s.key !== shortcut.key));
        };
    }, []);

    const unregisterShortcut = useCallback((key: string) => {
        setShortcuts((prev) => prev.filter((s) => s.key !== key));
    }, []);

    const toggleHelp = useCallback(() => {
        setIsHelpOpen((prev) => !prev);
    }, []);

    // Global keyboard event handler
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Don't trigger shortcuts when typing in inputs
            const target = e.target as HTMLElement;
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
                // Allow Escape to still work
                if (e.key !== 'Escape') return;
            }

            // Toggle help with ?
            if (e.key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                toggleHelp();
                return;
            }

            // Close help with Escape
            if (e.key === 'Escape' && isHelpOpen) {
                e.preventDefault();
                setIsHelpOpen(false);
                return;
            }

            // Find matching shortcut
            for (const shortcut of shortcuts) {
                const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase();
                const ctrlMatch = !!shortcut.ctrl === (e.ctrlKey || e.metaKey);
                const shiftMatch = !!shortcut.shift === e.shiftKey;
                const altMatch = !!shortcut.alt === e.altKey;

                if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
                    e.preventDefault();
                    shortcut.action();
                    return;
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [shortcuts, isHelpOpen, toggleHelp]);

    return (
        <KeyboardShortcutsContext.Provider
            value={{ shortcuts, registerShortcut, unregisterShortcut, isHelpOpen, toggleHelp }}
        >
            {children}
            {isHelpOpen && <ShortcutsHelpModal shortcuts={shortcuts} onClose={() => setIsHelpOpen(false)} />}
        </KeyboardShortcutsContext.Provider>
    );
}

interface ShortcutsHelpModalProps {
    shortcuts: Shortcut[];
    onClose: () => void;
}

function ShortcutsHelpModal({ shortcuts, onClose }: ShortcutsHelpModalProps) {
    // Group shortcuts by scope
    const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
        const scope = shortcut.scope || 'Global';
        if (!acc[scope]) acc[scope] = [];
        acc[scope].push(shortcut);
        return acc;
    }, {} as Record<string, Shortcut[]>);

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={onClose}
        >
            <div
                className="bg-gray-800 rounded-xl p-6 max-w-lg w-full mx-4 border border-gray-700 shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white">Keyboard Shortcuts</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="space-y-6 max-h-96 overflow-y-auto">
                    {Object.entries(groupedShortcuts).map(([scope, scopeShortcuts]) => (
                        <div key={scope}>
                            <h3 className="text-sm font-medium text-gray-400 mb-3">{scope}</h3>
                            <div className="space-y-2">
                                {scopeShortcuts.map((shortcut) => (
                                    <div key={shortcut.key} className="flex items-center justify-between">
                                        <span className="text-gray-300">{shortcut.description}</span>
                                        <kbd className="px-2 py-1 bg-gray-700 rounded text-sm font-mono text-gray-200">
                                            {formatShortcut(shortcut)}
                                        </kbd>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}

                    {/* Built-in shortcuts */}
                    <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-3">Help</h3>
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <span className="text-gray-300">Show this help</span>
                                <kbd className="px-2 py-1 bg-gray-700 rounded text-sm font-mono text-gray-200">?</kbd>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-gray-300">Close dialogs</span>
                                <kbd className="px-2 py-1 bg-gray-700 rounded text-sm font-mono text-gray-200">Esc</kbd>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function formatShortcut(shortcut: Shortcut): string {
    const parts: string[] = [];
    if (shortcut.ctrl) parts.push('Ctrl');
    if (shortcut.alt) parts.push('Alt');
    if (shortcut.shift) parts.push('Shift');
    if (shortcut.meta) parts.push('⌘');
    parts.push(shortcut.key.toUpperCase());
    return parts.join(' + ');
}

// Hook for registering shortcuts in components
// eslint-disable-next-line react-refresh/only-export-components
export function useShortcut(shortcut: Shortcut) {
    const { registerShortcut } = useKeyboardShortcuts();

    useEffect(() => {
        const unregister = registerShortcut(shortcut);
        return unregister;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [shortcut.key, shortcut.ctrl, shortcut.shift, shortcut.alt, registerShortcut]);
}

// Common shortcuts
// eslint-disable-next-line react-refresh/only-export-components
export const commonShortcuts = {
    search: { key: '/', description: 'Focus search', scope: 'Navigation' },
    home: { key: 'h', description: 'Go to home', scope: 'Navigation' },
    library: { key: 'l', description: 'Go to library', scope: 'Navigation' },
    upload: { key: 'u', description: 'Go to upload', scope: 'Navigation' },
    settings: { key: ',', ctrl: true, description: 'Open settings', scope: 'Navigation' },
};
