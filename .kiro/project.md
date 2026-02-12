# VGAC Agentic Layer

## Project Overview
An agentic intelligence layer on top of the existing VGAC GPU observability platform (vgac.cloud).

**Competition:** AWS AIdeas 2025
**Deadline:** March 13, 2025 (article), March 20 (voting)
**Budget:** $200 AWS credits

## What VGAC Already Has
VGAC predicts GPU job queue wait times with 0.969 AUROC across 12,000+ production job events.

Existing capabilities:
- **Prediction Engine:** LogisticRegression + IsotonicRegression calibrator, 8-feature pipeline, <10ms inference
- **Multi-Platform Collectors:** K8s, Slurm, AWS Batch unified schema
- **Policy Generator:** Converts predictions → K8s scheduling policies with 0.6 confidence threshold
- **40+ FastAPI Endpoints:** Full API surface for jobs, GPUs, cluster, predict, inference, telemetry
- **K8s Admission Webhook:** ValidatingAdmissionWebhook that annotates pods with risk scores

## What the Agentic Layer Adds
- **Autonomous Decision-Making:** Observe → Predict → Act → Learn loop
- **Environment-Specific Recalibration:** Track confidence per cluster, adapt behavior
- **Natural Language Interface:** Slack bot for "When will my job start?"
- **Confidence-Gated Actions:** Autonomous when confident, escalate when not

## Key Research Insight
Calibration degrades 22× across different GPU schedulers. An agent trained on one environment will be overconfident on another. This layer makes agents that KNOW when they don't know.

## The Pitch
> "Most AI agents are equally confident everywhere—and wrong. VGAC agents recalibrate confidence per environment, using the same methodology that revealed 22× calibration drift across GPU schedulers."

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        vgac.cloud                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   EXISTING VGAC PLATFORM                                        │
│   ├── Prediction Engine (0.969 AUROC)                          │
│   ├── Telemetry Ingestion                                       │
│   ├── Dashboard                                                 │
│   └── 12K+ production job events                                │
│                                                                 │
│   ─────────────────────────────────────────────────────────     │
│                           +                                     │
│   ─────────────────────────────────────────────────────────     │
│                                                                 │
│   NEW: AGENTIC INTELLIGENCE LAYER (This Project)               │
│   ├── ObserverAgent — wraps collectors                          │
│   ├── PredictorAgent — wraps ProductionModel                    │
│   ├── ActorAgent — wraps PolicyGenerator + Slack                │
│   ├── CalibratorAgent — wraps safeguard state                   │
│   └── Future: MCP integration                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Success Criteria
1. Working multi-agent system on AWS (AgentCore + Lambda)
2. Confidence-gated actions demonstrated
3. Recalibration loop shown in demo
4. Total cost < $200
5. Article published with Kiro workflow screenshots
