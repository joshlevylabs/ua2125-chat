#!/bin/bash
# UA2-125 AI Chatbot - AWS Deployment Script
# Usage: ./deploy.sh [environment] [region]

set -e

# Configuration
ENVIRONMENT=${1:-production}
REGION=${2:-us-west-2}
STACK_NAME="ua2125-chatbot-${ENVIRONMENT}"
ECR_REPO_NAME="ua2125-chatbot"

echo "=============================================="
echo "UA2-125 AI Chatbot - AWS Deployment"
echo "=============================================="
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack Name: ${STACK_NAME}"
echo "=============================================="

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: ${AWS_ACCOUNT_ID}"

# Step 1: Deploy CloudFormation Stack (if not exists)
echo ""
echo "Step 1: Deploying CloudFormation infrastructure..."

if aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} &> /dev/null; then
    echo "Stack exists, updating..."
    aws cloudformation update-stack \
        --stack-name ${STACK_NAME} \
        --template-body file://aws/cloudformation-template.yml \
        --parameters \
            ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
            ParameterKey=OpenAIApiKey,UsePreviousValue=true \
            ParameterKey=DatabasePassword,UsePreviousValue=true \
        --capabilities CAPABILITY_IAM \
        --region ${REGION} || echo "No updates to perform"
else
    echo "Creating new stack..."
    read -sp "Enter OpenAI API Key: " OPENAI_KEY
    echo ""
    read -sp "Enter Database Password: " DB_PASSWORD
    echo ""

    aws cloudformation create-stack \
        --stack-name ${STACK_NAME} \
        --template-body file://aws/cloudformation-template.yml \
        --parameters \
            ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
            ParameterKey=OpenAIApiKey,ParameterValue=${OPENAI_KEY} \
            ParameterKey=DatabasePassword,ParameterValue=${DB_PASSWORD} \
        --capabilities CAPABILITY_IAM \
        --region ${REGION}

    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME} --region ${REGION}
fi

# Step 2: Build and Push Docker Image
echo ""
echo "Step 2: Building and pushing Docker image..."

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Login to ECR
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Build image
docker build -t ${ECR_REPO_NAME}:latest .

# Tag image
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:$(git rev-parse --short HEAD 2>/dev/null || echo "manual")

# Push image
docker push ${ECR_URI}:latest
docker push ${ECR_URI}:$(git rev-parse --short HEAD 2>/dev/null || echo "manual")

echo "Image pushed: ${ECR_URI}:latest"

# Step 3: Get Stack Outputs
echo ""
echo "Step 3: Retrieving deployment information..."

ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[?OutputKey=='ALBDNSName'].OutputValue" \
    --output text \
    --region ${REGION})

RDS_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[?OutputKey=='RDSEndpoint'].OutputValue" \
    --output text \
    --region ${REGION})

echo ""
echo "=============================================="
echo "Deployment Complete!"
echo "=============================================="
echo ""
echo "Application URL: http://${ALB_DNS}"
echo "RDS Endpoint: ${RDS_ENDPOINT}"
echo ""
echo "Next Steps:"
echo "1. Run database migrations: psql -h ${RDS_ENDPOINT} -U postgres -d ua2125_chatbot -f backend/schema.sql"
echo "2. Run schema v2 migrations: psql -h ${RDS_ENDPOINT} -U postgres -d ua2125_chatbot -f backend/schema_v2.sql"
echo "3. Ingest knowledge base: python backend/ingest_docs.py"
echo "4. Configure HTTPS with ACM certificate"
echo "5. Update CORS_ORIGINS environment variable"
echo ""
echo "=============================================="
