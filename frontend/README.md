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
