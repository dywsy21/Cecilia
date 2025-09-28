#!/bin/bash

# Deploy script for Cecilia bot with all services including Vue frontend
echo "🚀 Deploying Cecilia Discord Bot with Subscription Service and Vue Frontend..."

# Ensure the script is run from the project root
cd "$(dirname "$0")" || exit 1

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run './install.sh' first."
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating Python environment..."
source venv/bin/activate

# Check if configuration files exist
if [ ! -f "bot/auths.py" ]; then
    echo "❌ bot/auths.py not found. Please run './install.sh' first and configure your credentials."
    exit 1
fi

if [ ! -f "bot/config.py" ]; then
    echo "❌ bot/config.py not found. Please run './install.sh' first."
    exit 1
fi

# Check if Node.js is installed for frontend
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js to run the Vue frontend."
    echo "   Frontend will be skipped, but backend services will start."
    FRONTEND_AVAILABLE=false
else
    FRONTEND_AVAILABLE=true
fi

# Check if frontend dependencies are installed
if [ "$FRONTEND_AVAILABLE" = true ]; then
    if [ ! -d "ui/node_modules" ]; then
        echo "📦 Installing Vue frontend dependencies..."
        cd ui
        npm install
        cd ..
    fi
fi

# Display service information
echo ""
echo "🔧 Starting Cecilia services:"
echo "   📡 Discord Bot (Webhook): Port 8010"
echo "   💬 Message Pusher: Port 8011 (internal)"
echo "   📧 Subscription Service: Port 8012"
echo "   📚 Essay Scheduler: Background"
echo "   🔬 Deep Research: Background"

if [ "$FRONTEND_AVAILABLE" = true ]; then
    echo "   🌐 Vue Frontend: Port 8075 (development server)"
else
    echo "   ❌ Vue Frontend: Disabled (Node.js not available)"
fi

echo ""
echo "🌐 Access URLs:"
echo "   • Discord Bot API: http://localhost:8010/health"
echo "   • Message Pusher API: http://localhost:8011/health"
echo "   • Subscription API: http://localhost:8012/api/subscription/create"
if [ "$FRONTEND_AVAILABLE" = true ]; then
    echo "   • Vue Frontend: http://localhost:8075"
fi
echo ""
echo "⚠️  Press Ctrl+C to stop all services"
echo ""

# PIDs for process management
BACKEND_PID=""
FRONTEND_PID=""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down Cecilia services..."
    
    # Kill backend process
    if [ ! -z "$BACKEND_PID" ]; then
        echo "   Stopping backend services (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
        wait $BACKEND_PID 2>/dev/null
    fi
    
    # Kill frontend process
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "   Stopping Vue frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
        wait $FRONTEND_PID 2>/dev/null
    fi
    
    # Kill any remaining background processes
    jobs -p | xargs -r kill 2>/dev/null
    
    echo "✅ Shutdown complete"
    exit 0
}

# Set up signal handling
trap cleanup INT TERM

# Start backend services in background
echo "🤖 Starting Cecilia backend services..."
python3 main.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend development server if available
if [ "$FRONTEND_AVAILABLE" = true ]; then
    echo "🌐 Starting Vue frontend development server..."
    cd ui
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    
    echo ""
    echo "✅ All services started successfully!"
    echo ""
    echo "📊 Service Status:"
    echo "   Backend Services: Running (PID: $BACKEND_PID)"
    echo "   Vue Frontend: Running (PID: $FRONTEND_PID)"
    echo ""
    echo "🌐 You can now access:"
    echo "   • Subscription Frontend: http://localhost:8075"
    echo "   • Discord Bot Health: http://localhost:8010/health"
    echo ""
else
    echo ""
    echo "✅ Backend services started successfully!"
    echo ""
    echo "📊 Service Status:"
    echo "   Backend Services: Running (PID: $BACKEND_PID)"
    echo "   Vue Frontend: Disabled"
    echo ""
fi

echo "📝 Logs:"
echo "   Backend: Check terminal output above"
if [ "$FRONTEND_AVAILABLE" = true ]; then
    echo "   Frontend: Vite dev server logs will appear below"
fi
echo ""
echo "⌨️  Press Ctrl+C to stop all services"

# Wait for both processes
if [ "$FRONTEND_AVAILABLE" = true ]; then
    # Wait for either process to exit
    while kill -0 $BACKEND_PID 2>/dev/null && kill -0 $FRONTEND_PID 2>/dev/null; do
        sleep 1
    done
    
    # Check which process exited
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ Backend services stopped unexpectedly"
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID 2>/dev/null
        fi
    elif ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "❌ Frontend development server stopped unexpectedly"
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID 2>/dev/null
        fi
    fi
else
    # Wait for backend process only
    wait $BACKEND_PID
fi

echo "🔄 Services stopped"
