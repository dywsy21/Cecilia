import asyncio
import logging
import signal
from apps.apps import AppManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point for Cecilia bot with all services"""
    logger.info("Starting Cecilia services...")
    
    # Create app manager
    app_manager = AppManager()
    
    # Initialize all services
    app_manager.initialize_interaction_server()
    
    try:
        # Create tasks for all services
        interaction_task = asyncio.create_task(app_manager.start_interaction_server(8010))
        pusher_task = asyncio.create_task(app_manager.start_msg_pusher_server(8011))
        
        logger.info("All services starting...")
        logger.info("- Interaction server on port 8010 (public via /bot)")
        logger.info("- Message pusher on port 8011 (internal localhost only)")
        
        # Wait for all tasks
        await asyncio.gather(interaction_task, pusher_task)
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        logger.info("Shutting down services...")

def handle_signal(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    raise KeyboardInterrupt()

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application shutdown complete")
        logger.info("Application shutdown complete")
