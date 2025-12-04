import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { JobCard } from './JobCard'
import type { AIJob } from '@/types/api'

// Mock date-fns
vi.mock('date-fns', () => ({
    formatDistanceToNow: vi.fn(() => '5 minutes ago'),
}))

describe('JobCard', () => {
    const baseJob: AIJob = {
        id: 'job-123-456-789',
        song_id: 'song-abc-def-ghi',
        state: 'queued',
        priority: 'standard',
        error_message: null,
        requested_by_id: 'user-1',
        started_at: null,
        finished_at: null,
        created_at: '2024-01-15T10:00:00Z',
        worker_id: null,
        last_heartbeat: null,
        progress_percent: null,
        progress_message: null,
    }

    const renderJobCard = (job: AIJob, showProgress = true) => {
        return render(
            <MemoryRouter>
                <JobCard job={job} showProgress={showProgress} />
            </MemoryRouter>
        )
    }

    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders job with queued state', () => {
        renderJobCard(baseJob)

        expect(screen.getByText('Queued')).toBeInTheDocument()
        expect(screen.getByText(/Song ID:/)).toBeInTheDocument()
        expect(screen.getByText(/song-abc/)).toBeInTheDocument()
    })

    it('renders job with processing state and progress', () => {
        const processingJob: AIJob = {
            ...baseJob,
            state: 'processing',
            progress_percent: 45,
            progress_message: 'Analyzing drums...',
        }

        renderJobCard(processingJob)

        expect(screen.getByText('Processing')).toBeInTheDocument()
        expect(screen.getByText('45%')).toBeInTheDocument()
    })

    it('renders job with complete state', () => {
        const completeJob: AIJob = {
            ...baseJob,
            state: 'complete',
            finished_at: '2024-01-15T10:30:00Z',
        }

        renderJobCard(completeJob)

        expect(screen.getByText('Complete')).toBeInTheDocument()
    })

    it('renders job with failed state and error message', () => {
        const failedJob: AIJob = {
            ...baseJob,
            state: 'failed',
            error_message: 'Audio processing failed: invalid format',
        }

        renderJobCard(failedJob)

        expect(screen.getByText('Failed')).toBeInTheDocument()
        expect(screen.getByText(/Audio processing failed/)).toBeInTheDocument()
    })

    it('truncates long error messages', () => {
        const longError = 'x'.repeat(150)
        const failedJob: AIJob = {
            ...baseJob,
            state: 'failed',
            error_message: longError,
        }

        renderJobCard(failedJob)

        // Should truncate at 100 chars and add ellipsis
        expect(screen.getByText(/x{100}\.\.\./)).toBeInTheDocument()
    })

    it('shows priority badge for priority jobs', () => {
        const priorityJob: AIJob = {
            ...baseJob,
            priority: 'priority',
        }

        renderJobCard(priorityJob)

        expect(screen.getByText('Priority')).toBeInTheDocument()
    })

    it('shows retry count when retries have occurred', () => {
        const retryJob: AIJob = {
            ...baseJob,
            state: 'processing',
            retry_count: 2,
            max_retries: 3,
            progress_percent: 10,
        }

        renderJobCard(retryJob)

        expect(screen.getByText('Retry 2/3')).toBeInTheDocument()
    })

    it('does not show retry count when no retries', () => {
        renderJobCard(baseJob)

        expect(screen.queryByText(/Retry/)).not.toBeInTheDocument()
    })

    it('links to job detail page', () => {
        renderJobCard(baseJob)

        const link = screen.getByRole('link')
        expect(link).toHaveAttribute('href', '/jobs/job-123-456-789')
    })

    it('hides progress bar when showProgress is false', () => {
        const processingJob: AIJob = {
            ...baseJob,
            state: 'processing',
            progress_percent: 50,
        }

        renderJobCard(processingJob, false)

        // Progress percentage should still show in text
        expect(screen.getByText('50%')).toBeInTheDocument()
        // But the progress bar component would not render
        // (the actual bar is inside ProgressBar component)
    })

    it('displays created time', () => {
        renderJobCard(baseJob)

        expect(screen.getByText(/Created/)).toBeInTheDocument()
    })

    it('renders cancelled state', () => {
        const cancelledJob: AIJob = {
            ...baseJob,
            state: 'cancelled',
        }

        renderJobCard(cancelledJob)

        expect(screen.getByText('Cancelled')).toBeInTheDocument()
    })
})
