/**
 * ParticleBackground - Animated floating particles background
 * 
 * Creates an immersive, osu!-inspired particle field with floating circles
 * that respond to mouse movement and create depth.
 */

import { useEffect, useRef, useCallback, useMemo } from 'react'
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

export function ParticleBackground({
    className,
    particleCount = 50,
    colors = ['#00d4ff', '#ff00ff', '#ffaa00'],
    speed = 0.5,
    interactive = true,
    blur = true,
}: ParticleBackgroundProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const particlesRef = useRef<Particle[]>([])
    const mouseRef = useRef({ x: 0, y: 0 })
    const animationRef = useRef<number>()

    const initParticles = useCallback((width: number, height: number) => {
        particlesRef.current = Array.from({ length: particleCount }, () => ({
            x: Math.random() * width,
            y: Math.random() * height,
            size: Math.random() * 4 + 1,
            speedX: (Math.random() - 0.5) * speed,
            speedY: (Math.random() - 0.5) * speed,
            opacity: Math.random() * 0.5 + 0.1,
            hue: Math.random() * 360,
        }))
    }, [particleCount, speed])

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

            // Interactive mouse influence
            if (interactive) {
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

            // Draw glow
            if (particle.size > 2) {
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

            // Connect nearby particles
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
        })

        ctx.globalAlpha = 1
        animationRef.current = requestAnimationFrame(animate)
    }, [colors, interactive])

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const handleResize = () => {
            canvas.width = canvas.offsetWidth * window.devicePixelRatio
            canvas.height = canvas.offsetHeight * window.devicePixelRatio
            const ctx = canvas.getContext('2d')
            if (ctx) {
                ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
            }
            initParticles(canvas.offsetWidth, canvas.offsetHeight)
        }

        const handleMouseMove = (e: MouseEvent) => {
            const rect = canvas.getBoundingClientRect()
            mouseRef.current = {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            }
        }

        handleResize()
        window.addEventListener('resize', handleResize)
        if (interactive) {
            window.addEventListener('mousemove', handleMouseMove)
        }

        animate()

        return () => {
            window.removeEventListener('resize', handleResize)
            window.removeEventListener('mousemove', handleMouseMove)
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
        }
    }, [animate, initParticles, interactive])

    return (
        <canvas
            ref={canvasRef}
            className={cn(
                'absolute inset-0 w-full h-full pointer-events-none',
                blur && 'filter blur-[0.5px]',
                className
            )}
            style={{ width: '100%', height: '100%' }}
        />
    )
}

// ============================================================================
// Gradient Orbs - Floating gradient blobs
// ============================================================================

interface GradientOrbsProps {
    className?: string
}

export function GradientOrbs({ className }: GradientOrbsProps) {
    return (
        <div className={cn('absolute inset-0 overflow-hidden pointer-events-none', className)}>
            {/* Primary cyan orb */}
            <div
                className="absolute w-[600px] h-[600px] rounded-full opacity-30 blur-[100px]
                           bg-gradient-to-br from-cyan-500 to-cyan-700
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

// ============================================================================
// Audio Visualizer Bars - Animated music bars
// ============================================================================

interface AudioBarsProps {
    className?: string
    barCount?: number
    color?: string
}

export function AudioBars({ className, barCount = 5, color = '#00d4ff' }: AudioBarsProps) {
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

export default ParticleBackground
