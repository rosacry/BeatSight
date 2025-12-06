/**
 * Avatar and AvatarGroup components with status indicators and fallbacks.
 */

import {
    forwardRef,
    useState,
    type HTMLAttributes,
    type ReactNode,
} from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

// ============================================================================
// AVATAR
// ============================================================================

const avatarVariants = cva(
    [
        'relative inline-flex items-center justify-center',
        'overflow-hidden rounded-full bg-gray-700',
        'ring-2 ring-gray-800',
    ],
    {
        variants: {
            size: {
                xs: 'w-6 h-6 text-xs',
                sm: 'w-8 h-8 text-sm',
                md: 'w-10 h-10 text-base',
                lg: 'w-12 h-12 text-lg',
                xl: 'w-16 h-16 text-xl',
                '2xl': 'w-20 h-20 text-2xl',
            },
            variant: {
                default: '',
                bordered: 'ring-4',
                glow: 'ring-4 ring-primary-500/30',
            },
        },
        defaultVariants: {
            size: 'md',
            variant: 'default',
        },
    }
)

const statusVariants = cva(
    'absolute rounded-full border-2 border-gray-800',
    {
        variants: {
            status: {
                online: 'bg-green-500',
                offline: 'bg-gray-500',
                busy: 'bg-red-500',
                away: 'bg-yellow-500',
            },
            size: {
                xs: 'w-1.5 h-1.5 right-0 bottom-0',
                sm: 'w-2 h-2 right-0 bottom-0',
                md: 'w-2.5 h-2.5 right-0 bottom-0',
                lg: 'w-3 h-3 right-0 bottom-0',
                xl: 'w-3.5 h-3.5 right-0 bottom-0',
                '2xl': 'w-4 h-4 right-0.5 bottom-0.5',
            },
        },
        defaultVariants: {
            status: 'offline',
            size: 'md',
        },
    }
)

export interface AvatarProps
    extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
    /** Image source */
    src?: string
    /** Alt text */
    alt?: string
    /** Fallback text (usually initials) */
    fallback?: string
    /** Status indicator */
    status?: 'online' | 'offline' | 'busy' | 'away'
    /** Custom fallback icon */
    fallbackIcon?: ReactNode
    /** Gradient background when no image */
    gradient?: boolean
}

export const Avatar = forwardRef<HTMLDivElement, AvatarProps>(
    (
        {
            className,
            size,
            variant,
            src,
            alt,
            fallback,
            status,
            fallbackIcon,
            gradient = false,
            ...props
        },
        ref
    ) => {
        const [imageError, setImageError] = useState(false)
        const showFallback = !src || imageError

        // Generate gradient from fallback text
        const gradientColors = fallback
            ? getGradientFromString(fallback)
            : ['from-gray-600', 'to-gray-700']

        return (
            <div
                ref={ref}
                className={clsx(
                    avatarVariants({ size, variant }),
                    gradient && showFallback && `bg-gradient-to-br ${gradientColors.join(' ')}`,
                    className
                )}
                {...props}
            >
                {!showFallback && (
                    <img
                        src={src}
                        alt={alt || fallback || 'Avatar'}
                        className="w-full h-full object-cover"
                        onError={() => setImageError(true)}
                    />
                )}

                {showFallback && (
                    <>
                        {fallbackIcon || (
                            <span className="font-medium text-white uppercase select-none">
                                {fallback?.slice(0, 2) || (
                                    <svg className="w-1/2 h-1/2 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                                    </svg>
                                )}
                            </span>
                        )}
                    </>
                )}

                {status && (
                    <span className={statusVariants({ status, size })} aria-label={`Status: ${status}`} />
                )}
            </div>
        )
    }
)

Avatar.displayName = 'Avatar'

// Helper to generate consistent gradient from string
function getGradientFromString(str: string): string[] {
    const hash = str.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
    const gradients = [
        ['from-blue-500', 'to-purple-600'],
        ['from-green-500', 'to-teal-600'],
        ['from-orange-500', 'to-red-600'],
        ['from-pink-500', 'to-rose-600'],
        ['from-indigo-500', 'to-blue-600'],
        ['from-cyan-500', 'to-blue-600'],
        ['from-amber-500', 'to-orange-600'],
        ['from-violet-500', 'to-purple-600'],
    ]
    return gradients[hash % gradients.length]
}

// ============================================================================
// AVATAR GROUP
// ============================================================================

export interface AvatarGroupProps extends HTMLAttributes<HTMLDivElement> {
    /** Maximum avatars to show */
    max?: number
    /** Avatar size */
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'
    /** Children should be Avatar components */
    children: ReactNode
}

export const AvatarGroup = forwardRef<HTMLDivElement, AvatarGroupProps>(
    ({ className, max = 4, size = 'md', children, ...props }, ref) => {
        const avatars = Array.isArray(children) ? children : [children]
        const visibleAvatars = avatars.slice(0, max)
        const remainingCount = avatars.length - max

        const overlapClasses: Record<string, string> = {
            xs: '-ml-1.5',
            sm: '-ml-2',
            md: '-ml-2.5',
            lg: '-ml-3',
            xl: '-ml-4',
            '2xl': '-ml-5',
        }

        return (
            <div ref={ref} className={clsx('flex items-center', className)} {...props}>
                {visibleAvatars.map((avatar, index) => (
                    <div
                        key={index}
                        className={clsx(index > 0 && overlapClasses[size])}
                        style={{ zIndex: visibleAvatars.length - index }}
                    >
                        {avatar}
                    </div>
                ))}

                {remainingCount > 0 && (
                    <div
                        className={clsx(
                            avatarVariants({ size }),
                            'bg-gray-700 text-gray-300 font-medium',
                            overlapClasses[size]
                        )}
                        style={{ zIndex: 0 }}
                    >
                        +{remainingCount}
                    </div>
                )}
            </div>
        )
    }
)

AvatarGroup.displayName = 'AvatarGroup'

// ============================================================================
// AVATAR WITH NAME
// ============================================================================

export interface AvatarWithNameProps extends AvatarProps {
    /** Display name */
    name: string
    /** Secondary text (e.g., role, email) */
    description?: string
    /** Reverse layout (name on left) */
    reverse?: boolean
}

export const AvatarWithName = forwardRef<HTMLDivElement, AvatarWithNameProps>(
    ({ className, name, description, reverse = false, ...avatarProps }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'flex items-center gap-3',
                    reverse && 'flex-row-reverse',
                    className
                )}
            >
                <Avatar {...avatarProps} fallback={avatarProps.fallback || name} />
                <div className={clsx('flex flex-col', reverse && 'items-end')}>
                    <span className="font-medium text-white">{name}</span>
                    {description && (
                        <span className="text-sm text-gray-400">{description}</span>
                    )}
                </div>
            </div>
        )
    }
)

AvatarWithName.displayName = 'AvatarWithName'

// ============================================================================
// AVATAR UPLOAD
// ============================================================================

export interface AvatarUploadProps extends Omit<AvatarProps, 'src'> {
    /** Current image source */
    src?: string
    /** Upload handler */
    onUpload?: (file: File) => void
    /** Accept file types */
    accept?: string
    /** Disabled state */
    disabled?: boolean
    /** Upload label */
    uploadLabel?: string
}

export const AvatarUpload = forwardRef<HTMLDivElement, AvatarUploadProps>(
    (
        {
            className,
            src,
            onUpload,
            accept = 'image/*',
            disabled = false,
            uploadLabel = 'Upload',
            ...avatarProps
        },
        ref
    ) => {
        const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            const file = e.target.files?.[0]
            if (file) {
                onUpload?.(file)
            }
        }

        return (
            <div ref={ref} className={clsx('relative group', className)}>
                <Avatar src={src} {...avatarProps} />

                {!disabled && (
                    <label
                        className={clsx(
                            'absolute inset-0 flex items-center justify-center',
                            'rounded-full bg-black/60 opacity-0 group-hover:opacity-100',
                            'cursor-pointer transition-opacity'
                        )}
                    >
                        <div className="flex flex-col items-center text-white">
                            <svg className="w-5 h-5 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span className="text-xs">{uploadLabel}</span>
                        </div>
                        <input
                            type="file"
                            accept={accept}
                            onChange={handleFileChange}
                            className="sr-only"
                        />
                    </label>
                )}
            </div>
        )
    }
)

AvatarUpload.displayName = 'AvatarUpload'
