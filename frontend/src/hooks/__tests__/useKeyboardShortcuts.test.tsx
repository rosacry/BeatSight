/**
 * Tests for useKeyboardShortcuts hook and KeyboardShortcutsProvider
 *
 * Created: December 3, 2025
 * References: ENGINEERING_ACTION_TRACKER.md item 4.5
 */

import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { fireEvent } from '@testing-library/dom'
import {
    useKeyboardShortcuts,
    KeyboardShortcutsProvider,
    type Shortcut,
} from '../useKeyboardShortcuts'

// Wrapper component
function createWrapper() {
    return ({ children }: { children: React.ReactNode }) => (
        <KeyboardShortcutsProvider>{children}</KeyboardShortcutsProvider>
    )
}

describe('useKeyboardShortcuts', () => {
    describe('context requirement', () => {
        it('should throw error when used outside provider', () => {
            // Suppress console.error for this test
            const consoleError = vi.spyOn(console, 'error').mockImplementation(() => { })
            const windowErrorHandler = (event: ErrorEvent) => {
                if (
                    event.error instanceof Error &&
                    event.error.message.includes(
                        'useKeyboardShortcuts must be used within a KeyboardShortcutsProvider'
                    )
                ) {
                    event.preventDefault()
                }
            }
            window.addEventListener('error', windowErrorHandler)

            try {
                expect(() => {
                    renderHook(() => useKeyboardShortcuts())
                }).toThrow('useKeyboardShortcuts must be used within a KeyboardShortcutsProvider')
            } finally {
                window.removeEventListener('error', windowErrorHandler)
            }

            consoleError.mockRestore()
        })

        it('should work when used within provider', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            expect(result.current).toBeDefined()
            expect(result.current.shortcuts).toEqual([])
            expect(typeof result.current.registerShortcut).toBe('function')
            expect(typeof result.current.unregisterShortcut).toBe('function')
            expect(typeof result.current.toggleHelp).toBe('function')
        })
    })

    describe('registerShortcut', () => {
        it('should register a shortcut', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            const shortcut: Shortcut = {
                key: 'k',
                ctrl: true,
                description: 'Search',
                action: vi.fn(),
            }

            act(() => {
                result.current.registerShortcut(shortcut)
            })

            expect(result.current.shortcuts).toHaveLength(1)
            expect(result.current.shortcuts[0].key).toBe('k')
            expect(result.current.shortcuts[0].description).toBe('Search')
        })

        it('should return unregister function', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            const shortcut: Shortcut = {
                key: 's',
                ctrl: true,
                description: 'Save',
                action: vi.fn(),
            }

            let unregister: (() => void) | undefined

            act(() => {
                unregister = result.current.registerShortcut(shortcut)
            })

            expect(result.current.shortcuts).toHaveLength(1)

            act(() => {
                unregister!()
            })

            expect(result.current.shortcuts).toHaveLength(0)
        })

        it('should register multiple shortcuts', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    ctrl: true,
                    description: 'Save',
                    action: vi.fn(),
                })
                result.current.registerShortcut({
                    key: 'z',
                    ctrl: true,
                    description: 'Undo',
                    action: vi.fn(),
                })
                result.current.registerShortcut({
                    key: 'y',
                    ctrl: true,
                    description: 'Redo',
                    action: vi.fn(),
                })
            })

            expect(result.current.shortcuts).toHaveLength(3)
        })
    })

    describe('unregisterShortcut', () => {
        it('should unregister a shortcut by key', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    ctrl: true,
                    description: 'Save',
                    action: vi.fn(),
                })
            })

            expect(result.current.shortcuts).toHaveLength(1)

            act(() => {
                result.current.unregisterShortcut('s')
            })

            expect(result.current.shortcuts).toHaveLength(0)
        })
    })

    describe('toggleHelp', () => {
        it('should toggle help modal state', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            expect(result.current.isHelpOpen).toBe(false)

            act(() => {
                result.current.toggleHelp()
            })

            expect(result.current.isHelpOpen).toBe(true)

            act(() => {
                result.current.toggleHelp()
            })

            expect(result.current.isHelpOpen).toBe(false)
        })
    })

    describe('keyboard event handling', () => {
        it('should trigger shortcut action on keypress', () => {
            const actionMock = vi.fn()

            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    ctrl: true,
                    description: 'Save',
                    action: actionMock,
                })
            })

            // Simulate Ctrl+S keypress
            act(() => {
                fireEvent.keyDown(window, {
                    key: 's',
                    ctrlKey: true,
                })
            })

            expect(actionMock).toHaveBeenCalledTimes(1)
        })

        it('should not trigger shortcut without modifier when required', () => {
            const actionMock = vi.fn()

            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    ctrl: true,
                    description: 'Save',
                    action: actionMock,
                })
            })

            // Simulate S without Ctrl
            act(() => {
                fireEvent.keyDown(window, {
                    key: 's',
                    ctrlKey: false,
                })
            })

            expect(actionMock).not.toHaveBeenCalled()
        })

        it('should handle shift modifier', () => {
            const actionMock = vi.fn()

            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    ctrl: true,
                    shift: true,
                    description: 'Save As',
                    action: actionMock,
                })
            })

            // Without Shift - should not trigger
            act(() => {
                fireEvent.keyDown(window, {
                    key: 's',
                    ctrlKey: true,
                    shiftKey: false,
                })
            })

            expect(actionMock).not.toHaveBeenCalled()

            // With Shift - should trigger
            act(() => {
                fireEvent.keyDown(window, {
                    key: 's',
                    ctrlKey: true,
                    shiftKey: true,
                })
            })

            expect(actionMock).toHaveBeenCalledTimes(1)
        })

        it('should open help modal with ? key', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            expect(result.current.isHelpOpen).toBe(false)

            act(() => {
                fireEvent.keyDown(window, {
                    key: '?',
                })
            })

            expect(result.current.isHelpOpen).toBe(true)
        })

        it('should close help modal with Escape', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            // Open help first
            act(() => {
                result.current.toggleHelp()
            })

            expect(result.current.isHelpOpen).toBe(true)

            // Press Escape
            act(() => {
                fireEvent.keyDown(window, {
                    key: 'Escape',
                })
            })

            expect(result.current.isHelpOpen).toBe(false)
        })

        it('should not trigger shortcuts when typing in input', () => {
            const actionMock = vi.fn()

            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 's',
                    description: 'Select',
                    action: actionMock,
                })
            })

            // Create a mock input element
            const input = document.createElement('input')
            document.body.appendChild(input)
            input.focus()

            // Simulate keypress on input
            act(() => {
                fireEvent.keyDown(input, {
                    key: 's',
                    target: input,
                })
            })

            // Should not trigger because target is an input
            expect(actionMock).not.toHaveBeenCalled()

            // Cleanup
            document.body.removeChild(input)
        })

        it('should allow Escape even when in input', () => {
            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            // Open help
            act(() => {
                result.current.toggleHelp()
            })

            expect(result.current.isHelpOpen).toBe(true)

            // Create a mock input element
            const input = document.createElement('input')
            document.body.appendChild(input)
            input.focus()

            // Simulate Escape on input
            act(() => {
                fireEvent.keyDown(input, {
                    key: 'Escape',
                    target: input,
                })
            })

            // Should still close help
            expect(result.current.isHelpOpen).toBe(false)

            // Cleanup
            document.body.removeChild(input)
        })
    })

    describe('case insensitivity', () => {
        it('should match keys case-insensitively', () => {
            const actionMock = vi.fn()

            const { result } = renderHook(() => useKeyboardShortcuts(), {
                wrapper: createWrapper(),
            })

            act(() => {
                result.current.registerShortcut({
                    key: 'S', // uppercase
                    ctrl: true,
                    description: 'Save',
                    action: actionMock,
                })
            })

            // Press lowercase s
            act(() => {
                fireEvent.keyDown(window, {
                    key: 's',
                    ctrlKey: true,
                })
            })

            expect(actionMock).toHaveBeenCalledTimes(1)
        })
    })
})
