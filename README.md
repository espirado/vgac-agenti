# VGAC Agentic Layer

An agentic intelligence layer for [VGAC](https://vgac.cloud) GPU observability platform.

**Competition:** AWS AIdeas 2025  
**Deadline:** March 13, 2025  
**Budget:** $200 AWS credits  
**Repository:** https://github.com/espirado/vgac-agenti

## The Problem

Most AI agents are equally confident everywhere—and wrong. They have no mechanism to detect when they're operating outside their training distribution.

## Our Solution

VGAC agents implement **environment-aware calibration**:
- Track accuracy per GPU environment (EKS, Slurm, Batch)
- Detect when predictions are unreliable
- Reduce autonomy when calibration drifts
- Request human validation in unfamiliar environments

This is grounded in research showing **22× calibration degradation** across different GPU schedulers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        vgac.cloud (existing)                    │
│   Prediction Engine │ Collectors │ Policy Generator            │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP/REST
┌───────────────────────────────┴─────────────────────────────────┐
│                    AGENTIC LAYER (this project)                 │
│                                                                 │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│   │ Observer  │  │ Predictor │  │   Actor   │  │Calibrator │  │
│   │   Agent   │  │   Agent   │  │   Agent   │  │   Agent   │  │
│   └───────────┘  └───────────┘  └───────────┘  └───────────┘  │
│                         │                                       │
│              Bedrock AgentCore Orchestrator                     │
└─────────────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Purpose | Key Behavior | Tools |
|-------|---------|--------------|-------|
| **Observer** | Watch cluster state | Detect anomalies, provide situational awareness | `tool_get_cluster_state`<br>`tool_get_queue_depth`<br>`tool_detect_anomaly` |
| **Predictor** | Predict wait times | Calibration-aware confidence scoring | `tool_predict_wait_time`<br>`tool_get_calibration_score`<br>`tool_get_environment_profile` |
| **Actor** | Take actions | Gate actions by calibration confidence | `tool_send_slack_notification`<br>`tool_requeue_job`<br>`tool_adjust_priority`<br>`tool_escalate_to_human` |
| **Calibrator** | Monitor accuracy | Trigger recalibration when drift detected | `tool_check_calibration_drift`<br>`tool_trigger_recalibration`<br>`tool_update_environment_profile` |

## Key Features

### 1. Environment-Aware Calibration
- Track prediction accuracy per GPU environment (EKS, Slurm, Batch)
- Detect 22× calibration degradation across schedulers
- Maintain per-cluster calibration profiles

### 2. Confidence-Gated Actions
- **High confidence (>0.85)**: Autonomous action
- **Medium confidence (0.60-0.85)**: Act + notify human
- **Low confidence (<0.60)**: Escalate only, no autonomous action

### 3. Drift Detection
- Monitor Expected Calibration Error (ECE) vs baseline (0.018)
- Trigger recalibration when drift exceeds 2× baseline
- Learning mode for new environments (<50 samples)

### 4. Multi-Platform Support
- Kubernetes (EKS)
- Slurm HPC clusters
- AWS Batch
- Unified telemetry schema

## Confidence Gating

```
Calibration > 0.85  →  Autonomous action
0.60 < Cal < 0.85   →  Act + notify human  
Calibration < 0.60  →  Escalate only, no autonomous action
```

## Quick Start

### Prerequisites
- Python 3.11+
- VGAC platform running locally or accessible via API
- AWS account (for deployment)

### Installation

```bash
# Clone
git clone https://github.com/espirado/vgac-agenti.git
cd vgac-agenti

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your settings:
#   - VGAC_API_BASE_URL (http://localhost:8000 for local)
#   - VGAC_PLATFORM_PATH (path to VGAC platform source)
#   - SLACK_WEBHOOK_URL (for notifications)
#   - AWS_REGION and DYNAMODB_TABLE_NAME
```

### Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
```

### Deployment

```bash
# Build SAM application
sam build

# Deploy to AWS
sam deploy --guided

# Or use AWS CDK (coming soon)
```

## Project Structure

```
vgac-agenti/
├── .kiro/                    # Kiro AI assistant configuration
│   ├── project.md            # Project context and overview
│   ├── rules/                # Code standards, AWS constraints, testing
│   │   ├── aws-constraints.md
│   │   ├── code-standards.md
│   │   └── testing.md
│   └── skills/               # Domain knowledge and patterns
│       ├── vgac-context.md   # VGAC platform API mapping
│       ├── agent-patterns.md # Agent design patterns
│       ├── calibration.md    # Calibration logic
│       └── integration.md    # Integration patterns
├── src/
│   └── agents/               # Agent implementations
│       ├── base.py           # Base agent class
│       ├── observer.py       # Cluster monitoring agent
│       ├── predictor.py      # Wait time prediction agent
│       ├── actor.py          # Action execution agent
│       └── calibrator.py     # Calibration monitoring agent
├── tests/
│   ├── conftest.py           # Pytest configuration
│   └── test_calibration.py  # Calibration tests
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── pyproject.toml            # Python project config
└── README.md                 # This file
```

### Coming Soon
- `src/tools/` - Tool definitions for Bedrock AgentCore
- `src/clients/` - VGAC, Slack, DynamoDB clients
- `lambdas/` - Lambda function handlers
- `infrastructure/` - SAM/CloudFormation templates

## Technology Stack

### Development
- **Python 3.11+** - Core language
- **Kiro** - AI-powered development assistant
- **Pytest** - Testing framework
- **Ruff** - Fast Python linter
- **MyPy** - Static type checking

### AWS Services (Deployment)
- **AWS Bedrock AgentCore** - Agent orchestration
- **AWS Bedrock (Claude Haiku)** - Agent reasoning
- **AWS Lambda** - Serverless compute
- **AWS DynamoDB** - Calibration state storage
- **AWS SAM** - Infrastructure as code

### Integrations
- **VGAC Platform** - GPU observability and prediction
- **Slack** - User notifications and alerts
- **Kubernetes** - Job scheduling integration

## VGAC Platform Integration

This agentic layer wraps the existing VGAC platform via REST APIs:

**VGAC Platform Components:**
- **Prediction Engine** - `src/prediction/fast_predictor.py` (0.801 AUROC, <10ms)
- **Calibration System** - `models/production/safeguard_state.json` (ECE: 0.018)
- **Collectors** - `src/collectors/` (K8s, Slurm, AWS Batch)
- **Policy Generator** - `src/policy/generator.py` (0.6 confidence threshold)

**API Endpoints Used:**
- `POST /api/predict/wait` - Wait time predictions
- `GET /api/cluster/summary` - Cluster state
- `GET /api/jobs/queue` - Job queue status
- `GET /api/jobs/predict/calibration` - Calibration metrics

See `.kiro/skills/vgac-context.md` for complete API documentation.

## Cost Estimate

Total estimated: **$150** (within $200 AWS AIdeas budget)

| Component | Service | Monthly Cost |
|-----------|---------|--------------|
| Agent orchestration | Bedrock AgentCore | $50 |
| Agent reasoning | Bedrock Claude Haiku | $35 |
| Compute | Lambda (1M requests) | Free tier |
| Storage | DynamoDB (25GB) | Free tier |
| Testing buffer | Development/testing | $65 |

## Development Status

- [x] Agent base classes and interfaces
- [x] Calibration logic and confidence gating
- [x] Kiro skills and project documentation
- [ ] VGAC API client implementation
- [ ] Bedrock AgentCore integration
- [ ] Lambda handlers and deployment
- [ ] Slack notification integration
- [ ] DynamoDB state management
- [ ] End-to-end testing
- [ ] Production deployment

## Contributing

This project is being developed for AWS AIdeas 2025 competition. Contributions welcome after initial submission.

## License

MIT

## Acknowledgments

- Built with [Kiro](https://kiro.ai) AI-powered development
- VGAC platform for GPU observability
- AWS Bedrock for agent orchestration
