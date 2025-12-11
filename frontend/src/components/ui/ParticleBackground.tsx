/**
 * ParticleBackground - Animated floating particles background
 * 
 * Creates an immersive particle field with floating circles inspired by rhythm games
 * that respond to mouse movement and create depth.
 * 
 * Performance optimized for mobile devices by:
 * - Reducing particle count on mobile
 * - Disabling expensive effects (glow, connections) on mobile
 * - Respecting prefers-reduced-motion
 * - Using lower animation frame rates on low-power devices
 */

import { useEffect, useRef, useCallback, useMemo, memo, useState } from 'react'
import { cn } from '../../lib/utils'

interface Particle {
    x: number
    y: number
    size: number
    speedX: number
    speedY: number
    opacity: number
    hue: number
}

interface ParticleBackgroundProps {
    className?: string
    particleCount?: number
    colors?: string[]
    speed?: number
    interactive?: boolean
    blur?: boolean
}

// Detect if device is mobile or low-power
function useIsMobile(): boolean {
    const [isMobile, setIsMobile] = useState(false)

    useEffect(() => {
        const checkMobile = () => {
            // Check viewport width
            const isSmallScreen = window.innerWidth < 768
            // Check for touch device
            const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0
            // Check for mobile user agent (fallback)
            const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)

            setIsMobile(isSmallScreen || (isTouch && isMobileUA))
        }

        checkMobile()
        window.addEventListener('resize', checkMobile)
        return () => window.removeEventListener('resize', checkMobile)
    }, [])

    return isMobile
}

// Detect reduced motion preference
function usePrefersReducedMotion(): boolean {
    const [prefersReduced, setPrefersReduced] = useState(false)

    useEffect(() => {
        // Safety check for test environment (jsdom doesn't have matchMedia)
        if (typeof window === 'undefined' || !window.matchMedia) {
            return
        }

        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
        setPrefersReduced(mediaQuery.matches)

        const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches)
        mediaQuery.addEventListener('change', handler)
        return () => mediaQuery.removeEventListener('change', handler)
    }, [])

    return prefersReduced
}

function ParticleBackgroundBase({
    className,
    particleCount = 50,
    colors = ['#ff66ab', '#aa92ff', '#ffaa00'],
    speed = 0.5,
    interactive = true,
    blur = true,
}: ParticleBackgroundProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const particlesRef = useRef<Particle[]>([])
    const mouseRef = useRef({ x: 0, y: 0 })
    const animationRef = useRef<number>()

    const isMobile = useIsMobile()
    const prefersReducedMotion = usePrefersReducedMotion()

    // Adjust settings for mobile/reduced motion
    const effectiveParticleCount = prefersReducedMotion ? 0 : (isMobile ? Math.min(15, particleCount) : particleCount)
    const enableGlow = !isMobile && !prefersReducedMotion
    const enableConnections = !isMobile && !prefersReducedMotion
    const enableInteractive = interactive && !isMobile // Disable mouse interaction on mobile

    const initParticles = useCallback((width: number, height: number) => {
        particlesRef.current = Array.from({ length: effectiveParticleCount }, () => ({
            x: Math.random() * width,
            y: Math.random() * height,
            size: Math.random() * (isMobile ? 3 : 4) + 1,
            speedX: (Math.random() - 0.5) * speed,
            speedY: (Math.random() - 0.5) * speed,
            opacity: Math.random() * 0.5 + 0.1,
            hue: Math.random() * 360,
        }))
    }, [effectiveParticleCount, speed, isMobile])

    const animate = useCallback(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        ctx.clearRect(0, 0, canvas.width, canvas.height)

        particlesRef.current.forEach((particle, index) => {
            // Update position
            particle.x += particle.speedX
            particle.y += particle.speedY

            // Interactive mouse influence (desktop only)
            if (enableInteractive) {
                const dx = mouseRef.current.x - particle.x
                const dy = mouseRef.current.y - particle.y
                const distance = Math.sqrt(dx * dx + dy * dy)
                if (distance < 150) {
                    const force = (150 - distance) / 150
                    particle.x -= dx * force * 0.02
                    particle.y -= dy * force * 0.02
                }
            }

            // Wrap around edges
            if (particle.x < 0) particle.x = canvas.width
            if (particle.x > canvas.width) particle.x = 0
            if (particle.y < 0) particle.y = canvas.height
            if (particle.y > canvas.height) particle.y = 0

            // Draw particle
            const colorIndex = index % colors.length
            ctx.beginPath()
            ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2)
            ctx.fillStyle = colors[colorIndex]
            ctx.globalAlpha = particle.opacity
            ctx.fill()

            // Draw glow (desktop only - expensive operation)
            if (enableGlow && particle.size > 2) {
                const gradient = ctx.createRadialGradient(
                    particle.x, particle.y, 0,
                    particle.x, particle.y, particle.size * 3
                )
                gradient.addColorStop(0, colors[colorIndex])
                gradient.addColorStop(1, 'transparent')
                ctx.beginPath()
                ctx.arc(particle.x, particle.y, particle.size * 3, 0, Math.PI * 2)
                ctx.fillStyle = gradient
                ctx.globalAlpha = particle.opacity * 0.3
                ctx.fill()
            }

            // Connect nearby particles (desktop only - O(n²) operation)
            if (enableConnections) {
                particlesRef.current.slice(index + 1).forEach((other) => {
                    const dx = particle.x - other.x
                    const dy = particle.y - other.y
                    const distance = Math.sqrt(dx * dx + dy * dy)

                    if (distance < 100) {
                        ctx.beginPath()
                        ctx.moveTo(particle.x, particle.y)
                        ctx.lineTo(other.x, other.y)
                        ctx.strokeStyle = colors[colorIndex]
                        ctx.globalAlpha = (1 - distance / 100) * 0.15
                        ctx.lineWidth = 0.5
                        ctx.stroke()
                    }
                })
            }
        })

        ctx.globalAlpha = 1
        animationRef.current = requestAnimationFrame(animate)
    }, [colors, enableInteractive, enableGlow, enableConnections])

    useEffect(() => {
        // Skip entirely if reduced motion is preferred and no particles
        if (effectiveParticleCount === 0) return

        const canvas = canvasRef.current
        if (!canvas) return

        const handleResize = () => {
            // Use lower pixel ratio on mobile for better performance
            const pixelRatio = isMobile ? 1 : Math.min(window.devicePixelRatio, 2)
            canvas.width = canvas.offsetWidth * pixelRatio
            canvas.height = canvas.offsetHeight * pixelRatio
            const ctx = canvas.getContext('2d')
            if (ctx) {
                ctx.scale(pixelRatio, pixelRatio)
            }
            initParticles(canvas.offsetWidth, canvas.offsetHeight)
        }

        const handleMouseMove = (e: MouseEvent) => {
            if (!enableInteractive) return
            const rect = canvas.getBoundingClientRect()
            mouseRef.current = {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            }
        }

        handleResize()
        window.addEventListener('resize', handleResize)
        if (enableInteractive) {
            window.addEventListener('mousemove', handleMouseMove)
        }

        animationRef.current = requestAnimationFrame(animate)

        return () => {
            window.removeEventListener('resize', handleResize)
            window.removeEventListener('mousemove', handleMouseMove)
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
        }
    }, [animate, initParticles, enableInteractive, effectiveParticleCount, isMobile])

    // Don't render canvas if reduced motion and no particles
    if (prefersReducedMotion) {
        return null
    }

    return (
        <canvas
            ref={canvasRef}
            className={cn(
                'absolute inset-0 w-full h-full pointer-events-none',
                blur && !isMobile && 'filter blur-[0.5px]', // Disable blur on mobile
                className
            )}
            style={{ width: '100%', height: '100%' }}
        />
    )
}

// Memoize to prevent re-renders when parent state changes (e.g., typing in inputs)
export const ParticleBackground = memo(ParticleBackgroundBase)

// ============================================================================
// Gradient Orbs - Floating gradient blobs
// Mobile optimized: smaller sizes, reduced blur, optional disable
// ============================================================================

interface GradientOrbsProps {
    className?: string
}

function GradientOrbsBase({ className }: GradientOrbsProps) {
    const [isMobile, setIsMobile] = useState(false)
    const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

    useEffect(() => {
        // Check for mobile
        const checkMobile = () => {
            setIsMobile(window.innerWidth < 768 ||
                ('ontouchstart' in window && /Android|webOS|iPhone|iPad|iPod/i.test(navigator.userAgent)))
        }
        checkMobile()
        window.addEventListener('resize', checkMobile)

        // Check for reduced motion (with safety check for test environment)
        let motionQuery: MediaQueryList | null = null
        let motionHandler: ((e: MediaQueryListEvent) => void) | null = null

        if (typeof window !== 'undefined' && window.matchMedia) {
            motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
            setPrefersReducedMotion(motionQuery.matches)
            motionHandler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches)
            motionQuery.addEventListener('change', motionHandler)
        }

        return () => {
            window.removeEventListener('resize', checkMobile)
            if (motionQuery && motionHandler) {
                motionQuery.removeEventListener('change', motionHandler)
            }
        }
    }, [])

    // Don't render on reduced motion preference
    if (prefersReducedMotion) {
        return null
    }

    // Simplified version for mobile - single static gradient, no animation
    if (isMobile) {
        return (
            <div className={cn('absolute inset-0 overflow-hidden pointer-events-none', className)}>
                {/* Single simplified gradient for mobile - no animation, smaller blur */}
                <div
                    className="absolute w-[300px] h-[300px] rounded-full opacity-20 blur-[40px]
                               bg-gradient-to-br from-primary-500 to-fuchsia-500"
                    style={{ top: '10%', left: '10%' }}
                />
            </div>
        )
    }

    return (
        <div className={cn('absolute inset-0 overflow-hidden pointer-events-none', className)}>
            {/* Primary orb */}
            <div
                className="absolute w-[600px] h-[600px] rounded-full opacity-30 blur-[100px]
                           bg-gradient-to-br from-primary-500 to-primary-700
                           animate-float-slow"
                style={{ top: '-10%', left: '-5%' }}
            />
            {/* Secondary magenta orb */}
            <div
                className="absolute w-[500px] h-[500px] rounded-full opacity-20 blur-[100px]
                           bg-gradient-to-br from-fuchsia-500 to-purple-700
                           animate-float-slower"
                style={{ bottom: '10%', right: '-10%' }}
            />
            {/* Accent orange orb */}
            <div
                className="absolute w-[400px] h-[400px] rounded-full opacity-15 blur-[80px]
                           bg-gradient-to-br from-orange-500 to-amber-600
                           animate-float"
                style={{ top: '40%', left: '60%' }}
            />
        </div>
    )
}

// Memoize to prevent re-renders
export const GradientOrbs = memo(GradientOrbsBase)

// ============================================================================
// Audio Visualizer Bars - Animated music bars
// ============================================================================

interface AudioBarsProps {
    className?: string
    barCount?: number
    color?: string
}

function AudioBarsBase({ className, barCount = 5, color = '#ff66ab' }: AudioBarsProps) {
    const bars = useMemo(() =>
        Array.from({ length: barCount }, (_, i) => ({
            delay: i * 0.1,
            height: 40 + Math.random() * 40,
        })),
        [barCount]
    )

    return (
        <div className={cn('flex items-end gap-1 h-16', className)}>
            {bars.map((bar, i) => (
                <div
                    key={i}
                    className="w-1.5 rounded-full animate-audio-bar"
                    style={{
                        backgroundColor: color,
                        animationDelay: `${bar.delay}s`,
                        height: `${bar.height}%`,
                    }}
                />
            ))}
        </div>
    )
}

// Memoize to prevent re-renders
export const AudioBars = memo(AudioBarsBase)

export default ParticleBackground
