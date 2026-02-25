# Technical Architecture

This document describes the technical architecture of OpenDemocracy AI. It expands on the high-level overview in the README and serves as the guiding blueprint for implementation.

## Overview

OpenDemocracy AI is structured as a four-layer pipeline:

```
Input -> Processing -> Modeling -> Output
```

Each layer is modular and independently deployable. Layers communicate through well-defined interfaces, allowing components to be swapped, upgraded, or run by different parties.

## Layer 1: Input

**Purpose**: Collect human perspectives through multiple channels while ensuring privacy and authenticity.

### Components

- **Survey Engine** (`opendemocracy.input.surveys`): Structured questionnaires with branching logic and open-ended responses.
- **Forum Connector** (`opendemocracy.input.connectors`): Adapters for ingesting public discourse from platforms (Reddit, X, forums) via their APIs.
- **Assembly Interface** (`opendemocracy.input.assemblies`): Integration with citizen assembly and deliberative democracy formats.
- **API Gateway** (`opendemocracy.input.api`): RESTful API for third-party integrations.

### Key Requirements

- All inputs are anonymized at the point of collection.
- Verified-human checks (proof-of-personhood) without identity disclosure.
- Opt-in participation only.
- Input provenance tracking (source type, not source identity).

## Layer 2: Processing

**Purpose**: Analyze, structure, and contextualize raw input into meaningful data.

### Components

- **NLP Pipeline** (`opendemocracy.processing.nlp`): Text analysis including tokenization, embedding, and semantic parsing.
- **Sentiment Analysis** (`opendemocracy.processing.sentiment`): Multi-dimensional sentiment mapping (not just positive/negative).
- **Opinion Clustering** (`opendemocracy.processing.clustering`): Group similar perspectives using unsupervised learning.
- **Demographic Contextualization** (`opendemocracy.processing.demographics`): Analyze how views vary across self-reported demographic dimensions.
- **Bias Detection** (`opendemocracy.processing.bias`): Flag potential sampling bias, framing effects, and manipulation attempts.

### Key Requirements

- All algorithms must be transparent and auditable.
- Processing pipeline must be reproducible given the same inputs.
- Bias detection runs on every processing step, not just the final output.

## Layer 3: Modeling

**Purpose**: Project consequences, identify tradeoffs, and generate scenarios.

### Components

- **Consequence Simulation** (`opendemocracy.modeling.simulation`): Model downstream effects of policy choices.
- **Tradeoff Analysis** (`opendemocracy.modeling.tradeoffs`): Identify where priorities genuinely conflict.
- **Scenario Generation** (`opendemocracy.modeling.scenarios`): Create plausible futures under different assumptions.
- **Temporal Projection** (`opendemocracy.modeling.temporal`): Track how collective views evolve over time.

### Key Requirements

- All models must declare their assumptions explicitly.
- Uncertainty must be quantified and communicated (confidence intervals, sensitivity analysis).
- Models must be falsifiable — testable against real-world outcomes.

## Layer 4: Output

**Purpose**: Present results in accessible, honest, and actionable formats.

### Components

- **Dashboard** (`opendemocracy.output.dashboard`): Interactive web-based visualization of results.
- **API** (`opendemocracy.output.api`): Programmatic access to all results and underlying data.
- **Reports** (`opendemocracy.output.reports`): Generated summary reports with full methodology transparency.
- **Widgets** (`opendemocracy.output.widgets`): Embeddable components for third-party sites.

### Key Requirements

- Always show full distributions, not just averages or majorities.
- Group-specific breakdowns available for any output.
- Confidence intervals on all quantitative claims.
- Methodology section accompanies every output.

## Cross-Cutting Concerns

### Privacy

- Differential privacy applied to all outputs.
- No individual response is ever recoverable from aggregate data.
- Data retention policies configurable per deployment.

### Security

- Input validation at every boundary.
- Rate limiting and anomaly detection on all public endpoints.
- Sybil resistance through proof-of-personhood mechanisms.

### Scalability

- Each layer can be scaled independently.
- Designed for horizontal scaling.
- Supports both centralized and federated deployment models.

### Internationalization

- Multi-language support from the ground up.
- Cross-cultural sentiment analysis that accounts for linguistic and cultural context.
- All user-facing text externalized for translation.

## Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | Python 3.12+ | Ecosystem for NLP/ML, broad contributor base |
| Web Framework | FastAPI | Async, typed, auto-documented APIs |
| NLP | spaCy, Hugging Face Transformers | Industry-standard, open-source NLP |
| ML/Clustering | scikit-learn, HDBSCAN | Well-tested unsupervised learning |
| Database | PostgreSQL | Reliable, supports complex queries |
| Cache | Redis | Fast caching for real-time features |
| Task Queue | Celery | Distributed task processing |
| Frontend | React / Next.js | Component-based, large ecosystem |
| Testing | pytest | Standard Python testing |
| CI/CD | GitHub Actions | Integrated with repository |

## Data Flow

```
Participant
    |
    v
[Input Layer] -- anonymize + validate --> raw_opinions table
    |
    v
[Processing Layer] -- NLP + clustering --> processed_opinions, clusters tables
    |
    v
[Modeling Layer] -- simulate + project --> scenarios, projections tables
    |
    v
[Output Layer] -- visualize + serve --> dashboards, APIs, reports
```

## Getting Started with Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions. The source code is organized under `src/opendemocracy/` with sub-packages matching each architecture layer.
