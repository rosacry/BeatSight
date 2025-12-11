/**
 * Navigation components including breadcrumbs, sidebar, and navigation menu.
 */

import {
    forwardRef,
    createContext,
    useContext,
    useState,
    useRef,
    useEffect,
    type HTMLAttributes,
    type ReactNode,
} from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

// ============================================================================
// BREADCRUMB
// ============================================================================

export interface BreadcrumbItem {
    label: string
    href?: string
    icon?: ReactNode
}

export interface BreadcrumbProps extends HTMLAttributes<HTMLElement> {
    /** Breadcrumb items */
    items: BreadcrumbItem[]
    /** Custom separator */
    separator?: ReactNode
    /** Max items to show (collapses middle) */
    maxItems?: number
    /** Custom link renderer */
    renderLink?: (item: BreadcrumbItem, index: number) => ReactNode
}

export const Breadcrumb = forwardRef<HTMLElement, BreadcrumbProps>(
    (
        {
            className,
            items,
            separator,
            maxItems,
            renderLink,
        },
        ref
    ) => {
        const DefaultSeparator = () => (
            <svg className="w-4 h-4 text-gray-500 mx-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
        )

        let displayItems = items

        if (maxItems && items.length > maxItems) {
            const start = items.slice(0, 1)
            const end = items.slice(-(maxItems - 1))
            displayItems = [...start, { label: '...' }, ...end]
        }

        const defaultRenderLink = (item: BreadcrumbItem, isLast: boolean) => {
            const content = (
                <span className="flex items-center gap-1.5">
                    {item.icon}
                    {item.label}
                </span>
            )

            if (isLast || !item.href) {
                return (
                    <span className={clsx('text-sm', isLast ? 'text-white font-medium' : 'text-gray-400')}>
                        {content}
                    </span>
                )
            }

            return (
                <a
                    href={item.href}
                    className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                    {content}
                </a>
            )
        }

        return (
            <nav ref={ref} aria-label="Breadcrumb" className={clsx('flex items-center', className)}>
                <ol className="flex items-center">
                    {displayItems.map((item, index) => {
                        const isLast = index === displayItems.length - 1

                        return (
                            <li key={index} className="flex items-center">
                                {renderLink
                                    ? renderLink(item, index)
                                    : defaultRenderLink(item, isLast)}
                                {!isLast && (separator || <DefaultSeparator />)}
                            </li>
                        )
                    })}
                </ol>
            </nav>
        )
    }
)

Breadcrumb.displayName = 'Breadcrumb'

// ============================================================================
// NAVIGATION MENU
// ============================================================================

const navMenuVariants = cva(
    'flex',
    {
        variants: {
            orientation: {
                horizontal: 'flex-row items-center gap-1',
                vertical: 'flex-col gap-0.5',
            },
        },
        defaultVariants: {
            orientation: 'horizontal',
        },
    }
)

const navItemVariants = cva(
    [
        'relative flex items-center gap-2 px-3 py-2 rounded-lg',
        'text-sm font-medium transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
    ],
    {
        variants: {
            active: {
                true: 'text-white bg-dark-300/50',
                false: 'text-gray-400 hover:text-white hover:bg-dark-400/50',
            },
            variant: {
                default: '',
                pill: 'rounded-full',
                underline: 'rounded-none border-b-2 border-transparent',
            },
        },
        compoundVariants: [
            {
                active: true,
                variant: 'underline',
                className: 'border-primary-500 bg-transparent rounded-none',
            },
        ],
        defaultVariants: {
            active: false,
            variant: 'default',
        },
    }
)

interface NavContextValue {
    activeItem: string | null
    setActiveItem: (id: string) => void
    orientation: 'horizontal' | 'vertical'
    variant: 'default' | 'pill' | 'underline'
}

const NavContext = createContext<NavContextValue | null>(null)

export interface NavMenuProps
    extends HTMLAttributes<HTMLElement>,
    VariantProps<typeof navMenuVariants> {
    /** Active item ID */
    activeItem?: string
    /** Active item change handler */
    onActiveChange?: (id: string) => void
    /** Visual variant */
    variant?: 'default' | 'pill' | 'underline'
    children: ReactNode
}

export const NavMenu = forwardRef<HTMLElement, NavMenuProps>(
    (
        {
            className,
            orientation = 'horizontal',
            activeItem: controlledActive,
            onActiveChange,
            variant = 'default',
            children,
            ...props
        },
        ref
    ) => {
        const [internalActive, setInternalActive] = useState<string | null>(null)
        const activeItem = controlledActive ?? internalActive

        const setActiveItem = (id: string) => {
            setInternalActive(id)
            onActiveChange?.(id)
        }

        return (
            <NavContext.Provider value={{ activeItem, setActiveItem, orientation: orientation!, variant }}>
                <nav
                    ref={ref}
                    className={clsx(navMenuVariants({ orientation }), className)}
                    {...props}
                >
                    {children}
                </nav>
            </NavContext.Provider>
        )
    }
)

NavMenu.displayName = 'NavMenu'

export interface NavItemProps extends HTMLAttributes<HTMLButtonElement> {
    /** Unique ID for this item */
    id: string
    /** Item icon */
    icon?: ReactNode
    /** Badge content */
    badge?: ReactNode
    /** Disabled state */
    disabled?: boolean
    /** Link href (makes it an anchor) */
    href?: string
}

export const NavItem = forwardRef<HTMLButtonElement, NavItemProps>(
    ({ className, id, icon, badge, disabled = false, href, children, onClick, ...props }, ref) => {
        const context = useContext(NavContext)
        if (!context) throw new Error('NavItem must be used within NavMenu')

        const { activeItem, setActiveItem, variant } = context
        const isActive = activeItem === id

        const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
            if (!disabled) {
                setActiveItem(id)
                onClick?.(e)
            }
        }

        const content = (
            <>
                {icon && <span className="flex-shrink-0">{icon}</span>}
                <span>{children}</span>
                {badge && (
                    <span className="ml-auto px-1.5 py-0.5 text-xs font-medium bg-primary-500/20 text-primary-400 rounded-full">
                        {badge}
                    </span>
                )}
                {isActive && variant === 'default' && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-primary-500 rounded-full" />
                )}
            </>
        )

        if (href) {
            return (
                <a
                    href={href}
                    className={clsx(
                        navItemVariants({ active: isActive, variant }),
                        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
                        className
                    )}
                    aria-current={isActive ? 'page' : undefined}
                >
                    {content}
                </a>
            )
        }

        return (
            <button
                ref={ref}
                type="button"
                className={clsx(
                    navItemVariants({ active: isActive, variant }),
                    disabled && 'opacity-50 cursor-not-allowed',
                    className
                )}
                onClick={handleClick}
                disabled={disabled}
                aria-current={isActive ? 'page' : undefined}
                {...props}
            >
                {content}
            </button>
        )
    }
)

NavItem.displayName = 'NavItem'

// ============================================================================
// SIDEBAR
// ============================================================================

export interface SidebarProps extends HTMLAttributes<HTMLElement> {
    /** Collapsed state */
    collapsed?: boolean
    /** Width when expanded */
    width?: number
    /** Width when collapsed */
    collapsedWidth?: number
    children: ReactNode
}

export const Sidebar = forwardRef<HTMLElement, SidebarProps>(
    (
        {
            className,
            collapsed = false,
            width = 256,
            collapsedWidth = 64,
            children,
            ...props
        },
        ref
    ) => {
        return (
            <aside
                ref={ref}
                className={clsx(
                    'h-full bg-dark-500 border-r border-white/10 transition-all duration-300 overflow-hidden',
                    className
                )}
                style={{ width: collapsed ? collapsedWidth : width }}
                {...props}
            >
                <div className="h-full flex flex-col">{children}</div>
            </aside>
        )
    }
)

Sidebar.displayName = 'Sidebar'

export interface SidebarSectionProps extends HTMLAttributes<HTMLDivElement> {
    /** Section title */
    title?: string
    /** Collapsible */
    collapsible?: boolean
    /** Default collapsed state */
    defaultCollapsed?: boolean
}

export const SidebarSection = forwardRef<HTMLDivElement, SidebarSectionProps>(
    ({ className, title, collapsible = false, defaultCollapsed = false, children, ...props }, ref) => {
        const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed)
        const contentRef = useRef<HTMLDivElement>(null)
        const [contentHeight, setContentHeight] = useState<number | 'auto'>('auto')

        useEffect(() => {
            if (contentRef.current) {
                setContentHeight(contentRef.current.scrollHeight)
            }
        }, [children])

        return (
            <div ref={ref} className={clsx('py-2', className)} {...props}>
                {title && (
                    <div
                        className={clsx(
                            'px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider',
                            collapsible && 'cursor-pointer hover:text-gray-400 flex items-center justify-between'
                        )}
                        onClick={() => collapsible && setIsCollapsed(!isCollapsed)}
                    >
                        {title}
                        {collapsible && (
                            <motion.svg
                                animate={{ rotate: isCollapsed ? -90 : 0 }}
                                transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                                className="w-4 h-4"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </motion.svg>
                        )}
                    </div>
                )}
                <AnimatePresence initial={false}>
                    {(!collapsible || !isCollapsed) && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: contentHeight, opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                            className="overflow-hidden"
                        >
                            <div ref={contentRef} className="space-y-0.5 px-2">{children}</div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        )
    }
)

SidebarSection.displayName = 'SidebarSection'

export interface SidebarItemProps extends HTMLAttributes<HTMLButtonElement> {
    /** Item icon */
    icon?: ReactNode
    /** Active state */
    active?: boolean
    /** Badge content */
    badge?: ReactNode
    /** Link href */
    href?: string
    /** Collapsed mode (show only icon) */
    collapsed?: boolean
}

export const SidebarItem = forwardRef<HTMLButtonElement, SidebarItemProps>(
    ({ className, icon, active = false, badge, href, collapsed = false, children, ...props }, ref) => {
        const content = (
            <>
                {icon && (
                    <span className={clsx('flex-shrink-0', collapsed ? 'mx-auto' : '')}>
                        {icon}
                    </span>
                )}
                {!collapsed && (
                    <>
                        <span className="flex-1 truncate">{children}</span>
                        {badge && (
                            <span className="px-1.5 py-0.5 text-xs font-medium bg-primary-500/20 text-primary-400 rounded-full">
                                {badge}
                            </span>
                        )}
                    </>
                )}
            </>
        )

        const classes = clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            active
                ? 'bg-primary-500/10 text-primary-400'
                : 'text-gray-400 hover:text-white hover:bg-dark-400/50',
            collapsed && 'justify-center',
            className
        )

        if (href) {
            return (
                <a href={href} className={classes}>
                    {content}
                </a>
            )
        }

        return (
            <button ref={ref} type="button" className={classes} {...props}>
                {content}
            </button>
        )
    }
)

SidebarItem.displayName = 'SidebarItem'

// ============================================================================
// PAGINATION
// ============================================================================

export interface PaginationProps extends HTMLAttributes<HTMLElement> {
    /** Current page */
    page: number
    /** Total pages */
    totalPages: number
    /** Page change handler */
    onPageChange: (page: number) => void
    /** Show first/last buttons */
    showFirstLast?: boolean
    /** Siblings on each side of current */
    siblings?: number
}

export const Pagination = forwardRef<HTMLElement, PaginationProps>(
    (
        {
            className,
            page,
            totalPages,
            onPageChange,
            showFirstLast = true,
            siblings = 1,
            ...props
        },
        ref
    ) => {
        const getPageNumbers = () => {
            const pages: (number | 'ellipsis')[] = []

            // Always show first page
            pages.push(1)

            // Calculate range around current page
            const rangeStart = Math.max(2, page - siblings)
            const rangeEnd = Math.min(totalPages - 1, page + siblings)

            // Add ellipsis after first if needed
            if (rangeStart > 2) {
                pages.push('ellipsis')
            }

            // Add pages in range
            for (let i = rangeStart; i <= rangeEnd; i++) {
                pages.push(i)
            }

            // Add ellipsis before last if needed
            if (rangeEnd < totalPages - 1) {
                pages.push('ellipsis')
            }

            // Always show last page if > 1
            if (totalPages > 1) {
                pages.push(totalPages)
            }

            return pages
        }

        const PageButton = ({
            pageNum,
            children,
            disabled,
            ...btnProps
        }: {
            pageNum?: number
            children: ReactNode
            disabled?: boolean
        } & HTMLAttributes<HTMLButtonElement>) => (
            <button
                type="button"
                onClick={() => pageNum && onPageChange(pageNum)}
                disabled={disabled}
                className={clsx(
                    'min-w-[36px] h-9 px-2 flex items-center justify-center rounded-lg text-sm font-medium transition-colors',
                    pageNum === page
                        ? 'bg-primary-500 text-white'
                        : disabled
                            ? 'text-gray-600 cursor-not-allowed'
                            : 'text-gray-400 hover:text-white hover:bg-dark-300/50'
                )}
                {...btnProps}
            >
                {children}
            </button>
        )

        return (
            <nav ref={ref} className={clsx('flex items-center gap-1', className)} aria-label="Pagination" {...props}>
                {showFirstLast && (
                    <PageButton pageNum={1} disabled={page === 1} aria-label="First page">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                        </svg>
                    </PageButton>
                )}

                <PageButton pageNum={page - 1} disabled={page === 1} aria-label="Previous page">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                </PageButton>

                {getPageNumbers().map((num, i) =>
                    num === 'ellipsis' ? (
                        <span key={`ellipsis-${i}`} className="px-2 text-gray-500">
                            ...
                        </span>
                    ) : (
                        <PageButton key={num} pageNum={num}>
                            {num}
                        </PageButton>
                    )
                )}

                <PageButton pageNum={page + 1} disabled={page === totalPages} aria-label="Next page">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                </PageButton>

                {showFirstLast && (
                    <PageButton pageNum={totalPages} disabled={page === totalPages} aria-label="Last page">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                        </svg>
                    </PageButton>
                )}
            </nav>
        )
    }
)

Pagination.displayName = 'Pagination'
