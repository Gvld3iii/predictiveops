# PredictiveOps – Architecture Overview

```mermaid
flowchart LR
    subgraph Observability
        CW[CloudWatch Metrics]
        DG[DevOps Guru]
        R53[Route53 Resolver Logs]
    end

    subgraph Eventing
        EB[EventBridge Rules]
    end

    subgraph Brain
        L[Lambda<br/>predictiveops-lambda]
    end

    subgraph Actions
        SSM[SSM Automation Runbooks]
        EC2[EC2 Instances]
        ECS[ECS Services]
    end

    subgraph Storage & Alerts
        DDB[(DynamoDB<br/>predictiveops_risk)]
        SNS[SNS Topic<br/>predictiveops-alerts]
        EMAIL[Email On-Call]
    end

    CW --> EB
    DG --> EB
    R53 --> EB
    EB --> L

    L --> DDB
    L --> SNS
    SNS --> EMAIL

    L -->|high risk & EC2 id| SSM
    L -->|high risk & ECS svc| SSM

    SSM --> EC2
    SSM --> ECS

