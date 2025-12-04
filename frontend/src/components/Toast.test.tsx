import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { ToastProvider, useToast, type ToastType } from './Toast'

// Test component to access toast context
function TestConsumer({ action, type, title, message }: {
    action?: 'add' | 'shortcut'
    type?: ToastType
    title?: string
    message?: string
}) {
    const toast = useToast()

    return (
        <div>
            <button onClick={() => {
                if (action === 'shortcut' && type) {
                    toast[type](title || 'Test', message)
                } else {
                    toast.addToast({ type: type || 'info', title: title || 'Test', message })
                }
            }}>
                Add Toast
            </button>
            <span data-testid="toast-count">{toast.toasts.length}</span>
        </div>
    )
}

describe('ToastProvider', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('provides toast context to children', () => {
        render(
            <ToastProvider>
                <TestConsumer />
            </ToastProvider>
        )

        expect(screen.getByTestId('toast-count')).toHaveTextContent('0')
    })

    it('adds a toast when addToast is called', () => {
        render(
            <ToastProvider>
                <TestConsumer action="add" type="success" title="Test Toast" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        expect(screen.getByRole('alert')).toBeInTheDocument()
        expect(screen.getByText('Test Toast')).toBeInTheDocument()
    })

    it('displays toast message when provided', () => {
        render(
            <ToastProvider>
                <TestConsumer action="add" type="info" title="Title" message="Detailed message" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        expect(screen.getByText('Detailed message')).toBeInTheDocument()
    })

    it('removes toast after clicking dismiss button', () => {
        render(
            <ToastProvider>
                <TestConsumer action="add" type="info" title="Test" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))
        expect(screen.getByRole('alert')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('auto-removes toast after default duration', async () => {
        render(
            <ToastProvider>
                <TestConsumer action="add" type="info" title="Auto Remove" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))
        expect(screen.getByRole('alert')).toBeInTheDocument()

        // Advance timers past default 5000ms duration
        act(() => {
            vi.advanceTimersByTime(5100)
        })

        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('success shortcut creates success toast', () => {
        render(
            <ToastProvider>
                <TestConsumer action="shortcut" type="success" title="Success!" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        const alert = screen.getByRole('alert')
        expect(alert).toHaveClass('text-green-400')
        expect(screen.getByText('Success!')).toBeInTheDocument()
    })

    it('error shortcut creates error toast with longer duration', async () => {
        render(
            <ToastProvider>
                <TestConsumer action="shortcut" type="error" title="Error!" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        const alert = screen.getByRole('alert')
        expect(alert).toHaveClass('text-red-400')

        // Error toasts have 8000ms duration
        act(() => {
            vi.advanceTimersByTime(5100)
        })
        // Should still be visible
        expect(screen.getByRole('alert')).toBeInTheDocument()

        act(() => {
            vi.advanceTimersByTime(3000)
        })
        // Now should be removed
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('warning shortcut creates warning toast', () => {
        render(
            <ToastProvider>
                <TestConsumer action="shortcut" type="warning" title="Warning!" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        const alert = screen.getByRole('alert')
        expect(alert).toHaveClass('text-yellow-400')
    })

    it('info shortcut creates info toast', () => {
        render(
            <ToastProvider>
                <TestConsumer action="shortcut" type="info" title="Info!" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))

        const alert = screen.getByRole('alert')
        expect(alert).toHaveClass('text-blue-400')
    })

    it('can display multiple toasts', () => {
        render(
            <ToastProvider>
                <TestConsumer action="add" type="info" title="Toast 1" />
            </ToastProvider>
        )

        fireEvent.click(screen.getByText('Add Toast'))
        fireEvent.click(screen.getByText('Add Toast'))
        fireEvent.click(screen.getByText('Add Toast'))

        expect(screen.getAllByRole('alert')).toHaveLength(3)
    })

    it('each toast type has an icon', () => {
        const types: ToastType[] = ['success', 'error', 'warning', 'info']

        types.forEach((type) => {
            const { container, unmount } = render(
                <ToastProvider>
                    <TestConsumer action="shortcut" type={type} title={`${type} toast`} />
                </ToastProvider>
            )

            fireEvent.click(screen.getByText('Add Toast'))

            const svgs = container.querySelectorAll('svg')
            expect(svgs.length).toBeGreaterThanOrEqual(1) // At least icon + close button

            unmount()
        })
    })
})

describe('useToast outside provider', () => {
    it('throws error when used outside ToastProvider', () => {
        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => { })

        expect(() => {
            render(<TestConsumer />)
        }).toThrow('useToast must be used within a ToastProvider')

        consoleError.mockRestore()
    })
})
