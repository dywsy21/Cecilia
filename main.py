import asyncio
import logging
import signal
from bot.bot import CeciliaBot, DISCORD_TOKEN
from apps.apps import AppManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point for Cecilia bot with concurrent services"""
    logger.info("Starting Cecilia Discord Bot with all services...")
    
    # Create bot instance
    bot = CeciliaBot()
    
    # Initialize message pusher after bot is created
    bot.app_manager.initialize_msg_pusher(bot)
    
    try:
        # Create tasks for all services
        bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
        pusher_task = asyncio.create_task(bot.app_manager.start_msg_pusher_server(8011))
        interactions_task = asyncio.create_task(bot.start_interactions_server(8010))
        
        logger.info("Starting Discord bot, MessagePusher server, and Interactions webhook...")
        
        # Wait for all tasks
        await asyncio.gather(bot_task, pusher_task, interactions_task)
        
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
