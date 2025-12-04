import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobStatusBadge } from './JobStatusBadge'
import type { AIJobState } from '@/types/api'

describe('JobStatusBadge', () => {
    const states: { state: AIJobState; label: string }[] = [
        { state: 'queued', label: 'Queued' },
        { state: 'processing', label: 'Processing' },
        { state: 'complete', label: 'Complete' },
        { state: 'failed', label: 'Failed' },
        { state: 'cancelled', label: 'Cancelled' },
    ]

    it.each(states)('renders $state state with "$label" label', ({ state, label }) => {
        render(<JobStatusBadge state={state} />)
        expect(screen.getByText(label)).toBeInTheDocument()
    })

    it('shows animated pulse indicator for processing state', () => {
        const { container } = render(<JobStatusBadge state="processing" />)

        const pulseElement = container.querySelector('.animate-pulse')
        expect(pulseElement).toBeInTheDocument()
    })

    it('does not show pulse indicator for non-processing states', () => {
        const { container } = render(<JobStatusBadge state="queued" />)

        const pulseElement = container.querySelector('.animate-pulse')
        expect(pulseElement).not.toBeInTheDocument()
    })

    it('applies custom className', () => {
        render(<JobStatusBadge state="complete" className="custom-class" />)

        const badge = screen.getByText('Complete')
        expect(badge).toHaveClass('custom-class')
    })

    it('has correct styling classes for queued state', () => {
        render(<JobStatusBadge state="queued" />)

        const badge = screen.getByText('Queued')
        expect(badge).toHaveClass('text-yellow-400')
    })

    it('has correct styling classes for complete state', () => {
        render(<JobStatusBadge state="complete" />)

        const badge = screen.getByText('Complete')
        expect(badge).toHaveClass('text-green-400')
    })

    it('has correct styling classes for failed state', () => {
        render(<JobStatusBadge state="failed" />)

        const badge = screen.getByText('Failed')
        expect(badge).toHaveClass('text-red-400')
    })

    it('is rendered as a span element with badge styling', () => {
        render(<JobStatusBadge state="queued" />)

        const badge = screen.getByText('Queued')
        expect(badge.tagName).toBe('SPAN')
        expect(badge).toHaveClass('rounded-full')
        expect(badge).toHaveClass('text-xs')
        expect(badge).toHaveClass('font-medium')
    })
})
