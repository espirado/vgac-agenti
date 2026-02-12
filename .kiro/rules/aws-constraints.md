# AWS Constraints

## Budget
**Total: $200 maximum**

This is a hard constraint. Every AWS service choice must consider cost.

## Service Selection Priority

### 1. Free Tier First (Always Prefer)
| Service | Free Tier Limit | Our Expected Usage |
|---------|-----------------|-------------------|
| Lambda | 1M requests, 400K GB-sec/month | ~50K requests |
| API Gateway | 1M calls/month | ~10K calls |
| DynamoDB | 25GB, 25 RCU/WCU | ~1GB |
| S3 | 5GB, 20K GET, 2K PUT | ~500MB |
| SNS | 1M publishes | ~1K |
| Step Functions | 4,000 state transitions | ~2K |
| CloudWatch | 10 metrics, 5GB logs | Basic |
| X-Ray | 100K traces | ~5K |

### 2. Serverless Over Provisioned (Always)
- ✅ Lambda, not EC2
- ✅ DynamoDB on-demand, not provisioned capacity
- ✅ SageMaker Serverless Inference, not real-time endpoints
- ✅ API Gateway, not ALB

### 3. Bedrock Model Selection
| Model | Cost | Use Case |
|-------|------|----------|
| Claude Haiku | $0.00025/1K input, $0.00125/1K output | **Default for all agents** |
| Claude Sonnet | $0.003/1K input, $0.015/1K output | Only for complex reasoning |
| Claude Opus | $0.015/1K input, $0.075/1K output | **Never use** |

**Rule:** Always use Haiku unless the task explicitly requires deeper reasoning.

## Budget Allocation
| Component | Service | Budget |
|-----------|---------|--------|
| Agent orchestration | Bedrock AgentCore | $50 |
| Agent reasoning | Bedrock Haiku | $35 |
| Prediction serving | Lambda (wraps VGAC API) | $5 |
| Environment profiles | DynamoDB | $5 |
| Calibration state | S3 | $0 |
| Slack integration | API Gateway + Lambda | $2 |
| CloudWatch dashboards | CloudWatch | $3 |
| Buffer (testing/mistakes) | — | $100 |
| **Total** | | **$200** |

## Cost Optimization Patterns

### Batch Agent Calls
```python
# ❌ Bad: Multiple orchestration steps
await agent.observe()
await agent.predict()
await agent.decide()

# ✅ Good: Single orchestrated call
await agent.observe_predict_decide()  # One AgentCore invocation
```

### Cache in DynamoDB
```python
# ❌ Bad: Repeated Bedrock calls for same context
explanation = await bedrock.generate(f"Explain cluster {cluster_id}")

# ✅ Good: Cache explanations
cached = await dynamodb.get(f"explanation:{cluster_id}")
if not cached or cached.age > timedelta(hours=1):
    explanation = await bedrock.generate(...)
    await dynamodb.put(f"explanation:{cluster_id}", explanation)
```

### Minimize Token Usage
```python
# ❌ Bad: Verbose prompts
prompt = f"""
You are an expert GPU cluster analyst. Your job is to analyze 
the following cluster state and provide detailed insights...
{full_cluster_dump}
"""

# ✅ Good: Concise prompts
prompt = f"Cluster {cluster_id}: {queue_depth} queued, {gpu_util}% util. Predict wait."
```

## Infrastructure Patterns

### SAM Template Structure
```yaml
# Use SAM for deployment (simpler than raw CloudFormation)
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.11
    Timeout: 30
    MemorySize: 256  # Start small, increase if needed
    
Resources:
  # Lambda functions
  # DynamoDB tables (PAY_PER_REQUEST billing)
  # API Gateway
  # IAM roles
```

### DynamoDB Design
```
# Single table design
PK: CLUSTER#{cluster_id}
SK: CALIBRATION | PROFILE | PREDICTION#{timestamp}

# On-demand billing (no provisioned capacity)
BillingMode: PAY_PER_REQUEST
```

## Forbidden (Cost Reasons)
- ❌ EC2 instances
- ❌ RDS databases
- ❌ ECS/EKS clusters
- ❌ Real-time SageMaker endpoints
- ❌ Provisioned DynamoDB capacity
- ❌ NAT Gateways
- ❌ Claude Opus model
