#!/bin/bash
# =============================================================================
# UA2-125 AI Chatbot - EC2 Deployment Script
# Run this script on your EC2 instance to set up the chatbot
# =============================================================================

set -e  # Exit on any error

echo "=============================================="
echo "  UA2-125 AI Chatbot Deployment Script"
echo "=============================================="

# Variables
APP_DIR="/home/ubuntu/ua2125-chat"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/ua2125-chatbot"
REPO_URL="https://github.com/joshlevylabs/ua2125-chat.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[x]${NC} $1"
}

# Check if running as ubuntu user or root
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root. Some commands will use 'sudo -u ubuntu'"
fi

# Step 1: Install system dependencies
print_status "Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git

# Step 2: Create log directory
print_status "Creating log directory..."
sudo mkdir -p $LOG_DIR
sudo chown ubuntu:ubuntu $LOG_DIR

# Step 3: Clone or update repository
if [ -d "$APP_DIR" ]; then
    print_status "Updating existing installation..."
    cd $APP_DIR
    git fetch origin
    git reset --hard origin/main
else
    print_status "Cloning repository..."
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
fi

# Step 4: Create/update virtual environment
if [ ! -d "$VENV_DIR" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Step 5: Install Python dependencies
print_status "Installing Python dependencies..."
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install -r backend/requirements.txt

# Step 6: Check for .env file
if [ ! -f "$APP_DIR/.env" ]; then
    print_warning ".env file not found!"
    echo ""
    echo "Please create $APP_DIR/.env with the following contents:"
    echo "=============================================="
    echo "# OpenAI"
    echo "OPENAI_API_KEY=sk-proj-your-key-here"
    echo ""
    echo "# Database (existing RDS)"
    echo "DB_HOST=sonance-beta-testing-1.c3av0xn7zvgg.us-west-1.rds.amazonaws.com"
    echo "DB_PORT=5432"
    echo "DB_NAME=postgres"
    echo "DB_USER=sonance_admin"
    echo "DB_PASSWORD=your-db-password"
    echo "DB_SSL=true"
    echo ""
    echo "# Server"
    echo "HOST=127.0.0.1"
    echo "PORT=8000"
    echo ""
    echo "# CORS"
    echo "CORS_ORIGINS=https://sonance-beta.info,https://www.sonance-beta.info,https://sonancebeta.vercel.app"
    echo ""
    echo "# Logging"
    echo "LOG_LEVEL=INFO"
    echo "=============================================="
    echo ""
    print_error "Create .env file and run this script again."
    exit 1
fi

# Step 7: Set up systemd service
print_status "Setting up systemd service..."
sudo cp deploy/ua2125-chatbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ua2125-chatbot

# Step 8: Set up nginx (before SSL)
print_status "Setting up nginx..."

# Create a temporary config without SSL first (for certbot)
cat > /tmp/nginx-ua2125-api-temp.conf << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name ua2125-api.sonance-beta.info;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
EOF

sudo cp /tmp/nginx-ua2125-api-temp.conf /etc/nginx/sites-available/ua2125-api
sudo ln -sf /etc/nginx/sites-available/ua2125-api /etc/nginx/sites-enabled/

# Test nginx config
if sudo nginx -t; then
    sudo systemctl reload nginx
    print_status "Nginx configured successfully"
else
    print_error "Nginx configuration test failed!"
    exit 1
fi

# Step 9: Start the chatbot service
print_status "Starting chatbot service..."
sudo systemctl restart ua2125-chatbot

# Wait for service to start
sleep 3

# Step 10: Verify service is running
if sudo systemctl is-active --quiet ua2125-chatbot; then
    print_status "Chatbot service is running!"
else
    print_error "Chatbot service failed to start. Check logs:"
    echo "  sudo journalctl -u ua2125-chatbot -n 50"
    exit 1
fi

# Step 11: Test the API
print_status "Testing API health endpoint..."
sleep 2
if curl -s http://127.0.0.1:8000/health | grep -q "healthy"; then
    print_status "API is responding!"
else
    print_warning "API health check failed. Service may still be starting..."
fi

echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure DNS:"
echo "   Add an A record: ua2125-api.sonance-beta.info -> $(curl -s ifconfig.me)"
echo ""
echo "2. After DNS propagates, set up SSL:"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d ua2125-api.sonance-beta.info"
echo ""
echo "3. After SSL is set up, update nginx config:"
echo "   sudo cp $APP_DIR/deploy/nginx-ua2125-api.conf /etc/nginx/sites-available/ua2125-api"
echo "   sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "Useful commands:"
echo "  Check service status: sudo systemctl status ua2125-chatbot"
echo "  View logs: sudo journalctl -u ua2125-chatbot -f"
echo "  Restart service: sudo systemctl restart ua2125-chatbot"
echo "  Test API: curl http://127.0.0.1:8000/health"
echo ""
