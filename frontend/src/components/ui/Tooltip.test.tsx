/**
 * Tests for Tooltip Component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Tooltip } from './Tooltip'

describe('Tooltip', () => {
    it('renders children without tooltip initially', () => {
        render(
            <Tooltip content="Test tooltip">
                <button>Hover me</button>
            </Tooltip>
        )

        expect(screen.getByText('Hover me')).toBeInTheDocument()
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    })

    it('does not show tooltip when disabled', async () => {
        render(
            <Tooltip content="Test tooltip" disabled delay={0}>
                <button>Hover me</button>
            </Tooltip>
        )

        const button = screen.getByText('Hover me')
        fireEvent.mouseEnter(button)

        // Wait a bit to ensure tooltip doesn't appear
        await new Promise(r => setTimeout(r, 50))

        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    })

    it('cancels show timeout when mouse leaves before delay', async () => {
        render(
            <Tooltip content="Test tooltip" delay={500}>
                <button>Hover me</button>
            </Tooltip>
        )

        const button = screen.getByText('Hover me')

        // Start hovering
        fireEvent.mouseEnter(button)

        // Wait 50ms, then leave
        await new Promise(r => setTimeout(r, 50))
        fireEvent.mouseLeave(button)

        // Wait past original delay
        await new Promise(r => setTimeout(r, 500))

        // Tooltip should never have appeared
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    })

    it('passes through child event handlers', () => {
        const onMouseEnter = vi.fn()
        const onMouseLeave = vi.fn()
        const onFocus = vi.fn()
        const onBlur = vi.fn()

        render(
            <Tooltip content="Test tooltip" delay={0}>
                <button
                    onMouseEnter={onMouseEnter}
                    onMouseLeave={onMouseLeave}
                    onFocus={onFocus}
                    onBlur={onBlur}
                >
                    Button
                </button>
            </Tooltip>
        )

        const button = screen.getByText('Button')

        fireEvent.mouseEnter(button)
        expect(onMouseEnter).toHaveBeenCalled()

        fireEvent.mouseLeave(button)
        expect(onMouseLeave).toHaveBeenCalled()

        fireEvent.focus(button)
        expect(onFocus).toHaveBeenCalled()

        fireEvent.blur(button)
        expect(onBlur).toHaveBeenCalled()
    })

    it('shows and hides tooltip on hover', async () => {
        render(
            <Tooltip content="Test tooltip" delay={10}>
                <button>Hover me</button>
            </Tooltip>
        )

        const button = screen.getByText('Hover me')

        // Show tooltip
        fireEvent.mouseEnter(button)

        await waitFor(() => {
            expect(screen.getByRole('tooltip')).toBeInTheDocument()
            expect(screen.getByText('Test tooltip')).toBeInTheDocument()
        }, { timeout: 500 })

        // Hide tooltip
        fireEvent.mouseLeave(button)

        await waitFor(() => {
            expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
        }, { timeout: 500 })
    })

    it('shows tooltip on focus', async () => {
        render(
            <Tooltip content="Focus tooltip" delay={10}>
                <button>Focus me</button>
            </Tooltip>
        )

        const button = screen.getByText('Focus me')
        fireEvent.focus(button)

        await waitFor(() => {
            expect(screen.getByRole('tooltip')).toBeInTheDocument()
        }, { timeout: 500 })
    })

    it('renders with custom content', async () => {
        render(
            <Tooltip content={<span data-testid="custom">Custom Content</span>} delay={10}>
                <button>Hover me</button>
            </Tooltip>
        )

        fireEvent.mouseEnter(screen.getByText('Hover me'))

        await waitFor(() => {
            expect(screen.getByTestId('custom')).toBeInTheDocument()
        }, { timeout: 500 })
    })
})
