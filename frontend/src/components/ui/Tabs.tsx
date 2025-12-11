/**
 * Tabs Components
 * Modern, animated tab navigation with keyboard accessibility.
 */

import React, { useState, createContext, useContext, useCallback, useRef, useEffect } from 'react'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Tabs Context
// ============================================================================

interface TabsContextType {
    activeTab: string
    setActiveTab: (id: string) => void
    variant: 'default' | 'pills' | 'underline' | 'contained'
    orientation: 'horizontal' | 'vertical'
    registerTab: (id: string) => void
    tabs: string[]
}

const TabsContext = createContext<TabsContextType | null>(null)

const useTabs = () => {
    const context = useContext(TabsContext)
    if (!context) {
        throw new Error('Tab components must be used within a Tabs provider')
    }
    return context
}

// ============================================================================
// Tabs Variants
// ============================================================================

const tabsListVariants = cva(['flex gap-1'], {
    variants: {
        variant: {
            default: 'bg-dark-500/50 p-1 rounded-lg border border-white/10/50',
            pills: 'gap-2',
            underline: 'border-b border-white/10 pb-0 gap-0',
            contained: 'bg-dark-400/30 rounded-t-lg',
        },
        orientation: {
            horizontal: 'flex-row',
            vertical: 'flex-col',
        },
    },
    defaultVariants: {
        variant: 'default',
        orientation: 'horizontal',
    },
})

const tabTriggerVariants = cva(
    [
        'relative inline-flex items-center justify-center gap-2',
        'text-sm font-medium transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
    ],
    {
        variants: {
            variant: {
                default: [
                    'rounded-md px-3 py-1.5',
                    'text-gray-400 hover:text-gray-200',
                    'data-[state=active]:bg-dark-400 data-[state=active]:text-primary-400',
                    'data-[state=active]:shadow-sm',
                ],
                pills: [
                    'rounded-full px-4 py-2',
                    'text-gray-400 hover:text-gray-200 hover:bg-dark-400',
                    'data-[state=active]:bg-primary-500/20 data-[state=active]:text-primary-400',
                    'data-[state=active]:ring-1 data-[state=active]:ring-primary-500/30',
                ],
                underline: [
                    'px-4 py-2.5 -mb-px',
                    'text-gray-400 hover:text-gray-200',
                    'border-b-2 border-transparent',
                    'data-[state=active]:border-primary-500 data-[state=active]:text-primary-400',
                ],
                contained: [
                    'px-4 py-2.5 rounded-t-lg',
                    'text-gray-400 hover:text-gray-200',
                    'data-[state=active]:bg-dark-500 data-[state=active]:text-primary-400',
                    'data-[state=active]:border-t data-[state=active]:border-x data-[state=active]:border-white/10',
                ],
            },
        },
        defaultVariants: {
            variant: 'default',
        },
    }
)

const tabContentVariants = cva(['focus:outline-none'], {
    variants: {
        variant: {
            default: 'pt-4',
            pills: 'pt-4',
            underline: 'pt-4',
            contained: 'bg-dark-500 border border-white/10 border-t-0 rounded-b-lg p-4',
        },
    },
    defaultVariants: {
        variant: 'default',
    },
})

// ============================================================================
// Tabs Root Component
// ============================================================================

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
    defaultValue?: string
    value?: string
    onValueChange?: (value: string) => void
    variant?: 'default' | 'pills' | 'underline' | 'contained'
    orientation?: 'horizontal' | 'vertical'
}

export function Tabs({
    defaultValue,
    value,
    onValueChange,
    variant = 'default',
    orientation = 'horizontal',
    children,
    className,
    ...props
}: TabsProps) {
    const [activeTab, setActiveTabState] = useState(value ?? defaultValue ?? '')
    const [tabs, setTabs] = useState<string[]>([])

    const setActiveTab = useCallback(
        (id: string) => {
            setActiveTabState(id)
            onValueChange?.(id)
        },
        [onValueChange]
    )

    const registerTab = useCallback((id: string) => {
        setTabs((prev) => (prev.includes(id) ? prev : [...prev, id]))
    }, [])

    // Sync with controlled value
    useEffect(() => {
        if (value !== undefined) {
            setActiveTabState(value)
        }
    }, [value])

    return (
        <TabsContext.Provider
            value={{
                activeTab,
                setActiveTab,
                variant,
                orientation,
                registerTab,
                tabs,
            }}
        >
            <div
                className={cn(orientation === 'vertical' && 'flex gap-4', className)}
                data-orientation={orientation}
                {...props}
            >
                {children}
            </div>
        </TabsContext.Provider>
    )
}

// ============================================================================
// Tabs List
// ============================================================================

export type TabsListProps = React.HTMLAttributes<HTMLDivElement>

export function TabsList({ className, children, ...props }: TabsListProps) {
    const { variant, orientation, tabs, activeTab, setActiveTab } = useTabs()
    const listRef = useRef<HTMLDivElement>(null)

    const handleKeyDown = (e: React.KeyboardEvent) => {
        const currentIndex = tabs.indexOf(activeTab)
        const isHorizontal = orientation === 'horizontal'

        let nextIndex = -1

        if ((isHorizontal && e.key === 'ArrowRight') || (!isHorizontal && e.key === 'ArrowDown')) {
            nextIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0
        } else if ((isHorizontal && e.key === 'ArrowLeft') || (!isHorizontal && e.key === 'ArrowUp')) {
            nextIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1
        } else if (e.key === 'Home') {
            nextIndex = 0
        } else if (e.key === 'End') {
            nextIndex = tabs.length - 1
        }

        if (nextIndex !== -1) {
            e.preventDefault()
            setActiveTab(tabs[nextIndex])
            // Focus the tab button
            const tabButtons = listRef.current?.querySelectorAll('[role="tab"]')
                ; (tabButtons?.[nextIndex] as HTMLElement)?.focus()
        }
    }

    return (
        <div
            ref={listRef}
            role="tablist"
            aria-orientation={orientation}
            onKeyDown={handleKeyDown}
            className={cn(tabsListVariants({ variant, orientation }), className)}
            {...props}
        >
            {children}
        </div>
    )
}

// ============================================================================
// Tab Trigger
// ============================================================================

export interface TabTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    value: string
    icon?: React.ReactNode
    badge?: React.ReactNode
}

export const TabTrigger = React.forwardRef<HTMLButtonElement, TabTriggerProps>(
    ({ value, icon, badge, className, children, disabled, ...props }, ref) => {
        const { activeTab, setActiveTab, variant, registerTab } = useTabs()
        const isActive = activeTab === value

        // Register this tab
        useEffect(() => {
            registerTab(value)
        }, [value, registerTab])

        return (
            <button
                ref={ref}
                role="tab"
                type="button"
                aria-selected={isActive}
                aria-controls={`panel-${value}`}
                tabIndex={isActive ? 0 : -1}
                data-state={isActive ? 'active' : 'inactive'}
                disabled={disabled}
                onClick={() => setActiveTab(value)}
                className={cn(tabTriggerVariants({ variant }), className)}
                {...props}
            >
                {icon && <span className="flex-shrink-0">{icon}</span>}
                {children}
                {badge && <span className="ml-1.5">{badge}</span>}
            </button>
        )
    }
)
TabTrigger.displayName = 'TabTrigger'

// ============================================================================
// Tab Content
// ============================================================================

export interface TabContentProps extends React.HTMLAttributes<HTMLDivElement> {
    value: string
    forceMount?: boolean
}

export function TabContent({ value, forceMount = false, className, children, ...props }: TabContentProps) {
    const { activeTab, variant } = useTabs()
    const isActive = activeTab === value

    if (!isActive && !forceMount) {
        return null
    }

    return (
        <div
            role="tabpanel"
            id={`panel-${value}`}
            aria-labelledby={value}
            tabIndex={0}
            hidden={!isActive}
            data-state={isActive ? 'active' : 'inactive'}
            className={cn(
                tabContentVariants({ variant }),
                isActive && 'animate-in fade-in-0 slide-in-from-left-1 duration-200',
                !isActive && forceMount && 'hidden',
                className
            )}
            {...props}
        >
            {children}
        </div>
    )
}

// ============================================================================
// Animated Tab Indicator (for underline variant)
// ============================================================================

export interface TabIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
    layoutId?: string
}

export function TabIndicator({ className, ...props }: TabIndicatorProps) {
    return (
        <div
            className={cn(
                'absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-primary-500 to-magenta-500',
                'transition-all duration-300 ease-out',
                className
            )}
            {...props}
        />
    )
}

// ============================================================================
// Preset: Icon Tabs
// ============================================================================

export interface IconTabsProps {
    tabs: Array<{
        value: string
        label: string
        icon: React.ReactNode
        content: React.ReactNode
        badge?: React.ReactNode
        disabled?: boolean
    }>
    defaultValue?: string
    value?: string
    onValueChange?: (value: string) => void
    variant?: 'default' | 'pills' | 'underline' | 'contained'
    className?: string
}

export function IconTabs({
    tabs: tabItems,
    defaultValue,
    value,
    onValueChange,
    variant = 'default',
    className,
}: IconTabsProps) {
    return (
        <Tabs
            defaultValue={defaultValue ?? tabItems[0]?.value}
            value={value}
            onValueChange={onValueChange}
            variant={variant}
            className={className}
        >
            <TabsList>
                {tabItems.map((tab) => (
                    <TabTrigger
                        key={tab.value}
                        value={tab.value}
                        icon={tab.icon}
                        badge={tab.badge}
                        disabled={tab.disabled}
                    >
                        {tab.label}
                    </TabTrigger>
                ))}
            </TabsList>
            {tabItems.map((tab) => (
                <TabContent key={tab.value} value={tab.value}>
                    {tab.content}
                </TabContent>
            ))}
        </Tabs>
    )
}

// ============================================================================
// Preset: Vertical Tabs
// ============================================================================

export interface VerticalTabsProps extends Omit<IconTabsProps, 'variant'> {
    listClassName?: string
    contentClassName?: string
}

export function VerticalTabs({
    tabs: tabItems,
    defaultValue,
    value,
    onValueChange,
    className,
    listClassName,
    contentClassName,
}: VerticalTabsProps) {
    return (
        <Tabs
            defaultValue={defaultValue ?? tabItems[0]?.value}
            value={value}
            onValueChange={onValueChange}
            variant="default"
            orientation="vertical"
            className={cn('flex gap-6', className)}
        >
            <TabsList className={cn('flex-col min-w-[200px]', listClassName)}>
                {tabItems.map((tab) => (
                    <TabTrigger
                        key={tab.value}
                        value={tab.value}
                        icon={tab.icon}
                        badge={tab.badge}
                        disabled={tab.disabled}
                        className="justify-start w-full"
                    >
                        {tab.label}
                    </TabTrigger>
                ))}
            </TabsList>
            <div className={cn('flex-1', contentClassName)}>
                {tabItems.map((tab) => (
                    <TabContent key={tab.value} value={tab.value}>
                        {tab.content}
                    </TabContent>
                ))}
            </div>
        </Tabs>
    )
}

export { tabsListVariants, tabTriggerVariants, tabContentVariants }
