import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CreditBalance, CreditBadge } from './CreditBalance'

// Mock the useCredits hook
vi.mock('@/hooks/useCredits', () => ({
    useCreditCount: vi.fn(),
}))

// Mock react-router-dom navigation
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom')
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    }
})

import { useCreditCount } from '@/hooks/useCredits'

// Helper function to render with router context
const renderWithRouter = (component: React.ReactElement) => {
    return render(
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            {component}
        </MemoryRouter>
    )
}

describe('CreditBalance', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders credit count when user has credits', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 10,
            isLoading: false,
        })

        renderWithRouter(<CreditBalance />)

        expect(screen.getByText('10')).toBeInTheDocument()
    })

    it('returns null when credits is 0 and showWhenZero is false', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: false,
        })

        const { container } = renderWithRouter(<CreditBalance />)

        expect(container.querySelector('button')).toBeNull()
    })

    it('renders when credits is 0 and showWhenZero is true', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: false,
        })

        renderWithRouter(<CreditBalance showWhenZero />)

        expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('shows loading indicator when loading', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: true,
        })

        renderWithRouter(<CreditBalance showWhenZero />)

        expect(screen.getByText('...')).toBeInTheDocument()
    })

    it('calls onClick when clicked', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        const handleClick = vi.fn()
        renderWithRouter(<CreditBalance onClick={handleClick} />)

        fireEvent.click(screen.getByRole('button'))
        expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('navigates to pricing when clicked without custom handler', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        renderWithRouter(<CreditBalance />)

        fireEvent.click(screen.getByRole('button'))
        expect(mockNavigate).toHaveBeenCalledWith('/pricing')
    })

    it('applies custom className', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        renderWithRouter(<CreditBalance className="custom-class" />)

        const button = screen.getByRole('button')
        expect(button).toHaveClass('custom-class')
    })

    it('has accessible label with credit info', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        renderWithRouter(<CreditBalance />)

        const button = screen.getByRole('button')
        // We now use aria-label instead of title (tooltip is handled by Tooltip component)
        expect(button).toHaveAttribute('aria-label', '5 credits available. Click to buy more.')
    })

    it('renders credit coin icon', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        const { container } = renderWithRouter(<CreditBalance />)

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
