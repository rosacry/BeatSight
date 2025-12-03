# Contributing to BeatSight

Thank you for your interest in contributing to BeatSight! This document provides guidelines and information for contributors.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help create a welcoming community

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/rosacry/BeatSight/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, .NET version, etc.)
   - Screenshots/videos if applicable

### Suggesting Features

1. Check [Discussions](https://github.com/rosacry/BeatSight/discussions) for similar ideas
2. Create a new discussion or issue explaining:
   - The problem it solves
   - Proposed solution
   - Alternative approaches considered
   - Impact on existing features

### Contributing Code

#### Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/BeatSight.git`
3. Create a feature branch: `git checkout -b feature/amazing-feature`
4. Set up development environment (see README.md)

#### Development Guidelines

**C# Code (Desktop App)**
- Follow Microsoft C# coding conventions
- Use latest C# language features where appropriate
- Add XML documentation comments for public APIs
- Write unit tests for new features
- Use meaningful variable and method names

**Python Code (AI Pipeline)**
- Follow PEP 8 style guide
- Use type hints for function signatures
- Write docstrings for all functions/classes
- Add unit tests with pytest
- Keep functions focused and modular

**Git Commits**
- Use conventional commits format:
  - `feat:` New features
  - `fix:` Bug fixes
  - `docs:` Documentation changes
  - `refactor:` Code refactoring
  - `test:` Adding tests
  - `chore:` Maintenance tasks

Example: `feat(editor): add waveform zoom controls`

#### Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. **Run local CI checks before pushing** (uses [`act`](https://github.com/nektos/act) to run real GitHub Actions in Docker):
   ```bash
   # List all available CI jobs
   ./scripts/act-local.sh
   
   # Run specific jobs:
   ./scripts/act-local.sh backend-lint       # Ruff lint + format
   ./scripts/act-local.sh backend-test       # pytest with Postgres/Redis
   ./scripts/act-local.sh desktop-build      # .NET build + test
   ./scripts/act-local.sh ai-pipeline-test   # AI pipeline tests
   ```
   **All checks must pass before pushing.** Requires Docker Desktop and `act` (`winget install nektos.act`).
4. Ensure all tests pass: `dotnet test` / `pytest`
5. Update CHANGELOG.md (if applicable)
6. Create pull request with:
   - Clear description of changes
   - Link to related issue(s)
   - Screenshots/videos for UI changes
6. Address review feedback
7. Squash commits if requested

### Contributing Beatmaps

1. Create high-quality beatmaps using the editor
2. Test thoroughly for accuracy and playability
3. Include appropriate metadata (title, artist, tags)
4. Upload via the in-app community feature
5. OR submit via GitHub if suitable for sample beatmaps

### Improving AI Models

**Dataset Contributions**
- Label drum hits in audio files
- Contribute to the training dataset
- Follow labeling guidelines in `ai-pipeline/training/README.md`

**Model Improvements**
- Experiment with new architectures
- Share training results and metrics
- Document hyperparameters and configuration
- Provide evaluation on test set

**Distributed Training**
- Use the training contributor app
- Report any issues or bugs
- Share hardware specs and performance

## Development Setup

### Desktop App

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet build
dotnet run
```

### AI Pipeline

```bash
cd ai-pipeline
python -m venv venv
source venv/bin/activate  # or venv/bin/activate.fish
pip install -r requirements.txt
pip install -e .  # Editable install
pytest tests/  # Run tests
```

### Backend API

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

## Testing

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Benchmark critical paths

## Documentation

- Update README.md for user-facing changes
- Update architecture docs for structural changes
- Add inline comments for complex logic
- Create tutorials for new features

## Community

- **Discussions**: Use [GitHub Discussions](https://github.com/rosacry/BeatSight/discussions) for questions
- **Issues**: Use [GitHub Issues](https://github.com/rosacry/BeatSight/issues) for bugs and features

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Credited in release notes
- Featured in the app's About section (for significant contributions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to ask in:
- GitHub Issues: Open a discussion or question issue on this repository
- GitHub Discussions: Use the Discussions tab for open-ended questions

Thank you for contributing to BeatSight! 🥁
