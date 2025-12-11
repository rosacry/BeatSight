/**
 * Micro-interaction Components
 * Delightful, small-scale interactions that enhance user experience.
 */

import React, {
  forwardRef,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
  type HTMLAttributes,
  type ButtonHTMLAttributes,
} from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// RIPPLE EFFECT
// ============================================================================

interface RippleProps {
  color?: string
  duration?: number
}

interface RippleInstance {
  id: number
  x: number
  y: number
  size: number
}

/**
 * Ripple effect hook for buttons and clickable elements
 */
export function useRipple({ color = 'rgba(255, 255, 255, 0.3)', duration = 600 }: RippleProps = {}) {
  const [ripples, setRipples] = useState<RippleInstance[]>([])

  const addRipple = useCallback((event: React.MouseEvent<HTMLElement>) => {
    const element = event.currentTarget
    const rect = element.getBoundingClientRect()
    const size = Math.max(rect.width, rect.height) * 2
    const x = event.clientX - rect.left - size / 2
    const y = event.clientY - rect.top - size / 2

    const newRipple: RippleInstance = {
      id: Date.now(),
      x,
      y,
      size,
    }

    setRipples((prev) => [...prev, newRipple])

    setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== newRipple.id))
    }, duration)
  }, [duration])

  const RippleContainer = () => (
    <span className="absolute inset-0 overflow-hidden rounded-[inherit] pointer-events-none">
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="absolute rounded-full animate-ripple"
          style={{
            left: ripple.x,
            top: ripple.y,
            width: ripple.size,
            height: ripple.size,
            backgroundColor: color,
          }}
        />
      ))}
    </span>
  )

  return { addRipple, RippleContainer }
}

// ============================================================================
// MAGNETIC BUTTON
// ============================================================================

interface MagneticButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  strength?: number
  radius?: number
}

export type { MagneticButtonProps }

/**
 * Button that follows cursor with magnetic effect
 */
export const MagneticButton = forwardRef<HTMLButtonElement, MagneticButtonProps>(
  ({ children, className, strength = 0.3, radius = 200, ...props }, ref) => {
    const buttonRef = useRef<HTMLButtonElement>(null)
    const [position, setPosition] = useState({ x: 0, y: 0 })

    const handleMouseMove = useCallback((e: MouseEvent) => {
      if (!buttonRef.current) return

      const rect = buttonRef.current.getBoundingClientRect()
      const centerX = rect.left + rect.width / 2
      const centerY = rect.top + rect.height / 2
      const distance = Math.sqrt(
        Math.pow(e.clientX - centerX, 2) + Math.pow(e.clientY - centerY, 2)
      )

      if (distance < radius) {
        const x = (e.clientX - centerX) * strength
        const y = (e.clientY - centerY) * strength
        setPosition({ x, y })
      } else {
        setPosition({ x: 0, y: 0 })
      }
    }, [strength, radius])

    const handleMouseLeave = useCallback(() => {
      setPosition({ x: 0, y: 0 })
    }, [])

    useEffect(() => {
      window.addEventListener('mousemove', handleMouseMove)
      return () => window.removeEventListener('mousemove', handleMouseMove)
    }, [handleMouseMove])

    return (
      <button
        ref={(el) => {
          (buttonRef as React.MutableRefObject<HTMLButtonElement | null>).current = el
          if (typeof ref === 'function') ref(el)
          else if (ref) ref.current = el
        }}
        className={cn(
          'relative transition-transform duration-200 ease-out',
          className
        )}
        style={{
          transform: `translate(${position.x}px, ${position.y}px)`,
        }}
        onMouseLeave={handleMouseLeave}
        {...props}
      >
        {children}
      </button>
    )
  }
)
MagneticButton.displayName = 'MagneticButton'

// ============================================================================
// TILT CARD
// ============================================================================

interface TiltCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  tiltAmount?: number
  glareEnabled?: boolean
  glareOpacity?: number
  perspective?: number
}

export type { TiltCardProps }

/**
 * Card with 3D tilt effect on hover
 */
export const TiltCard = forwardRef<HTMLDivElement, TiltCardProps>(
  (
    {
      children,
      className,
      tiltAmount = 10,
      glareEnabled = true,
      glareOpacity = 0.2,
      perspective = 1000,
      ...props
    },
    ref
  ) => {
    const cardRef = useRef<HTMLDivElement>(null)
    const [transform, setTransform] = useState({ rotateX: 0, rotateY: 0 })
    const [glarePosition, setGlarePosition] = useState({ x: 50, y: 50 })

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return

      const rect = cardRef.current.getBoundingClientRect()
      const centerX = rect.left + rect.width / 2
      const centerY = rect.top + rect.height / 2
      const mouseX = e.clientX - centerX
      const mouseY = e.clientY - centerY

      const rotateX = (-mouseY / (rect.height / 2)) * tiltAmount
      const rotateY = (mouseX / (rect.width / 2)) * tiltAmount

      setTransform({ rotateX, rotateY })

      // Update glare position
      const glareX = ((e.clientX - rect.left) / rect.width) * 100
      const glareY = ((e.clientY - rect.top) / rect.height) * 100
      setGlarePosition({ x: glareX, y: glareY })
    }, [tiltAmount])

    const handleMouseLeave = useCallback(() => {
      setTransform({ rotateX: 0, rotateY: 0 })
      setGlarePosition({ x: 50, y: 50 })
    }, [])

    return (
      <div
        ref={(el) => {
          (cardRef as React.MutableRefObject<HTMLDivElement | null>).current = el
          if (typeof ref === 'function') ref(el)
          else if (ref) ref.current = el
        }}
        className={cn('relative transition-transform duration-200 ease-out', className)}
        style={{
          perspective: `${perspective}px`,
          transform: `rotateX(${transform.rotateX}deg) rotateY(${transform.rotateY}deg)`,
          transformStyle: 'preserve-3d',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        {...props}
      >
        {children}
        {glareEnabled && (
          <div
            className="absolute inset-0 pointer-events-none rounded-[inherit] overflow-hidden"
            style={{
              background: `radial-gradient(circle at ${glarePosition.x}% ${glarePosition.y}%, rgba(255,255,255,${glareOpacity}) 0%, transparent 60%)`,
            }}
          />
        )}
      </div>
    )
  }
)
TiltCard.displayName = 'TiltCard'

// ============================================================================
// ANIMATED COUNTER
// ============================================================================

interface AnimatedCounterProps extends HTMLAttributes<HTMLSpanElement> {
  value: number
  duration?: number
  formatValue?: (value: number) => string
  delay?: number
}

export type { AnimatedCounterProps }

/**
 * Counter that animates to target value
 */
export const AnimatedCounter = forwardRef<HTMLSpanElement, AnimatedCounterProps>(
  ({ value, duration = 1000, formatValue = (v) => v.toLocaleString(), delay = 0, className, ...props }, ref) => {
    const [displayValue, setDisplayValue] = useState(0)
    const previousValue = useRef(0)

    useEffect(() => {
      const timeout = setTimeout(() => {
        const startValue = previousValue.current
        const startTime = Date.now()

        const animate = () => {
          const elapsed = Date.now() - startTime
          const progress = Math.min(elapsed / duration, 1)

          // Easing function (ease-out-expo)
          const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
          const currentValue = Math.round(startValue + (value - startValue) * easeProgress)

          setDisplayValue(currentValue)

          if (progress < 1) {
            requestAnimationFrame(animate)
          } else {
            previousValue.current = value
          }
        }

        requestAnimationFrame(animate)
      }, delay)

      return () => clearTimeout(timeout)
    }, [value, duration, delay])

    return (
      <span ref={ref} className={cn('tabular-nums', className)} {...props}>
        {formatValue(displayValue)}
      </span>
    )
  }
)
AnimatedCounter.displayName = 'AnimatedCounter'

// ============================================================================
// HOVER REVEAL
// ============================================================================

interface HoverRevealProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  revealContent: ReactNode
  direction?: 'up' | 'down' | 'left' | 'right'
}

export type { HoverRevealProps }

/**
 * Content that reveals additional info on hover
 */
export const HoverReveal = forwardRef<HTMLDivElement, HoverRevealProps>(
  ({ children, revealContent, direction = 'up', className, ...props }, ref) => {
    const translateClasses = {
      up: 'translate-y-full group-hover:translate-y-0',
      down: '-translate-y-full group-hover:translate-y-0',
      left: 'translate-x-full group-hover:translate-x-0',
      right: '-translate-x-full group-hover:translate-x-0',
    }

    return (
      <div ref={ref} className={cn('group relative overflow-hidden', className)} {...props}>
        {children}
        <div
          className={cn(
            'absolute inset-0 bg-dark-500/90 backdrop-blur-sm',
            'flex items-center justify-center',
            'transition-transform duration-300 ease-out',
            translateClasses[direction]
          )}
        >
          {revealContent}
        </div>
      </div>
    )
  }
)
HoverReveal.displayName = 'HoverReveal'

// ============================================================================
// SPOTLIGHT CARD
// ============================================================================

interface SpotlightCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  spotlightColor?: string
  spotlightSize?: number
}

export type { SpotlightCardProps }

/**
 * Card with spotlight effect following cursor
 */
export const SpotlightCard = forwardRef<HTMLDivElement, SpotlightCardProps>(
  ({ children, className, spotlightColor = 'rgba(0, 212, 255, 0.15)', spotlightSize = 400, ...props }, ref) => {
    const cardRef = useRef<HTMLDivElement>(null)
    const [spotlightPosition, setSpotlightPosition] = useState({ x: 0, y: 0 })
    const [isHovered, setIsHovered] = useState(false)

    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return
      const rect = cardRef.current.getBoundingClientRect()
      setSpotlightPosition({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }, [])

    return (
      <div
        ref={(el) => {
          (cardRef as React.MutableRefObject<HTMLDivElement | null>).current = el
          if (typeof ref === 'function') ref(el)
          else if (ref) ref.current = el
        }}
        className={cn('relative overflow-hidden', className)}
        onMouseMove={handleMouseMove}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        {...props}
      >
        {/* Spotlight overlay */}
        <div
          className="absolute inset-0 pointer-events-none transition-opacity duration-300"
          style={{
            opacity: isHovered ? 1 : 0,
            background: `radial-gradient(circle ${spotlightSize}px at ${spotlightPosition.x}px ${spotlightPosition.y}px, ${spotlightColor}, transparent)`,
          }}
        />
        {children}
      </div>
    )
  }
)
SpotlightCard.displayName = 'SpotlightCard'

// ============================================================================
// TYPING TEXT
// ============================================================================

interface TypingTextProps extends HTMLAttributes<HTMLSpanElement> {
  text: string
  speed?: number
  delay?: number
  cursor?: boolean
  onComplete?: () => void
}

export type { TypingTextProps }

/**
 * Text with typewriter animation
 */
export const TypingText = forwardRef<HTMLSpanElement, TypingTextProps>(
  ({ text, speed = 50, delay = 0, cursor = true, onComplete, className, ...props }, ref) => {
    const [displayText, setDisplayText] = useState('')
    const [isComplete, setIsComplete] = useState(false)

    useEffect(() => {
      setDisplayText('')
      setIsComplete(false)

      const timeout = setTimeout(() => {
        let currentIndex = 0
        const interval = setInterval(() => {
          if (currentIndex < text.length) {
            setDisplayText(text.slice(0, currentIndex + 1))
            currentIndex++
          } else {
            clearInterval(interval)
            setIsComplete(true)
            onComplete?.()
          }
        }, speed)

        return () => clearInterval(interval)
      }, delay)

      return () => clearTimeout(timeout)
    }, [text, speed, delay, onComplete])

    return (
      <span ref={ref} className={cn('inline', className)} {...props}>
        {displayText}
        {cursor && (
          <span
            className={cn(
              'inline-block w-0.5 h-[1em] bg-current ml-0.5 align-middle',
              isComplete ? 'animate-blink' : ''
            )}
          />
        )}
      </span>
    )
  }
)
TypingText.displayName = 'TypingText'

// ============================================================================
// STAGGER CHILDREN
// ============================================================================

interface StaggerChildrenProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  staggerDelay?: number
  initialDelay?: number
  direction?: 'up' | 'down' | 'left' | 'right' | 'none'
}

export type { StaggerChildrenProps }

/**
 * Container that staggers animation of children
 */
export const StaggerChildren = forwardRef<HTMLDivElement, StaggerChildrenProps>(
  ({ children, staggerDelay = 100, initialDelay = 0, direction = 'up', className, ...props }, ref) => {
    const translateClass = {
      up: 'translate-y-4',
      down: '-translate-y-4',
      left: 'translate-x-4',
      right: '-translate-x-4',
      none: '',
    }

    return (
      <div ref={ref} className={cn('', className)} {...props}>
        {React.Children.map(children, (child, index) => (
          <div
            className={cn(
              'opacity-0 animate-fade-in-up',
              translateClass[direction]
            )}
            style={{
              animationDelay: `${initialDelay + index * staggerDelay}ms`,
              animationFillMode: 'forwards',
            }}
          >
            {child}
          </div>
        ))}
      </div>
    )
  }
)
StaggerChildren.displayName = 'StaggerChildren'

// ============================================================================
// PARALLAX CONTAINER
// ============================================================================

interface ParallaxContainerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  speed?: number
  direction?: 'vertical' | 'horizontal'
}

export type { ParallaxContainerProps }

/**
 * Container with parallax scroll effect
 */
export const ParallaxContainer = forwardRef<HTMLDivElement, ParallaxContainerProps>(
  ({ children, speed = 0.5, direction = 'vertical', className, ...props }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null)
    const [offset, setOffset] = useState(0)

    useEffect(() => {
      const handleScroll = () => {
        if (!containerRef.current) return
        const rect = containerRef.current.getBoundingClientRect()
        const scrollProgress = (window.innerHeight - rect.top) / (window.innerHeight + rect.height)
        setOffset((scrollProgress - 0.5) * speed * 100)
      }

      window.addEventListener('scroll', handleScroll, { passive: true })
      handleScroll()

      return () => window.removeEventListener('scroll', handleScroll)
    }, [speed])

    const transform = direction === 'vertical'
      ? `translateY(${offset}px)`
      : `translateX(${offset}px)`

    return (
      <div
        ref={(el) => {
          (containerRef as React.MutableRefObject<HTMLDivElement | null>).current = el
          if (typeof ref === 'function') ref(el)
          else if (ref) ref.current = el
        }}
        className={cn('will-change-transform', className)}
        style={{ transform }}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ParallaxContainer.displayName = 'ParallaxContainer'

// ============================================================================
// MORPHING BUTTON
// ============================================================================

interface MorphingButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  loadingContent?: ReactNode
  successContent?: ReactNode
  errorContent?: ReactNode
  state?: 'idle' | 'loading' | 'success' | 'error'
}

export type { MorphingButtonProps }

/**
 * Button that morphs between states
 */
export const MorphingButton = forwardRef<HTMLButtonElement, MorphingButtonProps>(
  (
    {
      children,
      loadingContent = <LoadingSpinner />,
      successContent = <CheckIcon />,
      errorContent = <XIcon />,
      state = 'idle',
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const content = {
      idle: children,
      loading: loadingContent,
      success: successContent,
      error: errorContent,
    }

    const stateClasses = {
      idle: '',
      loading: 'cursor-wait',
      success: 'bg-green-600 hover:bg-green-600',
      error: 'bg-red-600 hover:bg-red-600',
    }

    return (
      <button
        ref={ref}
        className={cn(
          'relative overflow-hidden transition-all duration-300',
          stateClasses[state],
          className
        )}
        disabled={disabled || state === 'loading'}
        {...props}
      >
        <span
          className={cn(
            'flex items-center justify-center transition-all duration-300',
            state !== 'idle' && 'opacity-0 scale-50'
          )}
        >
          {children}
        </span>
        <span
          className={cn(
            'absolute inset-0 flex items-center justify-center transition-all duration-300',
            state === 'idle' ? 'opacity-0 scale-50' : 'opacity-100 scale-100'
          )}
        >
          {content[state]}
        </span>
      </button>
    )
  }
)
MorphingButton.displayName = 'MorphingButton'

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

function LoadingSpinner() {
  return (
    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

// ============================================================================
// CSS KEYFRAMES (add to tailwind.config.js or global CSS)
// ============================================================================

/*
Add these keyframes to your tailwind.config.js:

keyframes: {
  ripple: {
    '0%': { transform: 'scale(0)', opacity: '0.5' },
    '100%': { transform: 'scale(1)', opacity: '0' },
  },
  blink: {
    '0%, 50%': { opacity: '1' },
    '51%, 100%': { opacity: '0' },
  },
  'fade-in-up': {
    '0%': { opacity: '0', transform: 'translateY(10px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
},
animation: {
  ripple: 'ripple 0.6s linear forwards',
  blink: 'blink 1s step-end infinite',
  'fade-in-up': 'fade-in-up 0.5s ease-out forwards',
},
*/
