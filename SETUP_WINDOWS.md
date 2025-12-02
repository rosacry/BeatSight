# BeatSight Windows Setup Guide

Complete setup instructions for developing and running BeatSight on Windows.

## Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/yourusername/BeatSight.git
cd BeatSight

# 2. Run the bootstrap script (installs all dependencies)
.\scripts\bootstrap-windows.ps1

# 3. Start the development environment
.\scripts\start-dev.ps1
```

## Prerequisites

### Required Software

| Software | Version | Download |
|----------|---------|----------|
| Git | 2.40+ | [git-scm.com](https://git-scm.com/download/win) |
| .NET SDK | 8.0+ | [dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet/8.0) |
| Node.js | 20+ LTS | [nodejs.org](https://nodejs.org/) |
| Python | 3.10+ | [python.org](https://python.org/downloads/) |
| Docker Desktop | 4.20+ | [docker.com](https://www.docker.com/products/docker-desktop/) |

### Optional but Recommended

- **Visual Studio 2022** - For desktop development with full IDE support
- **VS Code** - For frontend/backend development
- **NVIDIA GPU** - For local AI inference (CUDA 12.1+)

## Detailed Setup

### 1. Install .NET 8 SDK

Download and install from Microsoft:
```powershell
# Using winget (Windows Package Manager)
winget install Microsoft.DotNet.SDK.8

# Verify installation
dotnet --version  # Should output 8.0.x
```

### 2. Install Node.js

```powershell
# Using winget
winget install OpenJS.NodeJS.LTS

# Or use nvm-windows for version management
# https://github.com/coreybutler/nvm-windows

# Verify installation
node --version  # Should output v20.x.x
npm --version   # Should output 10.x.x
```

### 3. Install Python

```powershell
# Using winget
winget install Python.Python.3.11

# IMPORTANT: During installation, check "Add Python to PATH"

# Verify installation
python --version  # Should output Python 3.11.x
pip --version     # Should output pip 23.x.x
```

### 4. Install Docker Desktop

1. Download from [docker.com](https://www.docker.com/products/docker-desktop/)
2. Run the installer
3. Restart your computer when prompted
4. Launch Docker Desktop and complete the tutorial
5. In Settings → General, ensure "Use WSL 2 based engine" is checked

```powershell
# Verify Docker is running
docker --version
docker compose version
```

### 5. Clone and Configure Repository

```powershell
# Clone repository
git clone https://github.com/yourusername/BeatSight.git
cd BeatSight

# Configure Git for Windows line endings
git config core.autocrlf true
```

## Component Setup

### Desktop Application (BeatSight.Desktop)

```powershell
cd desktop

# Restore NuGet packages
dotnet restore

# Build the solution
dotnet build BeatSight.sln

# Run the game
dotnet run --project BeatSight.Desktop
```

**Common Issues:**
- If you get font errors, install the [Inter font family](https://rsms.me/inter/)
- For audio issues, ensure Windows Audio Service is running

### Frontend (React/Vite)

```powershell
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

The frontend will be available at `http://localhost:5173`

### Backend (FastAPI)

```powershell
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e ".[dev]"

# Start development server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Database (PostgreSQL via Docker)

```powershell
cd backend

# Start PostgreSQL and Redis
docker compose up -d

# Run database migrations
alembic upgrade head

# Seed development data (optional)
python -m app.cli seed-dev
```

### AI Pipeline (Python)

```powershell
cd ai-pipeline

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install PyTorch with CUDA (if you have NVIDIA GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Or CPU-only version
pip install torch torchvision torchaudio

# Run tests
pytest tests/
```

## Running Everything Together

### Option 1: Docker Compose (Recommended)

```powershell
# From repository root
docker compose -f docker-compose.dev.yml up
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- Backend API on port 8000
- Frontend on port 5173

### Option 2: Individual Terminals

Open 4 PowerShell terminals:

**Terminal 1 - Database:**
```powershell
cd backend
docker compose up
```

**Terminal 2 - Backend:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Terminal 3 - Frontend:**
```powershell
cd frontend
npm run dev
```

**Terminal 4 - Desktop:**
```powershell
cd desktop
dotnet run --project BeatSight.Desktop
```

## GPU Acceleration Setup

### NVIDIA GPU (CUDA)

1. Install [NVIDIA Driver](https://www.nvidia.com/drivers) (535+)
2. Install [CUDA Toolkit 12.1](https://developer.nvidia.com/cuda-downloads)
3. Install [cuDNN 8.9](https://developer.nvidia.com/cudnn)

```powershell
# Verify CUDA installation
nvcc --version
nvidia-smi

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### AMD GPU (ROCm)

ROCm is not officially supported on Windows. Use CPU inference or WSL2 with Linux.

### No GPU

The AI pipeline works on CPU but is significantly slower (~10x). Recommended to use the cloud API for beatmap generation.

## Environment Variables

Create a `.env` file in the repository root:

```env
# Backend
DATABASE_URL=postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-change-in-production
ENVIRONMENT=development

# AI Pipeline
MODAL_TOKEN_ID=your-modal-token
MODAL_TOKEN_SECRET=your-modal-secret

# Storage (choose one)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET=beatsight-dev

# Frontend
VITE_API_URL=http://localhost:8000/api
```

## IDE Setup

### Visual Studio 2022

1. Open `BeatSight.sln`
2. Install recommended extensions:
   - Python Tools for Visual Studio
   - Node.js development workload
3. Set `BeatSight.Desktop` as startup project

### VS Code

1. Install recommended extensions (prompted on first open)
2. Open workspace: `File → Open Workspace from File → beatsight.code-workspace`
3. Select Python interpreter: `Ctrl+Shift+P → Python: Select Interpreter`

Recommended extensions:
- C# Dev Kit
- Python
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Docker

## Troubleshooting

### "dotnet: command not found"

Add .NET to PATH:
```powershell
$env:PATH += ";C:\Program Files\dotnet"
# Add permanently via System Properties → Environment Variables
```

### Python pip install fails with "Microsoft Visual C++ 14.0 is required"

Install Build Tools for Visual Studio:
```powershell
winget install Microsoft.VisualStudio.2022.BuildTools
# During installation, select "Desktop development with C++"
```

### Docker Desktop won't start

1. Ensure virtualization is enabled in BIOS
2. Enable Hyper-V and WSL2:
```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```
3. Restart computer

### Port already in use

```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### Audio not working in desktop app

1. Ensure Windows Audio Service is running
2. Check default audio device in Sound settings
3. Try running as Administrator

### Database connection refused

```powershell
# Check if PostgreSQL container is running
docker ps

# View container logs
docker logs beatsight-postgres

# Restart containers
docker compose down
docker compose up -d
```

## Running Tests

### Desktop (NUnit)
```powershell
cd desktop
dotnet test
```

### Backend (pytest)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

### Frontend (Vitest + Playwright)
```powershell
cd frontend
npm run test        # Unit tests
npm run test:e2e    # E2E tests
```

### AI Pipeline (pytest)
```powershell
cd ai-pipeline
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

## Next Steps

1. Read the [Architecture Guide](docs/ARCHITECTURE.md)
2. Check [Contributing Guidelines](docs/CONTRIBUTING.md)
3. Join our Discord for help
4. Try the [Quick Start Tutorial](docs/Guidebook.md)

## Getting Help

- **Discord**: [BeatSight Community](https://discord.gg/beatsight)
- **GitHub Issues**: [Report bugs](https://github.com/yourusername/BeatSight/issues)
- **Discussions**: [Ask questions](https://github.com/yourusername/BeatSight/discussions)
