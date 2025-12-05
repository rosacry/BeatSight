# BeatSight Frontend

React-based web frontend for BeatSight beatmap generation service.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **React Query** - Server state management
- **React Router** - Client-side routing
- **Zustand** - Client state management
- **Playwright** - E2E testing
- **Vitest** - Unit testing

## Getting Started

### Prerequisites

- Node.js 18+
- npm or pnpm
- Backend running at `localhost:8000` (see `../backend/README.md`)

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at `http://localhost:3000`.

### Environment Variables

See `.env.example` for all available options:

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API URL | `/api` |
| `VITE_WS_HOST` | WebSocket host | `localhost:8000` |
| `VITE_ENABLE_PWA` | Enable PWA features | `true` |
| `VITE_DEBUG` | Enable debug mode | `false` |

### Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Testing

```bash
# Unit tests
npm test

# Unit tests with coverage
npm run test:coverage

# E2E tests (headless)
npm run test:e2e

# E2E tests with UI
npm run test:e2e:ui

# E2E tests (headed browser)
npm run test:e2e:headed
```

## Project Structure

```
src/
├── api/           # API client and types
│   └── client.ts  # Backend API functions
├── components/    # Reusable UI components
│   ├── Layout.tsx
│   ├── JobStatusBadge.tsx
│   ├── ProgressBar.tsx
│   ├── JobCard.tsx
│   ├── JobProgressTracker.tsx
│   └── QuotaDisplay.tsx
├── pages/         # Page components
│   ├── HomePage.tsx
│   ├── JobQueuePage.tsx
│   ├── JobDetailPage.tsx
│   └── UploadPage.tsx
├── types/         # TypeScript type definitions
│   └── api.ts     # API response types
├── App.tsx        # Root component with routing
├── main.tsx       # Application entry point
└── index.css      # Tailwind CSS imports
```

## Features

### Job Queue Management
- View all generation jobs with status filtering
- Real-time progress updates via Server-Sent Events (SSE)
- Cancel queued/processing jobs
- Retry failed jobs

### File Upload
- Drag-and-drop audio file upload
- Supports MP3, WAV, OGG, FLAC
- Upload progress indicator
- Automatic job creation after upload

### Quota Tracking
- Visual quota usage display
- Daily and monthly quota limits
- Warnings when approaching limits

## API Integration

The frontend connects to the BeatSight backend API at `/api/v1`. Configure the API base URL in `src/api/client.ts`.

### Key Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /ai-jobs` | List all jobs |
| `GET /ai-jobs/:id` | Get job details |
| `POST /ai-jobs` | Create new job |
| `POST /ai-jobs/:id/cancel` | Cancel job |
| `POST /ai-jobs/:id/retry` | Retry failed job |
| `GET /ai-jobs/:id/progress/stream` | SSE progress stream |
| `GET /ai-jobs/quota` | Get quota status |
| `POST /storage/upload/:category` | Upload file |

## Development

### Code Style

- Components use functional style with hooks
- Named exports for all components
- Colocation of related files

### Adding New Pages

1. Create page component in `src/pages/`
2. Export from `src/pages/index.ts`
3. Add route in `src/App.tsx`

### Adding New Components

1. Create component in `src/components/`
2. Export from `src/components/index.ts`

## PWA Testing Guide

BeatSight is a Progressive Web App (PWA) that can be installed on mobile devices. Follow this guide to test PWA functionality.

### Prerequisites

- Build the production version: `npm run build`
- Serve with HTTPS (required for PWA): `npm run preview` or use a tool like `ngrok`
- Device and browser ready for testing

### Testing on Android (Chrome)

1. **Open the site in Chrome** on your Android device
2. **Look for the install prompt** - Chrome shows a banner at the bottom
3. **Or use the menu** - Tap ⋮ → "Add to Home Screen" or "Install App"
4. **Verify installation:**
   - App icon appears on home screen
   - Opens in standalone mode (no browser chrome)
   - Works offline (cached pages load without network)

### Testing on iOS (Safari)

> **⚠️ Note:** iOS PWA debugging requires a Mac with Safari. If you only have an iOS device (no Mac), you can still test the install flow and basic functionality, but cannot access Safari Web Inspector for debugging.

1. **Open the site in Safari** on your iPhone/iPad
2. **Tap the Share button** (square with arrow)
3. **Scroll down and tap "Add to Home Screen"**
4. **Name the app** and tap "Add"
5. **Verify installation:**
   - App icon appears on home screen
   - Opens in standalone mode
   - Splash screen shows on launch

### iOS Testing Without a Mac

If you don't have access to macOS for Safari Web Inspector:

1. **Use Eruda for on-device debugging** - Add `eruda` script to test builds for a mobile console
2. **Check manifest directly** - Visit `/manifest.json` in Safari to verify it loads
3. **Test offline manually** - Enable Airplane Mode after first visit
4. **Console logs via alert** - For critical debugging, use `alert()` temporarily
5. **Use BrowserStack/Sauce Labs** - Cloud-based iOS testing with debugging tools

### PWA Feature Checklist

| Feature | How to Test | Expected Behavior |
|---------|-------------|-------------------|
| **Install Prompt** | Visit site, wait 30s | Banner appears on Android |
| **Offline Mode** | Enable airplane mode after loading | Cached pages load, offline indicator shows |
| **App Icon** | Check home screen after install | BeatSight icon with correct artwork |
| **Splash Screen** | Launch from home screen | Branded splash while loading |
| **Standalone Mode** | Launch from home screen | No browser URL bar or navigation |
| **Push Notifications** | Enable in settings (if supported) | Test notification appears |
| **Update Prompt** | Deploy new version, revisit | "New version available" toast |

### Debugging PWA Issues

**Chrome DevTools (Desktop):**
```bash
# Open DevTools → Application tab
# - Manifest: Check manifest.json parsing
# - Service Workers: Verify registration
# - Cache Storage: Inspect cached assets
```

**Android Remote Debugging:**
1. Enable USB debugging on Android device
2. Connect device via USB
3. Open `chrome://inspect` on desktop Chrome
4. Click "inspect" under your device

**iOS Remote Debugging:**
1. Enable Web Inspector in iOS Settings → Safari → Advanced
2. Connect device via USB
3. Open Safari on Mac → Develop menu → [Device name]

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No install prompt | Not HTTPS or already installed | Use HTTPS, uninstall first |
| Offline not working | Service worker not registered | Check SW registration in DevTools |
| Old version cached | SW cache not updated | Clear site data, hard refresh |
| Icon not showing | Manifest icons misconfigured | Verify manifest.json paths |

