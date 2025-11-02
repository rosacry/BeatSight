# BeatSight Architecture

## Overview

BeatSight is designed as a modular, scalable system with clear separation between the gameplay client, AI processing pipeline, and community backend services.

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Devices                             │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Desktop Client  │   iOS Client     │   Android Client         │
│  (osu-framework) │   (Flutter)      │   (Flutter)              │
└────────┬─────────┴────────┬─────────┴──────────┬───────────────┘
         │                  │                    │
         └──────────────────┼────────────────────┘
                            │
                   ┌────────▼────────┐
                   │   Backend API   │
                   │   (FastAPI)     │
                   └────────┬────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────▼────┐      ┌─────▼──────┐    ┌─────▼─────┐
    │PostgreSQL│      │ S3/CDN     │    │AI Pipeline│
    │Database  │      │Audio Store │    │  (Python) │
    └──────────┘      └────────────┘    └───────────┘
```

## 1. Desktop Client (Primary Platform)

### Technology Stack
- **Framework**: osu-framework (C# / .NET 8.0)
- **Graphics**: OpenGL via framework abstraction
- **Audio**: BASS audio library (via framework)
- **Build**: .NET SDK, cross-platform compilation

### Core Modules

#### Game Engine (`BeatSight.Game`)
- **Screens**:
  - `MainMenuScreen`: Navigation hub
  - `SongSelectScreen`: Browse local/downloaded beatmaps
  - `GameplayScreen`: Main rhythm game interface
  - `EditorScreen`: Beatmap creation/editing
  - `ResultsScreen`: Score display and replay
  - `SettingsScreen`: Configuration

- **Gameplay Components**:
  - `PlayfieldRenderer`: Visualizes falling notes
  - `DrumKitDisplay`: Shows drum kit layout
  - `JudgementProcessor`: Calculates accuracy (300/100/50/miss)
  - `ComboCounter`: Tracks consecutive hits
  - `ScoreCalculator`: osu!-inspired pp-like system
  - `HitObjectManager`: Manages note timing and rendering

- **Audio System**:
  - `AudioEngine`: Playback with pitch-independent speed control
  - `MetronomeOverlay`: Configurable click track
  - `TrackIsolation`: Toggle between full mix and stems
  - `MicrophoneInput`: Real-time audio capture for scoring

- **Editor Components**:
  - `TimelineView`: Waveform display with zoom
  - `NoteEditor`: Place/move/delete notes
  - `DrumPartMapper`: Assign notes to drum components
  - `SnapDivisor`: Timing quantization
  - `HitsoundPlayer`: Audio feedback while editing

#### Desktop Runner (`BeatSight.Desktop`)
- Platform-specific initialization
- Window management
- File system integration
- OS-specific features (notifications, file associations)

### File Handling
- Local beatmap library management
- Import/export `.bsm` files
- Audio file format support (via BASS)
- Auto-download from community server

### Performance Targets
- **Latency**: <10ms audio-visual sync
- **Frame Rate**: 60 FPS minimum, 240 FPS capable
- **Input Lag**: <5ms (critical for rhythm games)

## 2. Mobile Clients (iOS/Android)

### Technology Stack
- **Framework**: Flutter 3.16+
- **Audio**: flutter_sound + audioplayers
- **State Management**: Riverpod or Bloc
- **Networking**: Dio (HTTP client)
- **Storage**: sqlite + hive (local cache)

### Design Philosophy
- Touch-optimized gameplay (tap circles on drum zones)
- Simplified editor (view-only or basic adjustments)
- Beatmap browser and downloader
- Offline playback support
- Cloud sync for scores/progress

### Platform-Specific
- **iOS**: 
  - AVFoundation for low-latency audio
  - App Store distribution
  - IAP for donations (optional)
  
- **Android**:
  - OpenSL ES for audio
  - Google Play distribution
  - Google Play Billing for donations

## 3. AI Processing Pipeline

### Technology Stack
- **Language**: Python 3.10+
- **ML Framework**: PyTorch 2.0+
- **Audio Processing**: librosa, soundfile, pydub
- **Source Separation**: Demucs (Meta)
- **Deployment**: Docker containers
- **API**: FastAPI (async Python)

### Processing Stages

#### Stage 1: Audio Preprocessing
```python
Input: Audio file (any format)
│
├── Format conversion (ffmpeg)
├── Sample rate normalization (44.1kHz)
├── Stereo to mono conversion (optional)
└── Output: WAV/FLAC standardized
```

#### Stage 2: Source Separation (Demucs)
```python
Input: Full mix audio
│
├── Demucs HTDemucs model (v4)
├── Separate: drums, bass, vocals, other
├── Quality: ~9 SDR (Signal-to-Distortion Ratio)
└── Output: Isolated drum stem
```

#### Stage 3: Onset Detection
```python
Input: Drum stem
│
├── Spectral flux analysis
├── Envelope following
├── Peak picking with adaptive threshold
├── Confidence scoring
└── Output: Timestamp list with confidence
```

#### Stage 4: Drum Classification
```python
Input: Onset timestamps + audio
│
├── Extract audio windows around onsets
├── Compute mel-spectrograms
├── CNN classifier (per onset)
│   ├── Kick (bass drum)
│   ├── Snare
│   ├── Hi-hat (closed/open)
│   ├── Crash cymbal
│   ├── Ride cymbal
│   ├── China cymbal
│   ├── Toms (high/mid/low)
│   └── Other percussion
├── Confidence threshold filtering
└── Output: Labeled hits
```

#### Stage 5: Beatmap Generation
```python
Input: Labeled hits + metadata
│
├── BPM detection (librosa)
├── Time signature inference
├── Quantization to beat grid
├── Difficulty calculation
├── Pattern analysis (rolls, fills)
├── Visual lane assignment
└── Output: .bsm beatmap file
```

### Machine Learning Models

#### Model 1: Drum Transcription Transformer
- **Architecture**: Transformer encoder with temporal convolutions
- **Input**: Mel-spectrogram sequences (128 bins × time)
- **Output**: Multi-label per-frame drum activations
- **Training Data**: 
  - MusicNet drum annotations
  - Custom labeled dataset (community contribution)
  - Synthetic data from MIDI + drum samples
- **Size**: ~50M parameters
- **Inference**: Real-time capable on CPU

#### Model 2: Drum Part Classifier
- **Architecture**: ResNet-18 variant for audio
- **Input**: Log-mel spectrogram (128×128)
- **Output**: 12-class drum part probability
- **Training**: Transfer learning from AudioSet
- **Size**: ~11M parameters
- **Accuracy Target**: >90% on held-out test set

### Training Infrastructure
- **Distributed Training**: PyTorch DDP + Horovod
- **Data Pipeline**: WebDataset for streaming
- **Tracking**: Weights & Biases (wandb)
- **Compute**: 
  - Central: AWS/GCP GPU instances (training)
  - Community: Volunteer compute (optional)

## 4. Backend Services

### Technology Stack
- **API Framework**: FastAPI (Python) or ASP.NET Core (C#)
- **Database**: PostgreSQL 15+
- **Cache**: Redis
- **Storage**: S3-compatible (AWS S3 / MinIO / Backblaze B2)
- **CDN**: CloudFlare
- **Auth**: JWT tokens + OAuth2
- **Deployment**: Docker + Kubernetes

### API Endpoints

#### Beatmap Management
```
GET    /api/v1/beatmaps              # List/search beatmaps
GET    /api/v1/beatmaps/:id          # Get beatmap metadata
GET    /api/v1/beatmaps/:id/download # Download .bsm file
POST   /api/v1/beatmaps              # Upload new beatmap
PUT    /api/v1/beatmaps/:id          # Update metadata
DELETE /api/v1/beatmaps/:id          # Delete (creator only)
POST   /api/v1/beatmaps/:id/rate     # Rate beatmap
```

#### Audio Processing
```
POST   /api/v1/process               # Submit audio for AI processing
GET    /api/v1/process/:job_id       # Check processing status
GET    /api/v1/process/:job_id/result # Download generated beatmap
```

#### User Management
```
POST   /api/v1/auth/register         # Create account
POST   /api/v1/auth/login            # Authenticate
GET    /api/v1/users/:id             # Get profile
PUT    /api/v1/users/:id             # Update profile
GET    /api/v1/users/:id/beatmaps    # User's uploads
GET    /api/v1/users/:id/scores      # User's scores
```

#### Donations
```
POST   /api/v1/donate                # Create donation session (Stripe)
GET    /api/v1/donate/status         # Check donation status
```

### Database Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Beatmaps
CREATE TABLE beatmaps (
    id UUID PRIMARY KEY,
    creator_id UUID REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    artist VARCHAR(255) NOT NULL,
    audio_hash VARCHAR(64), -- SHA256 of audio
    difficulty_rating FLOAT,
    bpm FLOAT,
    duration_seconds INT,
    drum_parts TEXT[], -- Array of detected parts
    upload_date TIMESTAMP DEFAULT NOW(),
    download_count INT DEFAULT 0,
    rating_avg FLOAT,
    rating_count INT DEFAULT 0,
    file_size_bytes BIGINT,
    storage_url TEXT -- S3 URL
);

-- Scores
CREATE TABLE scores (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    beatmap_id UUID REFERENCES beatmaps(id),
    score INT NOT NULL,
    accuracy FLOAT NOT NULL,
    max_combo INT,
    count_300 INT,
    count_100 INT,
    count_50 INT,
    count_miss INT,
    played_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, beatmap_id) -- Keep only best score
);

-- Processing Jobs
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    status VARCHAR(20), -- pending, processing, completed, failed
    audio_hash VARCHAR(64),
    result_beatmap_id UUID REFERENCES beatmaps(id),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Donations
CREATE TABLE donations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) NULL, -- Optional (anonymous)
    amount_cents INT NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    stripe_session_id VARCHAR(255),
    status VARCHAR(20),
    donated_at TIMESTAMP DEFAULT NOW()
);
```

## 5. Beatmap Format (`.bsm`)

See [BEATMAP_FORMAT.md](BEATMAP_FORMAT.md) for detailed specification.

**Key Design Principles**:
- Human-readable JSON
- Version-controlled format (schema versioning)
- Extensible for future features
- Compact but not compressed (allow git diffs)

## 6. Cross-Platform Considerations

### File Format Compatibility
- `.bsm` files are identical across all platforms
- Audio files referenced relatively (platform paths normalized)
- Metadata includes platform-agnostic timestamps

### Synchronization
- Optional cloud sync for scores/progress
- Local-first design (offline capable)
- Conflict resolution for edited beatmaps

### Performance Scaling
- Desktop: Full visual effects, high frame rates
- Mobile: Reduced particle effects, battery optimization
- All platforms: Same core timing/scoring logic

## 7. Security & Privacy

### Data Protection
- Passwords: bcrypt hashing (cost factor 12)
- API: Rate limiting per IP/user
- File uploads: Virus scanning, size limits
- User data: GDPR compliant, deletion requests honored

### Copyright Considerations
- Users upload audio at own risk (ToS disclaimer)
- Optional: Store only drum stems (transformative)
- DMCA takedown process
- No direct audio redistribution without stems

## 8. Scalability Plan

### Phase 1: MVP (Months 1-3)
- Desktop app with local processing
- Basic AI pipeline (Demucs + simple onset detection)
- No backend (local files only)

### Phase 2: Community (Months 4-6)
- Backend API deployment
- User accounts and beatmap uploads
- Cloud processing queue

### Phase 3: Mobile (Months 7-9)
- iOS/Android apps
- Cross-platform sync
- Mobile-optimized gameplay

### Phase 4: Advanced (Months 10-12)
- Real-time mic input scoring
- Distributed training platform
- Advanced AI models (transformer-based)
- Sample extraction tools

## 9. Development Tools

### CI/CD Pipeline
- **GitHub Actions**: Automated builds
- **Testing**: Unit tests (xUnit for C#, pytest for Python)
- **Code Quality**: ESLint, Pylint, StyleCop
- **Docker**: Containerized deployments

### Monitoring
- **Sentry**: Error tracking
- **Prometheus + Grafana**: Metrics
- **Application Insights**: Performance monitoring

### Version Control
- **Git**: Monorepo structure
- **Git LFS**: Large binary assets
- **Conventional Commits**: Standardized commit messages

---

## Technology Decision Rationale

### Why osu-framework?
- Battle-tested for rhythm games (osu! lazer)
- Cross-platform (Windows/macOS/Linux native)
- High-performance rendering and audio
- Built-in input handling with minimal latency
- Active development and community

### Why Demucs?
- State-of-the-art source separation (2023)
- No training required (pre-trained models)
- Open-source and free
- Python-based (easy integration)

### Why FastAPI (Python) vs ASP.NET Core (C#)?
- **Recommendation**: FastAPI
  - Same language as AI pipeline (Python)
  - Async-first design (better for I/O-heavy workloads)
  - Automatic OpenAPI docs
  - Faster development iteration
- **Alternative**: ASP.NET Core if team prefers C# consistency

### Why Flutter for mobile?
- Single codebase for iOS/Android
- Good performance for UI-heavy apps
- Easier than maintaining native codebases
- Can share beatmap parsing logic with desktop (via FFI if needed)

---

**Next Steps**: See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.
