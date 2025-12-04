import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QuotaDisplay } from './QuotaDisplay'
import type { QuotaStatus } from '@/types/api'

// Mock the useCredits hook
vi.mock('@/hooks/useCredits', () => ({
    useCreditCount: vi.fn(),
}))

import { useCreditCount } from '@/hooks/useCredits'

describe('QuotaDisplay', () => {
    const defaultQuota: QuotaStatus = {
        plan: 'free',
        used_this_month: 3,
        used_today: 1,
        remaining_month: 7,
        remaining_today: 4,
        limit_month: 10,
        limit_day: 5,
        resets_at: '2024-02-01T00:00:00Z',
        priority: 0,
    }

    beforeEach(() => {
        vi.clearAllMocks()
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: false,
        })
    })

    it('renders quota title', () => {
        render(<QuotaDisplay quota={defaultQuota} />)
        expect(screen.getByText('Your Quota')).toBeInTheDocument()
    })

    it('displays monthly quota usage', () => {
        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('Monthly')).toBeInTheDocument()
        expect(screen.getByText('3 / 10')).toBeInTheDocument()
        expect(screen.getByText('7 remaining')).toBeInTheDocument()
    })

    it('displays daily quota usage', () => {
        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('Today')).toBeInTheDocument()
        expect(screen.getByText('1 / 5')).toBeInTheDocument()
        expect(screen.getByText('4 remaining today')).toBeInTheDocument()
    })

    it('displays plan name capitalized', () => {
        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('Free')).toBeInTheDocument()
    })

    it('shows Pro plan correctly', () => {
        const proQuota = { ...defaultQuota, plan: 'pro' }
        render(<QuotaDisplay quota={proQuota} />)

        expect(screen.getByText('Pro')).toBeInTheDocument()
    })

    it('shows Free when plan is null', () => {
        const noPlantQuota = { ...defaultQuota, plan: null }
        render(<QuotaDisplay quota={noPlantQuota} />)

        expect(screen.getByText('Free')).toBeInTheDocument()
    })

    it('displays credits balance', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('5 credits')).toBeInTheDocument()
    })

    it('shows singular "credit" for 1 credit', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 1,
            isLoading: false,
        })

        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('1 credit')).toBeInTheDocument()
    })

    it('shows loading state for credits', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 0,
            isLoading: true,
        })

        render(<QuotaDisplay quota={defaultQuota} />)

        expect(screen.getByText('...')).toBeInTheDocument()
    })

    it('shows credits message when quota exhausted and credits available', () => {
        vi.mocked(useCreditCount).mockReturnValue({
            credits: 5,
            isLoading: false,
        })

        const exhaustedQuota = {
            ...defaultQuota,
            remaining_month: 0,
        }

        render(<QuotaDisplay quota={exhaustedQuota} />)

        expect(screen.getByText(/Credits will be used when quota runs out/)).toBeInTheDocument()
    })

    it('shows reset date when available', () => {
        render(<QuotaDisplay quota={defaultQuota} />)

        // Date format depends on locale, just check it contains "Resets"
        expect(screen.getByText(/Resets/)).toBeInTheDocument()
    })

    it('applies custom className', () => {
        const { container } = render(
            <QuotaDisplay quota={defaultQuota} className="custom-class" />
        )

        expect(container.firstChild).toHaveClass('custom-class')
    })

    describe('progress bar colors', () => {
        it('uses primary color when under 70%', () => {
            // 30% used (3/10)
            const { container } = render(<QuotaDisplay quota={defaultQuota} />)

            const progressBars = container.querySelectorAll('.bg-primary-500')
            expect(progressBars.length).toBeGreaterThan(0)
        })

        it('uses yellow color when over 70%', () => {
            const highUsage = {
                ...defaultQuota,
                used_this_month: 8, // 80%
                remaining_month: 2,
            }

            const { container } = render(<QuotaDisplay quota={highUsage} />)

            const yellowBar = container.querySelector('.bg-yellow-500')
            expect(yellowBar).toBeInTheDocument()
        })

        it('uses red color when over 90%', () => {
            const criticalUsage = {
                ...defaultQuota,
                used_this_month: 10, // 100%
                remaining_month: 0,
            }

            const { container } = render(<QuotaDisplay quota={criticalUsage} />)

            const redBar = container.querySelector('.bg-red-500')
            expect(redBar).toBeInTheDocument()
        })
    })
})
