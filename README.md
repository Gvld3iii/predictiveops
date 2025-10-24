# ⚡ PredictiveOps — AWS Outage Early-Warning System

**PredictiveOps** is an AWS-native early-warning framework that predicts regional or service-level instability *before* it causes downtime.  
It leverages **CloudWatch**, **DevOps Guru**, **Lambda**, **EventBridge**, and **SNS** to monitor real-time telemetry and trigger proactive alerts.

## 🚀 Features
- Anomaly detection with CloudWatch & DevOps Guru
- Lambda correlator computes a risk score from latency, error rates, DNS anomalies
- SNS emails for proactive alerts
- Route53 Resolver logs → NXDOMAIN anomaly metric

## 🧩 Flow
1. Metrics & logs → CloudWatch  
2. CloudWatch + DevOps Guru insights → EventBridge  
3. EventBridge rule → triggers `predictive-correlator` Lambda  
4. Lambda → computes risk & publishes to SNS (`predictive-outage-alerts`)  
5. SNS → sends early warning emails

## 🧠 Core Lambda Logic
```python
if latency > 200: risk += 0.5
if errors  > 1.0: risk += 0.5
if risk >= 0.7:
    sns.publish(TopicArn=SNS_ARN,
      Subject="[PredictiveOps] Early outage signal",
      Message=json.dumps({"latency":latency,"errors":errors,"risk":risk}))
md
