/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // osu!-inspired color palette - warm pinks with deep darks
                primary: {
                    50: '#fff0f7',
                    100: '#ffe4f0',
                    200: '#ffcce3',
                    300: '#ffa3cc',
                    400: '#ff66ab',  // osu! pink
                    500: '#ff4d9d',
                    600: '#e91e8c',
                    700: '#c91574',
                    800: '#a6145f',
                    900: '#8a1651',
                    950: '#54062d',
                },
                accent: {
                    50: '#f5f3ff',
                    100: '#ede9fe',
                    200: '#ddd6fe',
                    300: '#c4b5fd',
                    400: '#aa92ff',  // osu! purple
                    500: '#8b5cf6',
                    600: '#7c3aed',
                    700: '#6d28d9',
                    800: '#5b21b6',
                    900: '#4c1d95',
                    950: '#2e1065',
                },
                // BeatSight brand colors - refined
                beat: {
                    pink: '#ff66ab',
                    purple: '#aa92ff',
                    blue: '#66ccff',
                    cyan: '#8fe5fe',
                    yellow: '#ffd64c',
                },
                // Dark backgrounds inspired by osu!
                dark: {
                    50: '#3a3a3a',
                    100: '#333333',
                    200: '#2d2d2d',
                    300: '#262626',
                    400: '#222222',
                    500: '#1a1a1a',
                    600: '#161616',
                    700: '#121212',
                    800: '#0d0d0d',
                    900: '#080808',
                },
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'progress': 'progress 1s ease-in-out infinite',
                // New animations for UI components
                'fade-in': 'fadeIn 0.2s ease-out',
                'fade-out': 'fadeOut 0.2s ease-in',
                'slide-in-up': 'slideInUp 0.3s ease-out',
                'slide-in-down': 'slideInDown 0.3s ease-out',
                'slide-in-left': 'slideInLeft 0.3s ease-out',
                'slide-in-right': 'slideInRight 0.3s ease-out',
                'scale-in': 'scaleIn 0.2s ease-out',
                'scale-out': 'scaleOut 0.2s ease-in',
                'spin-slow': 'spin 3s linear infinite',
                'bounce-subtle': 'bounceSubtle 2s ease-in-out infinite',
                'glow-pulse': 'glowPulse 2s ease-in-out infinite',
                'shimmer': 'shimmer 2s linear infinite',
                'float': 'float 3s ease-in-out infinite',
                'indeterminate': 'indeterminate 1.5s ease-in-out infinite',
                // Micro-interaction animations
                'ripple': 'ripple 0.6s linear forwards',
                'blink': 'blink 1s step-end infinite',
                'fade-in-up': 'fade-in-up 0.5s ease-out forwards',
                'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
                'border-spin': 'border-spin 3s linear infinite',
                // Particle background animations
                'float-slow': 'floatSlow 20s ease-in-out infinite',
                'float-slower': 'floatSlower 25s ease-in-out infinite',
                'audio-bar': 'audioBar 1s ease-in-out infinite',
                'fadeInUp': 'fadeInUp 0.6s ease-out forwards',
            },
            keyframes: {
                progress: {
                    '0%': { transform: 'translateX(-100%)' },
                    '100%': { transform: 'translateX(100%)' },
                },
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                fadeOut: {
                    '0%': { opacity: '1' },
                    '100%': { opacity: '0' },
                },
                slideInUp: {
                    '0%': { transform: 'translateY(10px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                slideInDown: {
                    '0%': { transform: 'translateY(-10px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
                slideInLeft: {
                    '0%': { transform: 'translateX(-10px)', opacity: '0' },
                    '100%': { transform: 'translateX(0)', opacity: '1' },
                },
                slideInRight: {
                    '0%': { transform: 'translateX(10px)', opacity: '0' },
                    '100%': { transform: 'translateX(0)', opacity: '1' },
                },
                scaleIn: {
                    '0%': { transform: 'scale(0.95)', opacity: '0' },
                    '100%': { transform: 'scale(1)', opacity: '1' },
                },
                scaleOut: {
                    '0%': { transform: 'scale(1)', opacity: '1' },
                    '100%': { transform: 'scale(0.95)', opacity: '0' },
                },
                bounceSubtle: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-5px)' },
                },
                glowPulse: {
                    '0%, 100%': { boxShadow: '0 0 5px rgba(0, 212, 255, 0.5), 0 0 20px rgba(0, 212, 255, 0.2)' },
                    '50%': { boxShadow: '0 0 20px rgba(0, 212, 255, 0.8), 0 0 40px rgba(0, 212, 255, 0.4)' },
                },
                shimmer: {
                    '0%': { backgroundPosition: '-200% 0' },
                    '100%': { backgroundPosition: '200% 0' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-10px)' },
                },
                indeterminate: {
                    '0%': { transform: 'translateX(-100%)' },
                    '50%': { transform: 'translateX(100%)' },
                    '100%': { transform: 'translateX(100%)' },
                },
                // Micro-interaction keyframes
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
                'pulse-glow': {
                    '0%, 100%': { boxShadow: '0 0 10px var(--glow-color, rgba(0,212,255,0.3))' },
                    '50%': { boxShadow: '0 0 30px var(--glow-color, rgba(0,212,255,0.6))' },
                },
                'border-spin': {
                    '0%': { '--border-angle': '0deg' },
                    '100%': { '--border-angle': '360deg' },
                },
                // Particle background keyframes
                floatSlow: {
                    '0%, 100%': { transform: 'translate(0, 0) rotate(0deg)' },
                    '25%': { transform: 'translate(20px, -20px) rotate(2deg)' },
                    '50%': { transform: 'translate(-10px, 10px) rotate(-1deg)' },
                    '75%': { transform: 'translate(15px, 5px) rotate(1deg)' },
                },
                floatSlower: {
                    '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
                    '33%': { transform: 'translate(-30px, 20px) scale(1.05)' },
                    '66%': { transform: 'translate(20px, -15px) scale(0.95)' },
                },
                audioBar: {
                    '0%, 100%': { height: '20%' },
                    '50%': { height: '100%' },
                },
                fadeInUp: {
                    '0%': { opacity: '0', transform: 'translateY(20px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
            },
            // Additional design tokens
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
                // osu!-inspired gradients
                'beat-gradient': 'linear-gradient(135deg, #ff66ab 0%, #aa92ff 100%)',
                'beat-gradient-subtle': 'linear-gradient(135deg, rgba(255,102,171,0.1) 0%, rgba(170,146,255,0.1) 100%)',
                'beat-gradient-dark': 'linear-gradient(180deg, #1a1a1a 0%, #121212 100%)',
            },
            boxShadow: {
                // osu!-inspired glow effects - subtle and clean
                'glow-pink': '0 0 20px rgba(255, 102, 171, 0.4)',
                'glow-purple': '0 0 20px rgba(170, 146, 255, 0.4)',
                'glow-blue': '0 0 20px rgba(102, 204, 255, 0.4)',
                'glow-sm': '0 0 10px rgba(255, 102, 171, 0.2)',
                'inner-glow': 'inset 0 0 20px rgba(255, 102, 171, 0.1)',
            },
            transitionTimingFunction: {
                'bounce-in': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
                'smooth': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
            },
            // osu!-inspired border radius
            borderRadius: {
                'beat': '10px',
            },
        },
    },
    plugins: [],
}
