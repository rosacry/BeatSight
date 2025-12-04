import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressBar, IndeterminateProgressBar } from './ProgressBar'

describe('ProgressBar', () => {
    it('renders progress percentage', () => {
        render(<ProgressBar percent={45} />)
        expect(screen.getByText('45%')).toBeInTheDocument()
    })

    it('clamps percentage to minimum 0', () => {
        render(<ProgressBar percent={-10} />)
        expect(screen.getByText('0%')).toBeInTheDocument()
    })

    it('clamps percentage to maximum 100', () => {
        render(<ProgressBar percent={150} />)
        expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('displays custom message', () => {
        render(<ProgressBar percent={50} message="Analyzing drums..." />)
        expect(screen.getByText('Analyzing drums...')).toBeInTheDocument()
    })

    it('displays default message when none provided', () => {
        render(<ProgressBar percent={50} />)
        expect(screen.getByText('Processing...')).toBeInTheDocument()
    })

    it('displays stage with message', () => {
        render(<ProgressBar percent={30} stage="Separation" message="Running AI model" />)
        expect(screen.getByText(/Separation:/)).toBeInTheDocument()
        expect(screen.getByText('Running AI model')).toBeInTheDocument()
    })

    it('hides label when showLabel is false', () => {
        render(<ProgressBar percent={50} message="Custom message" showLabel={false} />)
        expect(screen.queryByText('Custom message')).not.toBeInTheDocument()
        expect(screen.queryByText('50%')).not.toBeInTheDocument()
    })

    it('applies custom className', () => {
        const { container } = render(<ProgressBar percent={50} className="custom-class" />)
        expect(container.firstChild).toHaveClass('custom-class')
    })

    it('uses primary color for incomplete progress', () => {
        const { container } = render(<ProgressBar percent={50} />)
        const progressFill = container.querySelector('.bg-primary-500')
        expect(progressFill).toBeInTheDocument()
    })

    it('uses green color for complete progress', () => {
        const { container } = render(<ProgressBar percent={100} />)
        const progressFill = container.querySelector('.bg-green-500')
        expect(progressFill).toBeInTheDocument()
    })

    it('sets correct width style based on percent', () => {
        const { container } = render(<ProgressBar percent={75} />)
        const progressFill = container.querySelector('[style*="width"]')
        expect(progressFill).toHaveStyle({ width: '75%' })
    })

    it('handles edge case of 0 percent', () => {
        render(<ProgressBar percent={0} />)
        expect(screen.getByText('0%')).toBeInTheDocument()
    })

    it('handles edge case of 100 percent', () => {
        render(<ProgressBar percent={100} />)
        expect(screen.getByText('100%')).toBeInTheDocument()
    })
})

describe('IndeterminateProgressBar', () => {
    it('renders with default loading message', () => {
        render(<IndeterminateProgressBar />)
        expect(screen.getByText('Loading...')).toBeInTheDocument()
    })

    it('renders with custom message', () => {
        render(<IndeterminateProgressBar message="Uploading file..." />)
        expect(screen.getByText('Uploading file...')).toBeInTheDocument()
    })

    it('applies custom className', () => {
        const { container } = render(<IndeterminateProgressBar className="my-custom-class" />)
        expect(container.firstChild).toHaveClass('my-custom-class')
    })

    it('has animated progress indicator', () => {
        const { container } = render(<IndeterminateProgressBar />)
        const animatedElement = container.querySelector('.animate-progress')
        expect(animatedElement).toBeInTheDocument()
    })
})
