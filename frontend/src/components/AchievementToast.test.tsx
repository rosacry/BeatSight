import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import {
    AchievementToast,
    AchievementNotificationProvider,
    showAchievementToast,
    type AchievementNotification
} from './AchievementToast'

describe('AchievementToast', () => {
    const mockAchievement: AchievementNotification = {
        id: '1',
        name: 'First Steps',
        description: 'Complete your first song analysis',
        icon: 'trophy',
        category: 'milestone',
        points: 10,
    }

    it('renders achievement toast correctly', () => {
        const onDismiss = vi.fn()
        render(
            <AchievementToast
                achievement={mockAchievement}
                onDismiss={onDismiss}
            />
        )

        expect(screen.getByText('Achievement Unlocked!')).toBeInTheDocument()
        expect(screen.getByText('First Steps')).toBeInTheDocument()
        expect(screen.getByText('Complete your first song analysis')).toBeInTheDocument()
        expect(screen.getByText('+10 points')).toBeInTheDocument()
    })

    it('calls onDismiss when toast is clicked', async () => {
        vi.useFakeTimers()
        const onDismiss = vi.fn()

        render(
            <AchievementToast
                achievement={mockAchievement}
                onDismiss={onDismiss}
            />
        )

        // Click on the toast container
        const toast = screen.getByText('First Steps').closest('.rounded-xl')
        expect(toast).toBeInTheDocument()

        await act(async () => {
            if (toast) fireEvent.click(toast)
        })

        // Wait for exit animation (300ms)
        await act(async () => {
            vi.advanceTimersByTime(350)
        })

        expect(onDismiss).toHaveBeenCalled()
        vi.useRealTimers()
    })

    it('renders different category styles', () => {
        const categories = ['milestone', 'skill', 'social', 'dedication'] as const

        for (const category of categories) {
            const { container, unmount } = render(
                <AchievementToast
                    achievement={{ ...mockAchievement, category }}
                    onDismiss={() => { }}
                />
            )

            // Just verify it renders without error
            const toast = container.querySelector('.rounded-xl')
            expect(toast).toBeInTheDocument()

            unmount()
        }
    })
})

describe('AchievementNotificationProvider', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders children correctly', () => {
        render(
            <AchievementNotificationProvider>
                <div data-testid="child">Child content</div>
            </AchievementNotificationProvider>
        )

        expect(screen.getByTestId('child')).toBeInTheDocument()
    })

    it('exports showAchievementToast function', () => {
        expect(typeof showAchievementToast).toBe('function')
    })
})
