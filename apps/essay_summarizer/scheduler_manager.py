"""Scheduler management for daily summarization and notification tasks"""
import asyncio
import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger(__name__)

async def run_summarization_scheduler(
    summarization_hour: int, 
    summarization_minute: int, 
    summarization_callback
):
    """Start the daily summarization scheduler"""
    logger.info("Starting summarization scheduler")
    
    max_consecutive_errors = 5
    consecutive_errors = 0
    
    while True:
        try:
            now = datetime.now()
            target_time = now.replace(hour=summarization_hour, minute=summarization_minute, second=0, microsecond=0)
            
            # If it's past scheduled time today, schedule for tomorrow
            if now.time() > time(summarization_hour, summarization_minute):
                target_time = target_time + timedelta(days=1)
            
            # Calculate sleep time
            sleep_seconds = (target_time - now).total_seconds()
            logger.info(f"Next summarization run scheduled for: {target_time}")
            
            await asyncio.sleep(sleep_seconds)
            
            # Run the summarization phase
            logger.info("Starting daily summarization phase")
            await summarization_callback()
            logger.info("Daily summarization phase completed")
            
            # Reset error counter on successful run
            consecutive_errors = 0
            
        except asyncio.CancelledError:
            logger.info("Summarization scheduler cancelled")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in summarization scheduler (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Summarization scheduler failed {max_consecutive_errors} consecutive times, giving up")
                raise
            
            # Sleep for an hour before retrying
            await asyncio.sleep(3600)

async def run_notification_scheduler(
    notification_hour: int, 
    notification_minute: int, 
    notification_callback
):
    """Start the daily notification scheduler"""
    logger.info("Starting notification scheduler")
    
    max_consecutive_errors = 5
    consecutive_errors = 0
    
    while True:
        try:
            now = datetime.now()
            target_time = now.replace(hour=notification_hour, minute=notification_minute, second=0, microsecond=0)
            
            # If it's past scheduled time today, schedule for tomorrow
            if now.time() > time(notification_hour, notification_minute):
                target_time = target_time + timedelta(days=1)
            
            # Calculate sleep time
            sleep_seconds = (target_time - now).total_seconds()
            logger.info(f"Next notification run scheduled for: {target_time}")
            
            await asyncio.sleep(sleep_seconds)
            
            # Run the notification phase
            logger.info("Starting daily notification phase")
            await notification_callback()
            logger.info("Daily notification phase completed")
            
            # Reset error counter on successful run
            consecutive_errors = 0
            
        except asyncio.CancelledError:
            logger.info("Notification scheduler cancelled")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in notification scheduler (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Notification scheduler failed {max_consecutive_errors} consecutive times, giving up")
                raise
            
            # Sleep for an hour before retrying
            await asyncio.sleep(3600)

async def run_dual_scheduler(
    summarization_hour: int,
    summarization_minute: int,
    notification_hour: int,
    notification_minute: int,
    summarization_callback,
    notification_callback
):
    """Start both summarization and notification schedulers"""
    logger.info("Starting both summarization and notification schedulers")
    
    # Create tasks for both schedulers
    summarization_task = asyncio.create_task(
        run_summarization_scheduler(summarization_hour, summarization_minute, summarization_callback)
    )
    notification_task = asyncio.create_task(
        run_notification_scheduler(notification_hour, notification_minute, notification_callback)
    )
    
    try:
        # Run both schedulers concurrently
        await asyncio.gather(summarization_task, notification_task)
    except asyncio.CancelledError:
        logger.info("Both schedulers cancelled")
        summarization_task.cancel()
        notification_task.cancel()
    except Exception as e:
        logger.error(f"Error in main scheduler: {e}")
        summarization_task.cancel()
        notification_task.cancel()
        raise
