import os, json, datetime, time, re
from decimal import Decimal
import boto3

# --- AWS clients ---
ddb = boto3.resource("dynamodb")
sns = boto3.client("sns")
ssm = boto3.client("ssm")

# --- Env ---
RISK_TABLE          = os.getenv("RISK_TABLE", "predictiveops_risk")
SNS_TOPIC_ARN       = os.getenv("SNS_TOPIC_ARN")
RISK_THRESHOLD      = Decimal(str(os.getenv("RISK_THRESHOLD", "0.75")))
RUNBOOK_EC2         = os.getenv("RUNBOOK_EC2", "PredictiveOps-RestartEC2")
RUNBOOK_ECS         = os.getenv("RUNBOOK_ECS", "PredictiveOps-RedeployECSService")
AUTOMATION_ROLE_ARN = os.getenv("AUTOMATION_ROLE_ARN")
COOLDOWN_SECONDS    = int(os.getenv("COOLDOWN_SECONDS", "0"))

table = ddb.Table(RISK_TABLE)

EC2_ID_RE  = re.compile(r"^i-[0-9a-fA-F]+$")
# Accept: ecs-service/<cluster name or cluster ARN>/<service name or service ARN>
ECS_RES_RE = re.compile(
    r"^ecs-service/(?P<cluster>[^/]+|arn:aws:ecs:[^:]+:\d+:cluster/.+)/(?P<service>[^/]+|arn:aws:ecs:[^:]+:\d+:service/.+)$"
)

def D(x):
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))

def compute_risk(latency_ms=None, error_rate_pct=None, nxdomain_anomaly=False):
    r = Decimal("0")
    if latency_ms is not None and float(latency_ms) >= 200:
        r += Decimal("0.45")
    if error_rate_pct is not None and float(error_rate_pct) >= 1.0:
        r += Decimal("0.45")
    if nxdomain_anomaly:
        r += Decimal("0.15")
    return min(r, Decimal("1.0"))

def cooldown_ok(key: str) -> bool:
    if COOLDOWN_SECONDS <= 0:
        return True
    try:
        item = table.get_item(Key={"id": f"cooldown::{key}"}).get("Item")
        now = time.time()
        if item and float(item.get("cooldown_until", 0)) > now:
            print(f"[Cooldown] active for {key}")
            return False
        return True
    except Exception as e:
        print(f"[Cooldown] check failed: {e}")
        return True

def set_cooldown(key: str):
    if COOLDOWN_SECONDS <= 0:
        return
    try:
        until = time.time() + COOLDOWN_SECONDS
        table.put_item(Item={
            "id": f"cooldown::{key}",
            "cooldown_until": D(until),
            "ts": datetime.datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"[Cooldown] set failed: {e}")

def start_automation(document_name: str, params: dict) -> str:
    """
    Thin wrapper around SSM Automation.
    Key fix: do NOT pass TargetParameterName when you don't need it.
    """
    if not AUTOMATION_ROLE_ARN:
        raise RuntimeError("AUTOMATION_ROLE_ARN not set")
    resp = ssm.start_automation_execution(
        DocumentName=document_name,
        Parameters=params
    )
    return resp["AutomationExecutionId"]

def start_ec2_restart(instance_id: str) -> str:
    return start_automation(RUNBOOK_EC2, {
        "InstanceId": [instance_id],
        "AutomationAssumeRole": [AUTOMATION_ROLE_ARN]
    })

def start_ecs_redeploy(cluster: str, service: str) -> str:
    # Accept name or ARN; the SSM doc resolves either to ARNs internally
    return start_automation(RUNBOOK_ECS, {
        "Cluster": [cluster],
        "Service": [service],
        "AutomationAssumeRole": [AUTOMATION_ROLE_ARN]
    })

def handler(event, context):
    records = event if isinstance(event, list) else [event]
    results = []

    for rec in records:
        detail = rec.get("detail", {}) or {}
        latency_ms = detail.get("latency", 0)
        error_rate = detail.get("errorRate", 0)
        nxdomain   = bool(detail.get("nxdomainAnomaly", False))
        resource   = detail.get("resourceId", detail.get("resourceName", "unknown"))

        risk = compute_risk(latency_ms, error_rate, nxdomain)

        # Persist
        item = {
            "id": f"{resource}-{datetime.datetime.utcnow().isoformat()}",
            "resource": resource,
            "latency_ms": D(latency_ms),
            "error_rate_pct": D(error_rate),
            "nxdomain_anomaly": nxdomain,
            "risk": D(risk),
            "ts": datetime.datetime.utcnow().isoformat()
        }
        table.put_item(Item=item)

        # Optional alert
        if SNS_TOPIC_ARN and risk >= RISK_THRESHOLD:
            try:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject="[PredictiveOps] Early outage signal",
                    Message=json.dumps({
                        **item,
                        "latency_ms": float(item["latency_ms"]),
                        "error_rate_pct": float(item["error_rate_pct"]),
                        "risk": float(item["risk"])
                    })
                )
            except Exception as e:
                print(f"[SNS] publish failed: {e}")

        auto_heal_started = False
        automation_id = None

        # Auto-heal paths
        if risk >= RISK_THRESHOLD and cooldown_ok(resource):
            try:
                # EC2 path
                if EC2_ID_RE.match(resource):
                    automation_id = start_ec2_restart(resource)
                    auto_heal_started = True
                    set_cooldown(resource)
                else:
                    # ECS path: ecs-service/<cluster or arn>/<service or arn>
                    m = ECS_RES_RE.match(resource)
                    if m:
                        cluster = m.group("cluster")
                        service = m.group("service")
                        automation_id = start_ecs_redeploy(cluster, service)
                        auto_heal_started = True
                        set_cooldown(resource)
            except Exception as e:
                print(f"[AutoHeal] failed for {resource}: {e}")

        results.append({
            "resource": resource,
            "risk": float(risk),
            "auto_heal_started": auto_heal_started,
            "automation_id": automation_id
        })

    return {"ok": True, "results": results}


