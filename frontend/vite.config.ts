import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import path from 'path'

export default defineConfig(({ mode }) => ({
    plugins: [
        react(),
        // Sentry source maps plugin (production builds with auth token available)
        mode === 'production' && process.env.SENTRY_AUTH_TOKEN && sentryVitePlugin({
            org: process.env.SENTRY_ORG,
            project: 'beatsight-frontend',
            authToken: process.env.SENTRY_AUTH_TOKEN,
            sourcemaps: {
                filesToDeleteAfterUpload: ['**/*.map'],
            },
            release: {
                name: process.env.VITE_RELEASE_VERSION || process.env.GITHUB_SHA,
            },
        }),
    ].filter(Boolean),
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    build: {
        sourcemap: true, // Generate source maps for Sentry
        rollupOptions: {
            output: {
                manualChunks: {
                    // Split vendor chunks for better caching
                    'vendor-react': ['react', 'react-dom', 'react-router-dom'],
                    'vendor-query': ['@tanstack/react-query'],
                    'vendor-sentry': ['@sentry/react'],
                    'vendor-utils': ['date-fns', 'clsx', 'tailwind-merge', 'zustand'],
                },
            },
        },
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
            },
        },
    },
}))
