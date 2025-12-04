import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CreditBalance, CreditBadge } from './CreditBalance'

// Mock the useCredits hook
vi.mock('@/hooks/useCredits', () => ({
    useCreditCount: vi.fn(),
}))

import { useCreditCount } from '@/hooks/useCredits'

describe('CreditBalance', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders credit count when user has credits', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 10,
            isLoading: false,
        })

        render(<CreditBalance />)

        expect(screen.getByText('10')).toBeInTheDocument()
    })

    it('returns null when credits is 0 and showWhenZero is false', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: false,
        })

        const { container } = render(<CreditBalance />)

        expect(container.firstChild).toBeNull()
    })

    it('renders when credits is 0 and showWhenZero is true', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: false,
        })

        render(<CreditBalance showWhenZero />)

        expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('shows loading indicator when loading', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: true,
        })

        render(<CreditBalance showWhenZero />)

        expect(screen.getByText('...')).toBeInTheDocument()
    })

    it('calls onClick when clicked', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        const handleClick = vi.fn()
        render(<CreditBalance onClick={handleClick} />)

        fireEvent.click(screen.getByRole('button'))
        expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('applies custom className', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        render(<CreditBalance className="custom-class" />)

        const button = screen.getByRole('button')
        expect(button).toHaveClass('custom-class')
    })

    it('has tooltip with credit info', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        render(<CreditBalance />)

        const button = screen.getByRole('button')
        expect(button).toHaveAttribute('title', 'Credit balance - click to buy more')
    })

    it('renders credit coin icon', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        const { container } = render(<CreditBalance />)

        const svg = container.querySelector('svg')
        expect(svg).toBeInTheDocument()
    })
})

describe('CreditBadge', () => {
    it('renders credit count', () => {
        render(<CreditBadge credits={15} />)

        expect(screen.getByText('15')).toBeInTheDocument()
    })

    it('returns null when credits is 0', () => {
        const { container } = render(<CreditBadge credits={0} />)

        expect(container.firstChild).toBeNull()
    })

    it('has badge styling', () => {
        const { container } = render(<CreditBadge credits={10} />)

        const badge = container.firstChild as HTMLElement
        expect(badge).toHaveClass('rounded-full')
        expect(badge).toHaveClass('text-xs')
    })

    it('renders coin icon', () => {
        const { container } = render(<CreditBadge credits={5} />)

        const svg = container.querySelector('svg')
        expect(svg).toBeInTheDocument()
    })
})
