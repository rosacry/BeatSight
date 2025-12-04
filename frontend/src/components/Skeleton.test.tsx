import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
    Skeleton,
    SkeletonText,
    SkeletonTitle,
    SkeletonAvatar,
    SkeletonButton,
    SkeletonImage,
    SongCardSkeleton,
    SongListItemSkeleton,
    ProfileSkeleton,
    JobCardSkeleton,
    TableRowSkeleton,
    LibraryGridSkeleton,
    LibraryListSkeleton,
} from './Skeleton'

describe('Skeleton components', () => {
    describe('Skeleton', () => {
        it('renders with animation classes', () => {
            const { container } = render(<Skeleton />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('animate-pulse')
            expect(element).toHaveClass('bg-gray-700')
        })

        it('applies custom className', () => {
            const { container } = render(<Skeleton className="h-10 w-full" />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('h-10')
            expect(element).toHaveClass('w-full')
        })
    })

    describe('SkeletonText', () => {
        it('renders with text-appropriate dimensions', () => {
            const { container } = render(<SkeletonText />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('h-4')
            expect(element).toHaveClass('w-full')
        })
    })

    describe('SkeletonTitle', () => {
        it('renders with title-appropriate dimensions', () => {
            const { container } = render(<SkeletonTitle />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('h-6')
            expect(element).toHaveClass('w-3/4')
        })
    })

    describe('SkeletonAvatar', () => {
        it('renders with circular shape', () => {
            const { container } = render(<SkeletonAvatar />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('rounded-full')
            expect(element).toHaveClass('h-10')
            expect(element).toHaveClass('w-10')
        })
    })

    describe('SkeletonButton', () => {
        it('renders with button-like dimensions', () => {
            const { container } = render(<SkeletonButton />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('h-10')
            expect(element).toHaveClass('w-24')
            expect(element).toHaveClass('rounded-lg')
        })
    })

    describe('SkeletonImage', () => {
        it('renders with image-like dimensions', () => {
            const { container } = render(<SkeletonImage />)
            const element = container.firstChild as HTMLElement
            expect(element).toHaveClass('h-48')
            expect(element).toHaveClass('w-full')
            expect(element).toHaveClass('rounded-lg')
        })
    })

    describe('Composite skeletons', () => {
        it('SongCardSkeleton renders all elements', () => {
            const { container } = render(<SongCardSkeleton />)
            expect(container.querySelector('.bg-gray-800')).toBeInTheDocument()
            // Should contain multiple skeleton elements
            expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(1)
        })

        it('SongListItemSkeleton renders with flex layout', () => {
            const { container } = render(<SongListItemSkeleton />)
            expect(container.querySelector('.flex')).toBeInTheDocument()
        })

        it('ProfileSkeleton renders avatar and stats grid', () => {
            const { container } = render(<ProfileSkeleton />)
            // Has avatar skeleton (rounded-full large element)
            expect(container.querySelector('.rounded-full')).toBeInTheDocument()
            // Has grid with 3 items
            const gridItems = container.querySelectorAll('.grid > div')
            expect(gridItems.length).toBe(3)
        })

        it('JobCardSkeleton renders job card structure', () => {
            const { container } = render(<JobCardSkeleton />)
            expect(container.querySelector('.bg-gray-800')).toBeInTheDocument()
            // Contains progress bar skeleton (rounded-full)
            expect(container.querySelector('.rounded-full')).toBeInTheDocument()
        })
    })

    describe('TableRowSkeleton', () => {
        it('renders default 5 columns', () => {
            render(
                <table>
                    <tbody>
                        <TableRowSkeleton />
                    </tbody>
                </table>
            )
            const cells = screen.getAllByRole('cell')
            expect(cells).toHaveLength(5)
        })

        it('renders custom number of columns', () => {
            render(
                <table>
                    <tbody>
                        <TableRowSkeleton columns={3} />
                    </tbody>
                </table>
            )
            const cells = screen.getAllByRole('cell')
            expect(cells).toHaveLength(3)
        })
    })

    describe('LibraryGridSkeleton', () => {
        it('renders default 8 cards', () => {
            const { container } = render(<LibraryGridSkeleton />)
            const cards = container.querySelectorAll('.bg-gray-800.rounded-lg')
            expect(cards).toHaveLength(8)
        })

        it('renders custom count of cards', () => {
            const { container } = render(<LibraryGridSkeleton count={4} />)
            const cards = container.querySelectorAll('.bg-gray-800.rounded-lg')
            expect(cards).toHaveLength(4)
        })

        it('has grid layout classes', () => {
            const { container } = render(<LibraryGridSkeleton />)
            expect(container.querySelector('.grid')).toBeInTheDocument()
        })
    })

    describe('LibraryListSkeleton', () => {
        it('renders default 5 items', () => {
            const { container } = render(<LibraryListSkeleton />)
            const items = container.querySelectorAll('.flex.items-center.gap-4')
            expect(items).toHaveLength(5)
        })

        it('renders custom count of items', () => {
            const { container } = render(<LibraryListSkeleton count={3} />)
            const items = container.querySelectorAll('.flex.items-center.gap-4')
            expect(items).toHaveLength(3)
        })
    })
})
