import asyncio
import logging
from .essay_summarizer.essay_summarizer import EssaySummarizer
from .msg_pusher.msg_pusher import create_message_pusher

logger = logging.getLogger(__name__)

class AppManager:
    """Manages all bot applications and their functionalities"""
    
    def __init__(self, bot_instance=None):
        self.essay_summarizer = EssaySummarizer()
        self.msg_pusher = None
        self.interaction_server = None
        self.bot_instance = bot_instance
        logger.info("AppManager initialized")
    
    def initialize_msg_pusher(self, bot_instance):
        """Initialize message pusher with bot instance"""
        self.bot_instance = bot_instance
        self.msg_pusher = create_message_pusher(bot_instance)
        logger.info("MessagePusher initialized in AppManager")
    
    def initialize_interaction_server(self):
        """Initialize interaction server"""
        from bot.interactions import create_interaction_server
        self.interaction_server = create_interaction_server(self)
        logger.info("InteractionServer initialized in AppManager")
    
    async def start_msg_pusher_server(self, port: int = 8011):
        """Start the message pusher HTTP server"""
        if self.msg_pusher:
            await self.msg_pusher.start_server(port)
        else:
            logger.error("MessagePusher not initialized")
    
    async def start_interaction_server(self, port: int = 8010):
        """Start the interaction HTTP server"""
        if self.interaction_server:
            await self.interaction_server.start_server(port)
        else:
            logger.error("InteractionServer not initialized")
    
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
            result = await self.essay_summarizer.summarize_topic(topic)
            return result
        except Exception as e:
            logger.error(f"Error in essay summarization: {e}")
            return f"Sorry, I couldn't summarize essays for '{topic}'. Error: {str(e)}"
    
    async def get_status(self) -> dict:
        """Get status of all apps"""
        return {
            "essay_summarizer": "online",
            "msg_pusher": "online" if self.msg_pusher else "not initialized",
            "interaction_server": "online" if self.interaction_server else "not initialized",
            "total_apps": 3
        }
