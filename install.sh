#!/bin/bash

echo "🤖 Installing Cecilia Discord Bot with Subscription Service..."

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

# Copy configuration files
echo "📄 Setting up configuration files..."
# cp bot/config-sample.py bot/config.py
# cp bot/auths-sample.py bot/auths.py

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/essay_summarizer
mkdir -p data/essay_summarizer/processed
mkdir -p data/essay_summarizer/summaries

# Initialize email targets file
echo "📧 Initializing email targets..."
# echo '{}' > data/essay_summarizer/email_targets.json

# Set up Vue frontend
echo "🌐 Setting up Vue frontend..."
cd ui

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js (v16 or later) from https://nodejs.org/"
    echo "   After installing Node.js, run this script again."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install npm."
    exit 1
fi

echo "📦 Installing Vue frontend dependencies..."
npm install

# Build frontend for production
echo "🏗️  Building Vue frontend..."
npm run build

# Return to project root
cd ..

echo "✅ Installation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit bot/auths.py with your Discord bot credentials and email settings"
echo "2. Edit bot/config.py with your preferred settings"
echo "3. Add email addresses to data/essay_summarizer/email_targets.json"
echo "4. Run './deploy.sh' to start all services"
echo ""
echo "🌐 Frontend will be available at:"
echo "   - Development: http://localhost:8075 (npm run dev)"
echo "   - Production: Serve ui/dist/ via nginx at https://subscription.dywsy21.cn:18080"
echo ""
echo "🔧 Services:"
echo "   - Discord Bot: Webhook mode on port 8010"
echo "   - Message Pusher: Internal API on port 8011"
echo "   - Subscription Service: API on port 8012"
echo "   - Essay Scheduler: Background service"
