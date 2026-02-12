# VGAC Agentic Layer

An agentic intelligence layer for [VGAC](https://vgac.cloud) GPU observability platform.

**Competition:** AWS AIdeas 2025  
**Deadline:** March 13, 2025  
**Budget:** $200 AWS credits

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

| Agent | Purpose | Key Behavior |
|-------|---------|--------------|
| **Observer** | Watch cluster state | Detect anomalies |
| **Predictor** | Predict wait times | Calibration-aware confidence |
| **Actor** | Take actions | Gate actions by calibration |
| **Calibrator** | Monitor accuracy | Trigger recalibration |

## Confidence Gating

```
Calibration > 0.85  →  Autonomous action
0.60 < Cal < 0.85   →  Act + notify human  
Calibration < 0.60  →  Escalate only, no autonomous action
```

## Setup

```bash
# Clone
git clone https://github.com/your-org/vgac-agentic.git
cd vgac-agentic

# Install dependencies
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your VGAC API URL and Slack webhook

# Run tests
pytest

# Deploy
sam build
sam deploy --guided
```

## Project Structure

```
vgac-agentic/
├── .kiro/                    # Kiro AI assistant configuration
│   ├── project.md            # Project context
│   ├── rules/                # Code standards, AWS constraints
│   └── skills/               # VGAC context, agent patterns, calibration
├── src/
│   ├── agents/               # Agent implementations
│   ├── tools/                # Tool definitions for AgentCore
│   └── clients/              # VGAC, Slack, DynamoDB clients
├── lambdas/                  # Lambda function handlers
├── infrastructure/           # SAM/CloudFormation templates
└── tests/
```

## Built With

- **Kiro** - AI-powered development
- **AWS Bedrock AgentCore** - Agent orchestration
- **AWS Lambda** - Serverless compute
- **AWS DynamoDB** - State storage
- **Slack** - User notifications

## Cost

Total estimated: **$150** (within $200 budget)

| Component | Service | Cost |
|-----------|---------|------|
| Agent orchestration | Bedrock AgentCore | $50 |
| Agent reasoning | Bedrock Haiku | $35 |
| Compute | Lambda | Free tier |
| Storage | DynamoDB | Free tier |
| Buffer | Testing | $65 |

## License

MIT
