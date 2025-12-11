/**
 * Data Table component with sorting, pagination, and selection.
 */

import {
    forwardRef,
    useState,
    useMemo,
    useCallback,
    type HTMLAttributes,
    type ReactNode,
} from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

// ============================================================================
// TYPES
// ============================================================================

export interface Column<T> {
    /** Unique key for the column */
    key: string
    /** Header label */
    header: string | ReactNode
    /** Cell renderer - receives row data */
    cell?: (row: T, index: number) => ReactNode
    /** Accessor for sorting/default rendering */
    accessor?: keyof T | ((row: T) => unknown)
    /** Column width */
    width?: string | number
    /** Enable sorting */
    sortable?: boolean
    /** Text alignment */
    align?: 'left' | 'center' | 'right'
    /** Sticky column */
    sticky?: boolean
}

export interface SortState {
    key: string
    direction: 'asc' | 'desc'
}

// ============================================================================
// TABLE VARIANTS
// ============================================================================

const tableVariants = cva(
    'w-full border-collapse',
    {
        variants: {
            variant: {
                default: '',
                striped: '',
                bordered: '',
            },
            size: {
                sm: '',
                md: '',
                lg: '',
            },
        },
        defaultVariants: {
            variant: 'default',
            size: 'md',
        },
    }
)

const cellVariants = cva(
    'transition-colors',
    {
        variants: {
            size: {
                sm: 'px-3 py-2 text-xs',
                md: 'px-4 py-3 text-sm',
                lg: 'px-6 py-4 text-base',
            },
            align: {
                left: 'text-left',
                center: 'text-center',
                right: 'text-right',
            },
        },
        defaultVariants: {
            size: 'md',
            align: 'left',
        },
    }
)

// ============================================================================
// DATA TABLE
// ============================================================================

export interface DataTableProps<T>
    extends Omit<HTMLAttributes<HTMLDivElement>, 'children'>,
    VariantProps<typeof tableVariants> {
    /** Data to display */
    data: T[]
    /** Column definitions */
    columns: Column<T>[]
    /** Row key accessor */
    getRowKey: (row: T, index: number) => string | number
    /** Loading state */
    loading?: boolean
    /** Empty state message */
    emptyMessage?: ReactNode
    /** Enable row selection */
    selectable?: boolean
    /** Selected row keys */
    selectedKeys?: Set<string | number>
    /** Selection change handler */
    onSelectionChange?: (keys: Set<string | number>) => void
    /** Enable row hover effect */
    hoverable?: boolean
    /** Row click handler */
    onRowClick?: (row: T, index: number) => void
    /** Controlled sort state */
    sortState?: SortState | null
    /** Sort change handler */
    onSortChange?: (state: SortState | null) => void
    /** Max height with scroll */
    maxHeight?: string | number
    /** Sticky header */
    stickyHeader?: boolean
}

export function DataTable<T>({
    className,
    variant,
    size,
    data,
    columns,
    getRowKey,
    loading = false,
    emptyMessage = 'No data available',
    selectable = false,
    selectedKeys = new Set(),
    onSelectionChange,
    hoverable = true,
    onRowClick,
    sortState: controlledSort,
    onSortChange,
    maxHeight,
    stickyHeader = false,
    ...props
}: DataTableProps<T>) {
    const [internalSort, setInternalSort] = useState<SortState | null>(null)
    const sortState = controlledSort ?? internalSort

    const handleSort = useCallback(
        (key: string) => {
            const newState: SortState | null =
                sortState?.key === key
                    ? sortState.direction === 'asc'
                        ? { key, direction: 'desc' }
                        : null
                    : { key, direction: 'asc' }

            setInternalSort(newState)
            onSortChange?.(newState)
        },
        [sortState, onSortChange]
    )

    const sortedData = useMemo(() => {
        if (!sortState) return data

        const column = columns.find((c) => c.key === sortState.key)
        if (!column?.accessor) return data

        return [...data].sort((a, b) => {
            const accessor = column.accessor!
            const aVal = typeof accessor === 'function' ? accessor(a) : a[accessor as keyof T]
            const bVal = typeof accessor === 'function' ? accessor(b) : b[accessor as keyof T]

            if (aVal === bVal) return 0
            if (aVal == null) return 1
            if (bVal == null) return -1

            const comparison = aVal < bVal ? -1 : 1
            return sortState.direction === 'asc' ? comparison : -comparison
        })
    }, [data, sortState, columns])

    const allSelected = data.length > 0 && data.every((row, i) => selectedKeys.has(getRowKey(row, i)))
    const someSelected = data.some((row, i) => selectedKeys.has(getRowKey(row, i)))

    const handleSelectAll = () => {
        if (allSelected) {
            onSelectionChange?.(new Set())
        } else {
            onSelectionChange?.(new Set(data.map((row, i) => getRowKey(row, i))))
        }
    }

    const handleSelectRow = (key: string | number) => {
        const newKeys = new Set(selectedKeys)
        if (newKeys.has(key)) {
            newKeys.delete(key)
        } else {
            newKeys.add(key)
        }
        onSelectionChange?.(newKeys)
    }

    const SortIcon = ({ columnKey }: { columnKey: string }) => {
        if (sortState?.key !== columnKey) {
            return (
                <svg className="w-4 h-4 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
            )
        }
        return sortState.direction === 'asc' ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
        ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
        )
    }

    return (
        <div
            className={clsx(
                'relative rounded-xl border border-white/10/50 bg-dark-400/50 backdrop-blur-sm overflow-hidden',
                className
            )}
            {...props}
        >
            <div
                className={clsx('overflow-auto', maxHeight && 'overflow-y-auto')}
                style={{ maxHeight }}
            >
                <table className={tableVariants({ variant, size })}>
                    <thead
                        className={clsx(
                            'bg-dark-400/80 border-b border-white/10/50',
                            stickyHeader && 'sticky top-0 z-10'
                        )}
                    >
                        <tr>
                            {selectable && (
                                <th className={clsx(cellVariants({ size }), 'w-12')}>
                                    <input
                                        type="checkbox"
                                        checked={allSelected}
                                        ref={(el) => el && (el.indeterminate = someSelected && !allSelected)}
                                        onChange={handleSelectAll}
                                        className="w-4 h-4 rounded border-gray-600 bg-dark-300 text-primary-500 focus:ring-primary-500 focus:ring-offset-0"
                                    />
                                </th>
                            )}
                            {columns.map((column) => (
                                <th
                                    key={column.key}
                                    className={clsx(
                                        cellVariants({ size, align: column.align }),
                                        'font-semibold text-gray-300 whitespace-nowrap',
                                        column.sortable && 'cursor-pointer hover:text-white select-none',
                                        column.sticky && 'sticky left-0 bg-dark-400/80 z-10'
                                    )}
                                    style={{ width: column.width }}
                                    onClick={() => column.sortable && handleSort(column.key)}
                                >
                                    <div className="flex items-center gap-2">
                                        {column.header}
                                        {column.sortable && <SortIcon columnKey={column.key} />}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td
                                    colSpan={columns.length + (selectable ? 1 : 0)}
                                    className="text-center py-12"
                                >
                                    <div className="flex flex-col items-center gap-3 text-gray-400">
                                        <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        <span>Loading...</span>
                                    </div>
                                </td>
                            </tr>
                        ) : sortedData.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={columns.length + (selectable ? 1 : 0)}
                                    className="text-center py-12 text-gray-400"
                                >
                                    {emptyMessage}
                                </td>
                            </tr>
                        ) : (
                            sortedData.map((row, rowIndex) => {
                                const rowKey = getRowKey(row, rowIndex)
                                const isSelected = selectedKeys.has(rowKey)

                                return (
                                    <tr
                                        key={rowKey}
                                        className={clsx(
                                            'border-b border-white/10/30 last:border-0',
                                            hoverable && 'hover:bg-dark-300/30',
                                            isSelected && 'bg-primary-500/10',
                                            onRowClick && 'cursor-pointer',
                                            variant === 'striped' && rowIndex % 2 === 1 && 'bg-dark-400/30'
                                        )}
                                        onClick={() => onRowClick?.(row, rowIndex)}
                                    >
                                        {selectable && (
                                            <td
                                                className={cellVariants({ size })}
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => handleSelectRow(rowKey)}
                                                    className="w-4 h-4 rounded border-gray-600 bg-dark-300 text-primary-500 focus:ring-primary-500 focus:ring-offset-0"
                                                />
                                            </td>
                                        )}
                                        {columns.map((column) => {
                                            const cellContent = column.cell
                                                ? column.cell(row, rowIndex)
                                                : column.accessor
                                                    ? String(
                                                        typeof column.accessor === 'function'
                                                            ? column.accessor(row)
                                                            : row[column.accessor as keyof T] ?? ''
                                                    )
                                                    : ''

                                            return (
                                                <td
                                                    key={column.key}
                                                    className={clsx(
                                                        cellVariants({ size, align: column.align }),
                                                        'text-gray-200',
                                                        column.sticky && 'sticky left-0 bg-dark-400/80 z-10'
                                                    )}
                                                >
                                                    {cellContent}
                                                </td>
                                            )
                                        })}
                                    </tr>
                                )
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

// ============================================================================
// TABLE PAGINATION
// ============================================================================

export interface TablePaginationProps extends HTMLAttributes<HTMLDivElement> {
    /** Current page (1-indexed) */
    page: number
    /** Total number of pages */
    totalPages: number
    /** Total number of items */
    totalItems?: number
    /** Items per page */
    pageSize?: number
    /** Page change handler */
    onPageChange: (page: number) => void
    /** Page size options */
    pageSizeOptions?: number[]
    /** Page size change handler */
    onPageSizeChange?: (size: number) => void
    /** Show page size selector */
    showPageSize?: boolean
    /** Show item count */
    showItemCount?: boolean
}

export const TablePagination = forwardRef<HTMLDivElement, TablePaginationProps>(
    (
        {
            className,
            page,
            totalPages,
            totalItems,
            pageSize = 10,
            onPageChange,
            pageSizeOptions = [10, 25, 50, 100],
            onPageSizeChange,
            showPageSize = true,
            showItemCount = true,
            ...props
        },
        ref
    ) => {
        const startItem = (page - 1) * pageSize + 1
        const endItem = Math.min(page * pageSize, totalItems ?? page * pageSize)

        const getPageNumbers = () => {
            const pages: (number | 'ellipsis')[] = []
            const showPages = 5

            if (totalPages <= showPages + 2) {
                for (let i = 1; i <= totalPages; i++) pages.push(i)
            } else {
                pages.push(1)

                if (page > 3) pages.push('ellipsis')

                const start = Math.max(2, page - 1)
                const end = Math.min(totalPages - 1, page + 1)

                for (let i = start; i <= end; i++) pages.push(i)

                if (page < totalPages - 2) pages.push('ellipsis')

                pages.push(totalPages)
            }

            return pages
        }

        return (
            <div
                ref={ref}
                className={clsx(
                    'flex items-center justify-between gap-4 px-4 py-3 bg-dark-400/30 border-t border-white/10/50',
                    className
                )}
                {...props}
            >
                <div className="flex items-center gap-4 text-sm text-gray-400">
                    {showItemCount && totalItems != null && (
                        <span>
                            Showing {startItem}-{endItem} of {totalItems}
                        </span>
                    )}
                    {showPageSize && onPageSizeChange && (
                        <div className="flex items-center gap-2">
                            <span>Rows:</span>
                            <select
                                value={pageSize}
                                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                                className="bg-dark-300 border border-gray-600 rounded px-2 py-1 text-sm text-gray-200 focus:ring-primary-500 focus:border-primary-500"
                            >
                                {pageSizeOptions.map((size) => (
                                    <option key={size} value={size}>
                                        {size}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    {/* Previous */}
                    <button
                        type="button"
                        onClick={() => onPageChange(page - 1)}
                        disabled={page <= 1}
                        className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-dark-300/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        aria-label="Previous page"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                    </button>

                    {/* Page Numbers */}
                    {getPageNumbers().map((pageNum, i) =>
                        pageNum === 'ellipsis' ? (
                            <span key={`ellipsis-${i}`} className="px-2 text-gray-500">
                                ...
                            </span>
                        ) : (
                            <button
                                key={pageNum}
                                type="button"
                                onClick={() => onPageChange(pageNum)}
                                className={clsx(
                                    'min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-colors',
                                    page === pageNum
                                        ? 'bg-primary-500 text-white'
                                        : 'text-gray-400 hover:text-white hover:bg-dark-300/50'
                                )}
                            >
                                {pageNum}
                            </button>
                        )
                    )}

                    {/* Next */}
                    <button
                        type="button"
                        onClick={() => onPageChange(page + 1)}
                        disabled={page >= totalPages}
                        className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-dark-300/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        aria-label="Next page"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>
            </div>
        )
    }
)

TablePagination.displayName = 'TablePagination'
