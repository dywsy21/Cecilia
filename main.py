import asyncio
import logging
import signal
from bot.bot import CeciliaBot
from apps.apps import AppManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point for Cecilia bot with concurrent services"""
    logger.info("Starting Cecilia Discord Bot with MessagePusher...")
    
    # Create bot instance
    bot = CeciliaBot()
    
    # Initialize message pusher after bot is created
    bot.app_manager.initialize_msg_pusher(bot)
    
    try:
        # Create tasks for both services
        bot_task = asyncio.create_task(bot.start(bot.token))
        pusher_task = asyncio.create_task(bot.app_manager.start_msg_pusher_server(8011))
        
        logger.info("Both Discord bot and MessagePusher server starting...")
        
        # Wait for both tasks
        await asyncio.gather(bot_task, pusher_task)
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        logger.info("Shutting down services...")
        if not bot.is_closed():
            await bot.close()

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
