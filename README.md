# ⚡ PredictiveOps — AWS Outage Early-Warning & Auto-Heal

**PredictiveOps** watches your AWS workloads for *early signs* of failure and kicks off **automated remediation** before customers feel it.

- ✅ EC2 restart automation (via SSM `PredictiveOps-RestartEC2`)
- ✅ ECS service redeploy automation (via SSM `PredictiveOps-RedeployECSService`)
- ✅ Lambda-based risk scoring on latency / error rate / DNS anomalies
- ✅ DynamoDB risk ledger (`predictiveops_risk`)
- ✅ SNS alerts to on-call email

---

## 🧩 High-Level Architecture

- **CloudWatch / external signals** → event with `latency`, `errorRate`, optional `nxdomain`
- **Lambda `predictiveops-lambda`**:
  - computes a risk score
  - writes record into DynamoDB (`predictiveops_risk`)
  - publishes optional SNS alert
  - if risk ≥ threshold and cooldown OK:
    - EC2: starts SSM `PredictiveOps-RestartEC2`
    - ECS: starts SSM `PredictiveOps-RedeployECSService`

- **SSM Automation**:
  - `PredictiveOps-RestartEC2` stops / waits / starts EC2
  - `PredictiveOps-RedeployECSService` forces new ECS deployment and waits until rollout is `COMPLETED`

---

## 🔧 Components

- Lambda: `predictiveops-lambda`
- DynamoDB table: `predictiveops_risk`
- SNS topic: `predictiveops-alerts`
- IAM roles:
  - `predictiveops-lambda-role`
  - `predictiveops-automation-role`
- SSM Documents:
  - `PredictiveOps-RestartEC2`
  - `PredictiveOps-RedeployECSService`

---

## 🚦 Risk Scoring

- +0.45 if latency ≥ 200ms  
- +0.45 if errorRate ≥ 1%  
- +0.15 if NXDOMAIN anomaly detected  
- Capped at 1.0, with default trigger at **0.75**

---

## 🧪 Local / Lab Validation

Prototype validated in AWS CloudShell with:

- ✅ EC2 restart automation
- ✅ ECS redeploy automation
- ✅ SNS email alert path
- ✅ DynamoDB logging for all risk events

---

## 🚀 Roadmap to “Marketplace-Ready”

- [ ] CloudFormation / CDK or Terraform one-click deploy
- [ ] Config UI or simple API for:
  - adding EC2/ECS targets
  - changing thresholds
  - tuning cooldowns
- [ ] Multi-account / multi-region aggregation
- [ ] AWS Marketplace listing (SaaS or container-based)

## Architecture

See: [docs/architecture.md](docs/architecture.md)

