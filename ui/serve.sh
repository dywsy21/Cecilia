#!/bin/bash

# Development server for Cecilia Vue frontend
echo "🌐 Starting Cecilia Vue frontend development server..."

# Ensure we're in the ui directory
cd "$(dirname "$0")" || exit 1

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start development server
echo "🚀 Starting Vite development server on http://localhost:8075"
echo "🔗 API proxy configured for backend on port 8012"
echo ""
echo "⚠️  Make sure Cecilia backend is running (./deploy.sh) for full functionality"
echo "⚠️  Press Ctrl+C to stop the development server"
echo ""

npm run dev
