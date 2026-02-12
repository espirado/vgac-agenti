# VGAC Codebase Context

## Overview
VGAC (vgac.cloud) is a GPU observability and prediction platform. This agentic layer builds ON TOP of the existing platform, wrapping its capabilities in autonomous agents.

**Important:** The agentic layer should CALL existing VGAC APIs, not reimplement functionality.

## Core Components to Wrap

### Prediction Engine
**What it does:** Predicts GPU job queue wait times
**Performance:** 0.801 AUROC, <10ms inference
**Implementation:** LogisticRegression + IsotonicRegression calibrator
**Location:** `src/prediction/fast_predictor.py`, `src/prediction/production_model.py`

**Actual API Endpoints:**
```
POST /api/predict/wait
Request:
{
    "gpus": 1,
    "cpu": 1000,
    "memory_gb": 4,
    "priority": 0,
    "namespace": "default"
}

Response:
{
    "probability_long_wait": 0.87,
    "estimated_wait_seconds": 3600,
    "wait_category": "high",
    "confidence": 0.92,
    "is_calibrated": true,
    "recommendation": "Consider lower priority queue",
    "latency_us": 8500
}

POST /api/predict/batch - Batch predictions
GET /api/predict/stats - Service statistics
GET /api/predict/cluster-state - Current cluster state
POST /api/predict/webhook - K8s admission webhook
GET /api/predict/health - Health check
```

### Calibration System
**What it does:** Tracks prediction accuracy, triggers recalibration
**Key metric:** ECE (Expected Calibration Error)
**Baseline:** last_known_good_ece = 0.018
**State file:** `models/production/safeguard_state.json`
**Location:** Tracked in model manifest at `models/production/manifest.json`

**Actual API Endpoints:**
```
GET /api/jobs/predict/calibration
Response:
{
    "ece": 0.018,
    "brier_score": 0.12,
    "sample_count": 1847,
    "last_recalibration": "2025-02-01T...",
    "recalibration_needed": false
}

POST /api/jobs/predict - Get prediction with calibration
GET /api/jobs/predict/batch - Batch predictions
```

### Multi-Platform Collectors
**What it does:** Ingests telemetry from different GPU environments
**Platforms:** Kubernetes, Slurm HPC, AWS Batch
**Unified schema:** All platforms normalized to common format
**Location:** `src/collectors/cluster.py`, `src/collectors/gpu.py`

**Actual API Endpoints:**
```
GET /api/cluster/summary
Response:
{
    "cluster_id": "eks-prod-gpu",
    "scheduler_type": "kubernetes",
    "total_nodes": 4,
    "ready_nodes": 4,
    "total_gpus": 32,
    "available_gpus": 12,
    "gpu_utilization": 0.78,
    "pending_jobs": 12,
    "running_jobs": 8,
    "queue_depth": 12
}

GET /api/cluster/summary/quick - Fast cluster state
GET /api/cluster/bifurcation - Bifurcation analysis
GET /api/cluster/nodes - Node inventory
GET /api/cluster/slurm/status - Slurm-specific status
GET /api/cluster/slurm/queue - Slurm queue state
GET /api/cluster/capacity/forecast - Capacity forecasting
```

### Policy Generator
**What it does:** Converts predictions → K8s scheduling policies
**Confidence threshold:** 0.5 operating threshold, 0.6 confidence gate
**Actions:** Priority adjustment, memory hints, colocation, time-slicing
**Location:** `src/policy/generator.py`, `src/policy/inference_router.py`

**Key insight for agents:** The 0.6 threshold is production-tested. Use it for confidence gating.

**Policy Classes:**
```python
class PriorityClass(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BEST_EFFORT = "best_effort"

class PreemptionPolicy(Enum):
    NEVER = "never"
    RELUCTANT = "reluctant"
    NORMAL = "normal"
    EAGER = "eager"
    IMMEDIATE = "immediate"
```

**Note:** Policy generation is currently embedded in the prediction service. No separate HTTP API endpoint exists yet. Agents should use the prediction endpoints which include policy recommendations.

### Job Lifecycle Tracking
**What it does:** Track jobs from submission through completion
**Location:** `src/api/routers/jobs.py`

**Actual API Endpoints:**
```
GET /api/jobs/queue - Current queue snapshot
GET /api/jobs/pending - Pending jobs list
GET /api/jobs/running - Running jobs list
GET /api/jobs/history - Historical job data
GET /api/jobs/history/stats - Job statistics
GET /api/jobs/history/failures - Failure pattern analysis
GET /api/jobs/{job_id} - Specific job details

POST /api/jobs/predict - Predict wait time for job submission
POST /api/jobs/predict/batch - Batch job predictions
GET /api/jobs/predict/calibration - Calibration metrics
```

### Admission Webhook
**What it does:** K8s ValidatingAdmissionWebhook that gates pod admission
**Capability:** Can annotate pods with risk scores, reject high-risk submissions
**Note:** This is a K8s-specific component, not an HTTP API

## VGAC Platform File Structure

**Base Path:** `<VGAC_PLATFORM_PATH>` (set via environment variable)

### Core Components

**Prediction Engine:**
- `src/prediction/fast_predictor.py` - Ultra-low latency predictor (<10ms target)
- `src/prediction/production_model.py` - Production model wrapper
- `src/prediction/enhanced_predictor.py` - Enhanced prediction with explainability

**Policy Generator:**
- `src/policy/generator.py` - Converts predictions → scheduling policies
- `src/policy/inference_router.py` - Routes inference requests
- `src/policy/gpu_ext_bridge.py` - GPU extension bridge

**Collectors:**
- `src/collectors/base.py` - Base collector interface
- `src/collectors/cluster.py` - Cluster state collector
- `src/collectors/gpu.py` - GPU telemetry collector

**API Endpoints (FastAPI):**
- `src/api/app.py` - Main FastAPI application
- `src/api/routers/predict.py` - Prediction endpoints
- `src/api/routers/jobs.py` - Job lifecycle endpoints
- `src/api/routers/cluster.py` - Cluster state endpoints
- `src/api/routers/gpus.py` - GPU telemetry endpoints
- `src/api/routers/inference.py` - Inference routing endpoints
- `src/api/routers/telemetry.py` - Telemetry collection endpoints

**ML Models:**
- `src/ml/model_loader.py` - Model loading and caching

**Production Models:**
- `models/production/model.joblib` - Trained LogisticRegression model
- `models/production/calibrator.joblib` - IsotonicRegression calibrator
- `models/production/manifest.json` - Model metadata and metrics
- `models/production/safeguard_state.json` - Calibration safeguard state (ECE tracking)
- `models/production/feature_schema.json` - Feature definitions

**Core Models:**
- `src/core/models.py` - Core data models
- `src/core/inference_models.py` - Inference-specific models
- `src/core/gandiva_profiling.py` - Profiling utilities

### Key Configuration Files

**Safeguard State** (`models/production/safeguard_state.json`):
```json
{
  "last_known_good_ece": 0.018,
  "last_known_good_time": 1766071523.4189,
  "updated_at": "2025-12-18T10:25:23.419016"
}
```

**Model Manifest** (`models/production/manifest.json`):
- Model version: v3.0-phase2-eks
- AUROC: 0.801 (raw), 0.783 (calibrated)
- ECE: 0.098 (raw), 0.115 (calibrated)
- Features: pending_ratio, pending_at_submit
- Threshold: 0.5 operating threshold, 0.6 confidence threshold

## Key Files Reference

When Kiro generates code that interacts with VGAC, reference these patterns:

### Data Models

**From `src/api/routers/jobs.py`:**
```python
class JobState(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    unknown = "unknown"

class JobType(str, Enum):
    gpu = "gpu"
    cpu = "cpu"
    mixed = "mixed"

class WaitPrediction(BaseModel):
    job_id: str
    predicted_wait_seconds: float
    predicted_probability_long_wait: float
    confidence: float
    is_calibrated: bool
    model_version: str
    ece: Optional[float]
    expected_wait_range: Optional[Dict[str, float]]
    top_factors: List[Dict[str, Any]]
    recommendation: Optional[str]
```

**From `src/api/routers/cluster.py`:**
```python
class SchedulerType(str, Enum):
    kubernetes = "kubernetes"
    slurm = "slurm"
    unknown = "unknown"

class NodeStatus(str, Enum):
    ready = "ready"
    not_ready = "not_ready"
    schedulable = "schedulable"
    cordoned = "cordoned"
    unknown = "unknown"
```

**From `src/api/routers/predict.py`:**
```python
class JobSpec(BaseModel):
    gpus: int = 0  # Number of GPUs requested
    cpu: float = 1000  # CPU millicores
    memory_gb: float = 1  # Memory in GB
    priority: int = 0  # Job priority
    namespace: str = "default"
    queue: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    is_distributed: bool = False
    gpu_type: Optional[str] = None

class PredictionResult(BaseModel):
    probability_long_wait: float  # [0, 1]
    estimated_wait_seconds: float
    wait_category: str
    confidence: float  # [0, 1]
    is_calibrated: bool
    recommendation: Optional[str]
    latency_us: int
```

### Feature Pipeline

**Current Production Model (v3.0-phase2-eks):**
The model uses 2 primary features:
1. `pending_ratio` - Ratio of pending to total jobs
2. `pending_at_submit` - Number of pending jobs at submission time

**Cluster State Cache** (from `fast_predictor.py`):
```python
class ClusterStateCache:
    total_gpus: int
    available_gpus: int
    pending_jobs: int
    pending_gpu_jobs: int
    running_jobs: int
    gpu_utilization: float
    pending_ratio: float
    bifurcation_ratio: float
    avg_wait_last_hour: float
    p95_wait_last_hour: float
```

**Performance Targets:**
- Prediction latency: <10ms (Python), <1ms (Rust target)
- Model: LogisticRegression + IsotonicRegression calibrator
- AUROC: 0.801 (raw), 0.783 (calibrated)
- ECE: 0.098 (raw), 0.115 (calibrated)

## Integration Points for Agents

| Agent | Wraps | Primary API Endpoints |
|-------|-------|----------------------|
| ObserverAgent | Collectors | GET /api/cluster/summary<br>GET /api/cluster/summary/quick<br>GET /api/jobs/queue |
| PredictorAgent | ProductionModel | POST /api/predict/wait<br>POST /api/predict/batch<br>GET /api/predict/cluster-state |
| ActorAgent | PolicyGenerator | POST /api/jobs/predict (includes recommendations)<br>POST /api/predict/wait (includes recommendations) |
| CalibratorAgent | Safeguard state | GET /api/jobs/predict/calibration<br>GET /api/predict/stats |

## Environment Variables for VGAC Connection

**For Local Development:**
```bash
VGAC_API_BASE_URL=http://localhost:8000  # Local VGAC instance
VGAC_PLATFORM_PATH=/path/to/vgac  # Platform source directory
VGAC_TIMEOUT_SECONDS=10
```

**For Production:**
```bash
VGAC_API_BASE_URL=https://api.vgac.cloud  # Production endpoint
VGAC_API_KEY=xxx                          # If authenticated
VGAC_TIMEOUT_SECONDS=10
```

## Error Handling with VGAC
```python
class VGACAPIError(Exception):
    """VGAC API returned an error."""
    pass

class VGACTimeoutError(VGACAPIError):
    """VGAC API timed out."""
    pass

class VGACUnavailableError(VGACAPIError):
    """VGAC API is unavailable."""
    pass

# Always handle gracefully
try:
    result = await vgac_client.predict(job_id)
except VGACAPIError as e:
    logger.error(f"VGAC API error: {e}")
    return FallbackPrediction(confidence=0.0, error=str(e))
```
