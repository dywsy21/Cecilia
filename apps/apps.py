import asyncio
import logging
from .essay_summarizer.essay_summarizer import EssaySummarizer
from .msg_pusher.msg_pusher import create_message_pusher
from .ollama_monitor.ollama_monitor import OllamaMonitor
from apps.deep_research_wrapper.deep_research_wrapper import DeepResearchWrapper, run_deep_research_wrapper_server
from bot.config import (
    DEEP_RESEARCH_INNER_PORT, DEEP_RESEARCH_OUTER_PORT, 
    DEEP_RESEARCH_CHANNEL, DEEP_RESEARCH_LANGUAGE,
    DEEP_RESEARCH_MAX_RESULTS
)

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
            self.ollama_monitor = OllamaMonitor()
            self.deep_research_wrapper = None
            self.deep_research_task = None
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
            # Initialize deep research wrapper
            self.initialize_deep_research_wrapper()
            logger.info("MessagePusher initialized in AppManager")
        except Exception as e:
            logger.error(f"Failed to initialize MessagePusher: {e}")
            raise CeciliaServiceError(f"Cannot initialize MessagePusher: {e}")
    
    def initialize_deep_research_wrapper(self):
        """Initialize deep research wrapper"""
        try:
            self.deep_research_wrapper = DeepResearchWrapper(
                inner_port=DEEP_RESEARCH_INNER_PORT,
                discord_channel_id=str(DEEP_RESEARCH_CHANNEL),
                bot_instance=self.bot_instance
            )
            logger.info("Deep Research Wrapper initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Deep Research Wrapper: {e}")
            raise CeciliaServiceError(f"Cannot initialize Deep Research Wrapper: {e}")
    
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
    
    async def start_deep_research_wrapper(self):
        """Start the deep research wrapper server"""
        if not self.deep_research_wrapper:
            logger.error("Deep Research Wrapper not initialized")
            raise CeciliaServiceError("Deep Research Wrapper not initialized")
        
        try:
            if not self.deep_research_task or self.deep_research_task.done():
                self.deep_research_task = asyncio.create_task(
                    run_deep_research_wrapper_server(
                        DEEP_RESEARCH_OUTER_PORT,
                        DEEP_RESEARCH_INNER_PORT, 
                        str(DEEP_RESEARCH_CHANNEL),
                        self.bot_instance
                    )
                )
                logger.info("Deep Research Wrapper server started")
        except Exception as e:
            logger.error(f"Failed to start Deep Research Wrapper server: {e}")
            raise CeciliaServiceError(f"Cannot start Deep Research Wrapper server: {e}")
    
    async def trigger_deep_research(self, topic: str, **kwargs) -> dict:
        """Trigger a deep research session"""
        try:
            if not self.deep_research_wrapper:
                return {"success": False, "error": "Deep Research Wrapper not initialized"}
            
            # Prepare arguments with default values
            arguments = {
                "query": topic,
                "provider": kwargs.get("provider", "google"),
                "thinking_model": kwargs.get("thinking_model", "gemini-2.0-flash-thinking-exp"),
                "task_model": kwargs.get("task_model", "gemini-2.0-flash-exp"),
                "search_provider": kwargs.get("search_provider", "tavily"),
                "language": kwargs.get("language", DEEP_RESEARCH_LANGUAGE),
                "max_result": kwargs.get("max_result", DEEP_RESEARCH_MAX_RESULTS)
            }
            
            # Execute deep research
            result = await self.deep_research_wrapper.handle_deep_research(arguments)
            
            if result and len(result) > 0:
                return {"success": True, "message": result[0].text}
            else:
                return {"success": False, "error": "No result returned from deep research"}
                
        except Exception as e:
            logger.error(f"Error triggering deep research: {e}")
            return {"success": False, "error": str(e)}
    
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
        """Get status of all apps including Ollama and Deep Research"""
        try:
            # Get Ollama status
            async with self.ollama_monitor as monitor:
                ollama_status = await monitor.check_ollama_status()
            
            status = {
                "essay_summarizer": "online",
                "msg_pusher": "online" if self.msg_pusher else "not initialized",
                "scheduler": "running" if self.scheduler_task and not self.scheduler_task.done() else "stopped",
                "ollama": ollama_status.get('status', 'unknown'),
                "ollama_models": ollama_status.get('models_count', 0),
                "deep_research": "running" if self.deep_research_task and not self.deep_research_task.done() else "stopped",
                "total_apps": 4  # Updated to include Deep Research
            }
            return status
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                "essay_summarizer": "online",
                "msg_pusher": "online" if self.msg_pusher else "not initialized",
                "scheduler": "running" if self.scheduler_task and not self.scheduler_task.done() else "stopped",
                "ollama": "error",
                "ollama_models": 0,
                "deep_research": "error",
                "total_apps": 4
            }
    
    async def get_ollama_resources(self) -> dict:
        """Get Ollama system resources and usage"""
        try:
            async with self.ollama_monitor as monitor:
                resources = await monitor.get_full_status()
            return resources
        except Exception as e:
            logger.error(f"Error getting Ollama resources: {e}")
            return {
                "ollama": {"status": "error"},
                "system": {
                    "cpu_percent": 0.0,
                    "memory": {"percent": 0.0},
                    "gpu": {"available": False, "gpus": []}
                },
                "ollama_processes": {"processes_found": 0, "total_cpu": 0.0, "total_memory_mb": 0.0}
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
                
            if self.deep_research_task and not self.deep_research_task.done():
                self.deep_research_task.cancel()
                try:
                    await self.deep_research_task
                except asyncio.CancelledError:
                    pass
                logger.info("Deep Research Wrapper stopped")
        except Exception as e:
            logger.error(f"Error shutting down services: {e}")
                
            if self.deep_research_task and not self.deep_research_task.done():
                self.deep_research_task.cancel()
                try:
                    await self.deep_research_task
                except asyncio.CancelledError:
                    pass
                logger.info("Deep Research Wrapper stopped")
        except Exception as e:
            logger.error(f"Error shutting down services: {e}")
