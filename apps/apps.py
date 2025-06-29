import asyncio
import logging
from .essay_summarizer.essay_summarizer import EssaySummarizer

logger = logging.getLogger(__name__)

class AppManager:
    """Manages all bot applications and their functionalities"""
    
    def __init__(self):
        self.essay_summarizer = EssaySummarizer()
        logger.info("AppManager initialized")
    
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
            "total_apps": 1
        }
