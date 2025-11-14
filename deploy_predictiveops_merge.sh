#!/usr/bin/env bash
set -euo pipefail
REGION="${REGION:-us-east-1}"
PROJECT="${PROJECT:-predictiveops}"
FUNCTION_NAME="${FUNCTION_NAME:-predictiveops-lambda}"
TABLE_NAME="${TABLE_NAME:-predictiveops_risk}"
SNS_TOPIC_NAME="${SNS_TOPIC_NAME:-predictiveops-alerts}"
RULE_NAME="${RULE_NAME:-PredictiveOpsAnomalyRule}"
ZIP_PATH="${ZIP_PATH:-lambda/predictive_ops_handler.zip}"
HANDLER="${HANDLER:-predictive_ops_handler.handler}"
RISK_THRESHOLD="${RISK_THRESHOLD:-0.75}"

echo "Region: $REGION"

# Package Lambda if not zipped
if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Packaging Lambda..."
  (cd lambda && zip -r predictive_ops_handler.zip predictive_ops_handler.py >/dev/null)
fi

# DynamoDB
if ! aws dynamodb describe-table --region "$REGION" --table-name "$TABLE_NAME" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --region "$REGION" \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --region "$REGION" --table-name "$TABLE_NAME"
fi

# SNS
SNS_TOPIC_ARN=$(aws sns list-topics --region "$REGION" --query "Topics[?contains(TopicArn, \`:${SNS_TOPIC_NAME}\`)].TopicArn" --output text)
if [[ -z "$SNS_TOPIC_ARN" || "$SNS_TOPIC_ARN" == "None" ]]; then
  SNS_TOPIC_ARN=$(aws sns create-topic --region "$REGION" --name "$SNS_TOPIC_NAME" --query 'TopicArn' --output text)
fi

# IAM Role
ROLE_NAME="${PROJECT}-lambda-role"
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  cat > /tmp/trust-policy.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole" }] }
EOF
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document file:///tmp/trust-policy.json >/dev/null
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/AmazonSSMFullAccess
fi
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

# Lambda create/update
if aws lambda get-function --region "$REGION" --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  echo "Updating Lambda code..."
  aws lambda update-function-code --region "$REGION" --function-name "$FUNCTION_NAME" --zip-file "fileb://$ZIP_PATH" >/dev/null
  aws lambda update-function-configuration \
    --region "$REGION" --function-name "$FUNCTION_NAME" \
    --role "$ROLE_ARN" --handler "$HANDLER" --runtime python3.12 \
    --environment "Variables={RISK_TABLE=$TABLE_NAME,SNS_TOPIC_ARN=$SNS_TOPIC_ARN,RISK_THRESHOLD=$RISK_THRESHOLD}" >/dev/null
else
  echo "Creating Lambda..."
  aws lambda create-function \
    --region "$REGION" --function-name "$FUNCTION_NAME" --runtime python3.12 \
    --role "$ROLE_ARN" --handler "$HANDLER" \
    --zip-file "fileb://$ZIP_PATH" \
    --environment "Variables={RISK_TABLE=$TABLE_NAME,SNS_TOPIC_ARN=$SNS_TOPIC_ARN,RISK_THRESHOLD=$RISK_THRESHOLD}" >/dev/null
fi

LAMBDA_ARN=$(aws lambda get-function --region "$REGION" --function-name "$FUNCTION_NAME" --query 'Configuration.FunctionArn' --output text)

# EventBridge
if ! aws events describe-rule --region "$REGION" --name "$RULE_NAME" >/dev/null 2>&1; then
  aws events put-rule --region "$REGION" --name "$RULE_NAME" --event-pattern '{"source":["aws.devops-guru"]}' >/dev/null
fi
HAS_TARGET=$(aws events list-targets-by-rule --region "$REGION" --rule "$RULE_NAME" --query "Targets[?Arn=='$LAMBDA_ARN'] | length(@)" --output text)
if [[ "$HAS_TARGET" == "0" ]]; then
  aws events put-targets --region "$REGION" --rule "$RULE_NAME" --targets "Id"="1","Arn"="$LAMBDA_ARN" >/dev/null
  RULE_ARN=$(aws events describe-rule --region "$REGION" --name "$RULE_NAME" --query 'Arn' --output text)
  aws lambda add-permission \
    --region "$REGION" --function-name "$FUNCTION_NAME" \
    --statement-id "${PROJECT}-AllowEvents" --action 'lambda:InvokeFunction' \
    --principal events.amazonaws.com --source-arn "$RULE_ARN" >/dev/null || true
fi

echo "✅ Deploy complete for $FUNCTION_NAME in $REGION"

