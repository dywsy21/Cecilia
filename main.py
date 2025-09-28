import asyncio
import logging
import signal
import sys
from bot.bot import CeciliaBot, DISCORD_TOKEN
from apps.apps import AppManager

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class CeciliaServiceError(Exception):
    """Custom exception for unrecoverable service errors"""
    pass

async def main():
    """Main entry point for Cecilia bot with all services"""
    logger.info("Starting Cecilia Discord Bot with all services...")
    
    try:
        # Create bot instance
        bot = CeciliaBot()
        
        # Initialize message pusher after bot is created
        bot.app_manager.initialize_msg_pusher(bot)
        
        # Create tasks for all services
        bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
        pusher_task = asyncio.create_task(bot.app_manager.start_msg_pusher_server(8011))
        interactions_task = asyncio.create_task(bot.start_interactions_server(8010))
        subscription_task = asyncio.create_task(bot.app_manager.start_subscription_service(8012))
        scheduler_task = asyncio.create_task(bot.app_manager.start_essay_scheduler())
        deep_research_task = asyncio.create_task(bot.app_manager.start_deep_research_wrapper())
        
        logger.info("Starting Discord bot, MessagePusher server, Interactions webhook, Subscription service, Essay scheduler, and Deep Research wrapper...")
        
        # Wait for all tasks
        await asyncio.gather(
            bot_task, 
            pusher_task, 
            interactions_task, 
            subscription_task,
            scheduler_task, 
            deep_research_task
        )
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        return 0  # Normal shutdown
    except ImportError as e:
        logger.error(f"Critical import error - missing dependencies: {e}")
        return 2  # Configuration/dependency error
    except FileNotFoundError as e:
        logger.error(f"Critical file missing - configuration error: {e}")
        return 3  # Configuration error
    except PermissionError as e:
        logger.error(f"Permission denied - service cannot access required resources: {e}")
        return 4  # Permission error
    except OSError as e:
        logger.error(f"System error - cannot bind to ports or access system resources: {e}")
        return 5  # System resource error
    except asyncio.CancelledError:
        logger.info("Service tasks cancelled during shutdown")
        return 0  # Normal shutdown
    except CeciliaServiceError as e:
        logger.error(f"Unrecoverable service error: {e}")
        return 10  # Custom service error
    except Exception as e:
        logger.error(f"Unexpected critical error: {e}", exc_info=True)
        return 1  # General error
    finally:
        try:
            logger.info("Shutting down services...")
            if 'bot' in locals():
                await bot.app_manager.shutdown()
                if not bot.is_closed():
                    await bot.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            return 6  # Shutdown error

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
        exit_code = asyncio.run(main())
        if exit_code != 0:
            logger.error(f"Service exiting with error code: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Application shutdown complete")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
