# Contributing to OpenDemocracy AI

Thank you for your interest in contributing to OpenDemocracy AI! This project thrives on diverse perspectives — we need developers, data scientists, political scientists, ethicists, designers, translators, community organizers, and constructive critics.

## Getting Started

1. **Fork the repository** and clone your fork locally.
2. **Create a branch** for your work: `git checkout -b feature/your-feature-name`
3. **Make your changes** following the guidelines below.
4. **Write tests** for any new functionality.
5. **Submit a pull request** against the `main` branch.

## Development Setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/OpenDemocracy.git
cd OpenDemocracy

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
ruff format --check .

# Run type checking
mypy src/
```

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- We use [mypy](https://mypy-lang.org/) for type checking.
- Write clear, self-documenting code. Add comments only where the logic isn't self-evident.
- All public APIs should have docstrings.

## Commit Messages

Write clear commit messages that explain **why** a change was made, not just what changed.

```
Add opinion clustering pipeline for Phase 2 pilot

Implements k-means and HDBSCAN clustering on embedded opinion
vectors to identify natural groupings in participant responses.
```

## Pull Request Process

1. Ensure all tests pass and linting is clean.
2. Update documentation if your change affects public APIs or user-facing behavior.
3. Fill out the PR template with a description of your changes.
4. Request review from at least one maintainer.
5. PRs require approval from one maintainer before merging.

## Types of Contributions

### Bug Reports

Open an issue using the Bug Report template. Include:
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, etc.)

### Feature Proposals

Open an issue using the Feature Proposal template. Include:
- Problem statement
- Proposed solution
- How it aligns with the project's core principles
- Any tradeoffs or alternatives considered

### Code Contributions

- **Small fixes** (typos, minor bugs): Submit a PR directly.
- **New features or large changes**: Open an issue first to discuss the approach before investing significant time.

### Non-Code Contributions

We value contributions beyond code:
- Documentation improvements
- Translations
- Community organizing and pilot facilitation
- Research on democratic processes and collective intelligence
- UX/UI design work
- Security auditing

## Ethical Guidelines

This project serves democratic participation. Contributions must:

- **Preserve neutrality**: The system must not favor any political position, ideology, or interest group.
- **Protect privacy**: Never introduce code that could de-anonymize participants.
- **Maintain transparency**: All algorithms and data processing must be auditable.
- **Resist capture**: Avoid dependencies or designs that could give any single entity undue control.

## Code of Conduct

All participants are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming, inclusive, and harassment-free experience for everyone.

## Questions?

- Open a [Discussion](https://github.com/AshmanRoonz/OpenDemocracy/discussions) on GitHub
- Community channels: Discord/Matrix (links TBD)

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
