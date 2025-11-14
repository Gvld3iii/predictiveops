# PredictiveOps — AWS Outage Early-Warning & Auto-Heal

PredictiveOps is an AWS-native early-warning system that detects elevated risk
of outages using CloudWatch, DevOps Guru-style signals, and Lambda,
then automatically triggers SSM Automation runbooks to restart EC2 instances
or redeploy ECS services.

## Core Features
- Risk scoring for latency / error spikes and DNS anomalies
- Writes risk events to DynamoDB
- Sends alerts via SNS
- Triggers SSM runbooks:
  - `PredictiveOps-RestartEC2`
  - `PredictiveOps-RedeployECSService`

## Repo Layout
- `lambda/` — Lambda handler (`predictive_ops_handler.py`)
- `infra/` — IAM, SSM, DynamoDB snapshots (JSON/YAML)
- `infra-snapshot-YYYYMMDD.zip` — exported infra snapshot

## Status
Prototype validated in AWS CloudShell with:
- EC2 restart automation ✅
- ECS redeploy automation ✅
