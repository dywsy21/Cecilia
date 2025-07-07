import asyncio
import logging
from .essay_summarizer.essay_summarizer import EssaySummarizer
from .msg_pusher.msg_pusher import create_message_pusher

logger = logging.getLogger(__name__)

class CeciliaServiceError(Exception):
    """Custom exception for unrecoverable service errors"""
    pass

class AppManager:
    """Manages all bot applications and their functionalities"""
    
    def __init__(self, bot_instance=None):
        try:
            self.essay_summarizer = EssaySummarizer()
            self.msg_pusher = None
            self.bot_instance = bot_instance
            self.scheduler_task = None
            logger.info("AppManager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AppManager: {e}")
            raise CeciliaServiceError(f"Cannot initialize AppManager: {e}")
    
    def initialize_msg_pusher(self, bot_instance):
        """Initialize message pusher with bot instance"""
        try:
            self.bot_instance = bot_instance
            self.msg_pusher = create_message_pusher(bot_instance)
            # Set app manager reference in essay summarizer for message pushing
            self.essay_summarizer.set_app_manager(self)
            logger.info("MessagePusher initialized in AppManager")
        except Exception as e:
            logger.error(f"Failed to initialize MessagePusher: {e}")
            raise CeciliaServiceError(f"Cannot initialize MessagePusher: {e}")
    
    async def start_msg_pusher_server(self, port: int = 8011):
        """Start the message pusher HTTP server"""
        if not self.msg_pusher:
            logger.error("MessagePusher not initialized")
            raise CeciliaServiceError("MessagePusher not initialized")
        
        try:
            await self.msg_pusher.start_server(port)
        except Exception as e:
            logger.error(f"Failed to start MessagePusher server: {e}")
            raise CeciliaServiceError(f"Cannot start MessagePusher server: {e}")
    
    async def start_essay_scheduler(self):
        """Start the essay subscription scheduler"""
        try:
            if not self.scheduler_task or self.scheduler_task.done():
                self.scheduler_task = asyncio.create_task(self.essay_summarizer.start_scheduler())
                logger.info("Essay subscription scheduler started")
        except Exception as e:
            logger.error(f"Failed to start essay scheduler: {e}")
            raise CeciliaServiceError(f"Cannot start essay scheduler: {e}")
    
    async def summarize_essays(self, topic: str) -> str:
        """
        Summarize essays on ArXiv about a specific topic
        
        Args:
            topic (str): The research topic to search for
            
        Returns:
            str: Formatted summary of relevant essays
        """
        try:
            logger.info(f"Starting essay summarization for topic: {topic}")
            result = await self.essay_summarizer.summarize_and_push(topic)
            
            if result['success']:
                return f"✅ {result['message']}"
            else:
                return f"❌ {result['error']}"
                
        except Exception as e:
            logger.error(f"Error in essay summarization: {e}")
            return f"Sorry, I couldn't summarize essays for '{topic}'. Error: {str(e)}"
    
    async def get_status(self) -> dict:
        """Get status of all apps"""
        return {
            "essay_summarizer": "online",
            "msg_pusher": "online" if self.msg_pusher else "not initialized",
            "scheduler": "running" if self.scheduler_task and not self.scheduler_task.done() else "stopped",
            "total_apps": 2
        }
    
    async def shutdown(self):
        """Gracefully shutdown all services"""
        try:
            if self.scheduler_task and not self.scheduler_task.done():
                self.scheduler_task.cancel()
                try:
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass
                logger.info("Essay scheduler stopped")
        except Exception as e:
            logger.error(f"Error shutting down services: {e}")
