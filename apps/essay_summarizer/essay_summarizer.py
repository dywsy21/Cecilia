import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from bot.config import (
    SUBSCRIPTION_ONLY_NEW, 
    SUMMARIZATION_SCHEDULE_HOUR, 
    SUMMARIZATION_SCHEDULE_MINUTE,
    NOTIFICATION_SCHEDULE_HOUR,
    NOTIFICATION_SCHEDULE_MINUTE
)
from ..email_service.email_service import EmailService
from ..llm_handler.llm_handler import LLMHandler

# Import the new modules
from . import arxiv_client
from . import pdf_processor
from . import data_manager
from . import notification_sender
from . import scheduler_manager

logger = logging.getLogger(__name__)

class EssaySummarizer:
    """Handles essay summarization from ArXiv with subscription management"""
    
    def __init__(self):
        try:
            # Initialize directory structure
            self.base_dir = Path("data/essay_summarizer")
            self.processed_papers_dir = self.base_dir / "processed"
            self.summaries_dir = self.base_dir / "summaries"
            self.subscriptions_file = self.base_dir / "subscriptions.json"
            self.email_targets_file = self.base_dir / "email_targets.json"
            
            # Create directories if they don't exist
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.processed_papers_dir.mkdir(parents=True, exist_ok=True)
            self.summaries_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize LLM handler and email service
            self.llm_handler = LLMHandler()
            self.email_service = EmailService()
            
            # App manager reference (set by app manager)
            self.app_manager = None
            
            # Arxiv searching api base url
            self.arxiv_base_url = "https://export.arxiv.org/api/query"
            
            logger.info("EssaySummarizer initialized successfully")
            
        except PermissionError as e:
            logger.error(f"Permission denied when creating directories: {e}")
            raise
        except OSError as e:
            logger.error(f"OS error when initializing essay summarizer: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing essay summarizer: {e}")
            raise

    def set_app_manager(self, app_manager):
        """Set reference to AppManager for message pushing"""
        self.app_manager = app_manager
    
    async def search_arxiv(self, category: str, topic: str, max_results: int = 10) -> List[Dict]:
        """Search for papers on a specific category and topic with retry logic"""
        return await arxiv_client.search_arxiv(category, topic, max_results)
    
    def _load_email_targets(self) -> Dict[str, List[str]]:
        """Load email targets from disk with new format: {email: [categories]}"""
        return data_manager.load_email_targets(self.email_targets_file)

    def _save_email_targets(self, email_targets: Dict[str, List[str]]):
        """Save email targets to disk"""
        data_manager.save_email_targets(email_targets, self.email_targets_file)

    def _load_subscriptions(self) -> Dict[str, List[Dict]]:
        """Load subscriptions from disk"""
        return data_manager.load_subscriptions(self.subscriptions_file)

    def _save_subscriptions(self, subscriptions: Dict[str, List[Dict]]):
        """Save subscriptions to disk"""
        data_manager.save_subscriptions(subscriptions, self.subscriptions_file)

    def _cleanup_invalid_subscriptions(self):
        """Clean up invalid subscription records"""
        return data_manager.cleanup_invalid_subscriptions(self.subscriptions_file)
    
    def _is_valid_pdf(self, pdf_path: Path) -> bool:
        """Check if a PDF file is valid by examining its header and basic structure"""
        return pdf_processor.is_valid_pdf(pdf_path)
    
    async def download_pdf(self, pdf_url: str, paper_id: str) -> Optional[Path]:
        """Download PDF file from ArXiv with timeout and retry logic"""
        return await pdf_processor.download_pdf(pdf_url, paper_id, self.processed_papers_dir)
    
    async def pdf_to_markdown(self, pdf_path: Path) -> Optional[str]:
        """Convert PDF to markdown using markitdown"""
        return await pdf_processor.pdf_to_markdown(pdf_path)
    
    async def summarize_with_llm(self, paper_content: str, paper_title: str) -> Optional[str]:
        """Summarize paper content using the configured LLM provider"""
        try:
            return await self.llm_handler.summarize_paper(paper_content, paper_title)
        except Exception as e:
            logger.error(f"Error summarizing with LLM: {e}")
            return None
    
    async def check_llm_service(self) -> bool:
        """Check if the LLM service is running"""
        try:
            return await self.llm_handler.check_service()
        except Exception as e:
            logger.error(f"LLM service check failed: {e}")
            return False
    
    def _get_paper_hash(self, paper_id: str) -> str:
        """Get hash for paper to check if already processed"""
        return data_manager.get_paper_hash(paper_id)
    
    def _is_paper_processed(self, paper_id: str) -> bool:
        """Check if paper has been processed before"""
        return data_manager.is_paper_processed(paper_id, self.summaries_dir)
    
    def _is_paper_processed_today(self, paper_id: str) -> bool:
        """Check if paper was processed today"""
        return data_manager.is_paper_processed_today(paper_id, self.summaries_dir)
    
    def _was_paper_processed_before_today(self, paper_id: str) -> bool:
        """Check if paper was processed before today (not including today)"""
        return data_manager.was_paper_processed_before_today(paper_id, self.summaries_dir)
    
    async def _save_paper_summary(self, paper: Dict, summary: str):
        """Save paper summary to disk"""
        await data_manager.save_paper_summary(paper, summary, self.summaries_dir)
    
    async def _load_existing_summary(self, paper_id: str) -> Optional[Dict]:
        """Load existing summary for a paper"""
        return await data_manager.load_existing_summary(paper_id, self.summaries_dir)

    async def _send_message_via_api(self, user_id: str, message_data: Dict) -> Dict:
        """Send message via HTTP API to message pusher"""
        return await notification_sender.send_message_via_api(user_id, message_data)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length while preserving word boundaries"""
        return notification_sender.truncate_text(text, max_length)

    def _create_paper_embed(self, paper: Dict, index: int, total_count: int, category: str, topic: str) -> Dict:
        """Create individual embed for a single paper with full utilization of embed limits"""
        return notification_sender.create_paper_embed(paper, index, total_count, category, topic)

    def _get_paper_color(self, index: int) -> str:
        """Get color for paper embed based on index"""
        return notification_sender.get_paper_color(index)

    async def _send_embeds_with_interval(self, user_id: str, embeds: List[Dict], interval: float = 2.0):
        """Send multiple embeds with time intervals to avoid rate limits"""
        await notification_sender.send_embeds_with_interval(user_id, embeds, interval)

    async def summarize_and_push(self, category: str, topic: str, user_id: Optional[str] = None, only_new: bool = False, is_scheduled: bool = False) -> Dict:
        """Main workflow for summarizing papers and pushing results with parallel processing"""
        try:
            logger.info(f"Starting summarization workflow for category: '{category}', topic: '{topic}' (user: {user_id}, only_new: {only_new}, scheduled: {is_scheduled})")
            
            # Search for papers
            logger.info(f"Searching ArXiv for papers in category '{category}' on topic: '{topic}'")
            papers = await self.search_arxiv(category, topic, max_results=10)
            if not papers:
                logger.warning(f"No papers found for category: '{category}', topic: '{topic}'")
                return {"success": False, "error": f"No papers found for category: {category}, topic: {topic}"}
            
            logger.info(f"Found {len(papers)} papers for category '{category}', topic '{topic}'")
            
            # Check LLM service
            logger.info(f"Checking {self.llm_handler.provider} service availability...")
            if not await self.check_llm_service():
                logger.error(f"{self.llm_handler.provider} service check failed")
                return {"success": False, "error": f"{self.llm_handler.provider} service is not running. Please ensure {self.llm_handler.provider} service is available."}
            
            # Categorize papers: already processed vs need processing
            summarized_papers = []
            papers_to_process = []
            reused_count = 0
            
            for i, paper in enumerate(papers, 1):
                try:
                    paper_id = paper['id']
                    logger.debug(f"Categorizing paper {i}/{len(papers)}: {paper_id}")
                    
                    # Different logic for scheduled vs instant requests
                    if is_scheduled:
                        # For scheduled runs: skip papers processed before today
                        if self._was_paper_processed_before_today(paper_id) and SUBSCRIPTION_ONLY_NEW:
                            logger.debug(f"Skipping paper {paper_id} - processed before today")
                            continue
                        
                        # If processed today, reuse the summary
                        if self._is_paper_processed(paper_id):
                            logger.debug(f"Paper {paper_id} already processed today - reusing summary")
                            existing_summary = await self._load_existing_summary(paper_id)
                            if existing_summary:
                                summarized_papers.append({
                                    'title': existing_summary['title'],
                                    'authors': existing_summary['authors'],
                                    'summary': existing_summary['summary'],
                                    'pdf_url': existing_summary.get('pdf_url', ''),
                                    'categories': existing_summary.get('categories', [])
                                })
                                reused_count += 1
                                continue
                        
                        # If not processed at all, add to processing queue
                        papers_to_process.append(paper)
                        
                    else:
                        # For instant requests: include all papers, but reuse summaries if available
                        if self._is_paper_processed(paper_id):
                            if only_new:
                                logger.debug(f"Skipping already processed paper {paper_id} (only_new=True)")
                                continue
                            else:
                                logger.debug(f"Loading existing summary for paper {paper_id} (only_new=False)")
                                existing_summary = await self._load_existing_summary(paper_id)
                                
                                if existing_summary:
                                    summarized_papers.append({
                                        'title': existing_summary['title'],
                                        'authors': existing_summary['authors'],
                                        'summary': existing_summary['summary'],
                                        'pdf_url': existing_summary.get('pdf_url', ''),
                                        'categories': existing_summary.get('categories', [])
                                    })
                                    reused_count += 1
                                    continue
                                else:
                                    logger.warning(f"Paper {paper_id} marked as processed but summary not found, reprocessing")
                        
                        # Add to processing queue
                        papers_to_process.append(paper)
                        
                except Exception as e:
                    logger.error(f"Error categorizing paper {paper.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Categorization complete: {len(papers_to_process)} papers to process, {reused_count} existing summaries to reuse")
            
            # Process papers in parallel if there are any to process
            newly_processed_papers = []
            if papers_to_process:
                logger.info(f"Starting parallel processing of {len(papers_to_process)} papers...")
                newly_processed_papers = await self._process_papers_parallel(papers_to_process)
                logger.info(f"Parallel processing completed: {len(newly_processed_papers)} papers successfully processed")
            
            # Combine results
            all_summarized_papers = summarized_papers + newly_processed_papers
            processed_count = len(newly_processed_papers)
            
            logger.info(f"Processing complete: {processed_count} new papers processed, {reused_count} existing summaries reused")
            
            # Create and send embeds if we have papers
            if all_summarized_papers:
                logger.info(f"Creating and sending {len(all_summarized_papers)} embed messages")
                
                if user_id:
                    # Create header embed
                    header_embed = self._create_summary_header_embed(category, topic, len(all_summarized_papers), processed_count, reused_count, only_new)
                    
                    # Create individual paper embeds
                    paper_embeds = []
                    for i, paper in enumerate(all_summarized_papers, 1):
                        paper_embed = self._create_paper_embed(paper, i, len(all_summarized_papers), category, topic)
                        paper_embeds.append(paper_embed)
                    
                    # Combine all embeds (header + papers)
                    all_embeds = [header_embed] + paper_embeds
                    
                    # Send all embeds with intervals
                    logger.info(f"Sending {len(all_embeds)} embeds to user {user_id}")
                    await self._send_embeds_with_interval(user_id, all_embeds, interval=2.5)
                
                return {
                    "success": True,
                    "message": f"Found {len(all_summarized_papers)} papers for category '{category}', topic '{topic}' ({processed_count} newly processed, {reused_count} from cache)",
                    "papers_count": len(all_summarized_papers),
                    "new_papers": processed_count,
                    "cached_papers": reused_count,
                    "papers": all_summarized_papers
                }
            else:
                # Handle case where no papers are found (especially for only_new=True)
                if only_new and processed_count == 0:
                    logger.info(f"No new papers found for scheduled subscription: category '{category}', topic '{topic}'")
                    return {
                        "success": True,
                        "message": f"No new papers found for category '{category}', topic '{topic}' - all papers already processed",
                        "papers_count": 0,
                        "new_papers": 0,
                        "cached_papers": 0,
                        "no_new_papers": True,
                        "papers": []
                    }
                else:
                    logger.info(f"No papers could be processed for category '{category}', topic '{topic}'")
                    return {
                        "success": False,
                        "error": f"No papers could be processed for category '{category}', topic '{topic}' - all papers failed processing",
                        "papers_count": 0,
                        "papers": []
                    }
                
        except Exception as e:
            logger.error(f"Error in summarize_and_push for category '{category}', topic '{topic}': {e}")
            logger.exception("Full traceback for summarize_and_push error:")
            return {"success": False, "error": str(e)}
    
    async def instantly_summarize_and_push(self, category: str, topic: str, user_id: str) -> Dict:
        """Instantly summarize papers for a category and topic and push to user (includes cached papers)"""
        result = await self.summarize_and_push(category, topic, user_id, only_new=False, is_scheduled=False)
        return result

    def _create_summary_header_embed(self, category: str, topic: str, total_papers: int, new_count: int, cached_count: int, only_new: bool = False) -> Dict:
        """Create header embed with summary statistics"""
        return notification_sender.create_summary_header_embed(
            category, topic, total_papers, new_count, cached_count, 
            self.llm_handler.model, only_new
        )

    async def add_subscription(self, user_id: str, category: str, topic: str) -> str:
        """Add a topic subscription for a user"""
        subscriptions = self._cleanup_invalid_subscriptions()

        if user_id not in subscriptions:
            subscriptions[user_id] = []

        # Check if subscription already exists
        for existing_sub in subscriptions[user_id]:
            if (existing_sub.get('category', '').lower() == category.lower() and 
                existing_sub.get('topic', '').lower() == topic.lower()):
                return f"❌ You're already subscribed to '{topic}' in category '{category}'"

        subscriptions[user_id].append({"category": category, "topic": topic})
        self._save_subscriptions(subscriptions)

        return f"✅ Successfully subscribed to '{topic}' in category '{category}'. You'll receive daily summaries at {NOTIFICATION_SCHEDULE_HOUR}:{NOTIFICATION_SCHEDULE_MINUTE:02d}."

    async def remove_subscription(self, user_id: str, category: str, topic: str) -> str:
        """Remove a topic subscription for a user"""
        subscriptions = self._cleanup_invalid_subscriptions()

        if user_id not in subscriptions:
            return "❌ You have no subscriptions to remove."

        # Find and remove subscription
        original_count = len(subscriptions[user_id])
        subscriptions[user_id] = [
            sub for sub in subscriptions[user_id]
            if not (sub.get('category', '').lower() == category.lower() and 
                   sub.get('topic', '').lower() == topic.lower())
        ]

        if len(subscriptions[user_id]) == original_count:
            return f"❌ You're not subscribed to '{topic}' in category '{category}'"

        self._save_subscriptions(subscriptions)
        return f"✅ Successfully unsubscribed from '{topic}' in category '{category}'"

    async def list_subscriptions(self, user_id: str) -> str:
        """List all subscriptions for a user"""
        subscriptions = self._cleanup_invalid_subscriptions()

        if user_id not in subscriptions or not subscriptions[user_id]:
            return "📝 You have no active subscriptions.\nUse `/subscribe add [category] [topic]` to add a subscription!"

        topics_list = []
        for sub in subscriptions[user_id]:
            category = sub.get('category', 'all')
            topic = sub.get('topic', 'unknown')
            topics_list.append(f"• **{category}** - {topic}")

        topics_text = "\n".join(topics_list)
        
        return f"""📚 **Your Research Subscriptions:**
{topics_text}

🕰️ Daily summaries are sent at {NOTIFICATION_SCHEDULE_HOUR}:{NOTIFICATION_SCHEDULE_MINUTE:02d}
💡 Use `/subscribe add [category] [topic]` to add more subscriptions
📝 Use `/subscribe remove [category] [topic]` to remove subscriptions"""
    
    async def daily_summarization(self):
        """Daily summarization phase - process all required papers and store results"""
        logger.info("Starting daily summarization phase...")
        
        try:
            # Get all subscriptions and email targets to determine what papers to process
            subscriptions = self._cleanup_invalid_subscriptions()
            email_targets = self._load_email_targets()
            
            # Collect all unique paper types needed
            all_paper_types = set()
            
            # Add Discord subscription topics
            for user_id, user_subscriptions in subscriptions.items():
                for subscription in user_subscriptions:
                    category = subscription.get('category', 'all')
                    topic = subscription.get('topic', '')
                    if topic:
                        paper_type = f"{category}.{topic}" if category != 'all' else topic
                        all_paper_types.add(paper_type)
            
            # Add email subscription topics
            for email, paper_types in email_targets.items():
                all_paper_types.update(paper_types)
            
            logger.info(f"Found {len(all_paper_types)} unique paper types to process: {list(all_paper_types)}")
            
            # Process each paper type and store results
            daily_results = {}
            
            for paper_type in all_paper_types:
                try:
                    # Parse paper type
                    if '.' in paper_type:
                        category, topic = paper_type.split('.', 1)
                    else:
                        category = 'all'
                        topic = paper_type
                    
                    logger.info(f"Processing paper type for summarization: {category}/{topic}")
                    
                    # Run summarization without sending to users
                    result = await self.summarize_and_push(
                        category, topic, 
                        user_id=None,  # No user ID = no Discord sending
                        only_new=SUBSCRIPTION_ONLY_NEW, 
                        is_scheduled=True
                    )
                    
                    # Store results for later notification
                    daily_results[paper_type] = {
                        'category': category,
                        'topic': topic,
                        'papers': result.get('papers', []),
                        'stats': {
                            'papers_count': len(result.get('papers', [])),
                            'new_papers': result.get('new_papers', 0),
                            'cached_papers': result.get('cached_papers', 0)
                        },
                        'success': result.get('success', False),
                        'no_new_papers': result.get('no_new_papers', False),
                        'processed_at': datetime.now().isoformat()
                    }
                    
                    if result.get('success'):
                        logger.info(f"Summarization completed for {paper_type}: {len(result.get('papers', []))} papers")
                    else:
                        logger.warning(f"Summarization failed for {paper_type}: {result.get('error', 'Unknown error')}")
                    
                    # Small delay between paper types
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error during summarization for paper type {paper_type}: {e}")
                    # Handle case where category/topic parsing failed
                    if '.' in paper_type:
                        error_category, error_topic = paper_type.split('.', 1)
                    else:
                        error_category = 'all'
                        error_topic = paper_type
                    
                    daily_results[paper_type] = {
                        'category': error_category,
                        'topic': error_topic,
                        'papers': [],
                        'stats': {'papers_count': 0, 'new_papers': 0, 'cached_papers': 0},
                        'success': False,
                        'error': str(e),
                        'processed_at': datetime.now().isoformat()
                    }
                    continue
            
            # Save all results for later notification
            await self._save_daily_results(daily_results)
            
            # Cleanup old results files
            await self._cleanup_old_results()
            
            logger.info(f"Daily summarization phase completed. Processed {len(all_paper_types)} paper types.")
            
        except Exception as e:
            logger.error(f"Error in daily summarization phase: {e}")
            raise

    async def daily_notifications(self):
        """Daily notification phase - send Discord messages and emails based on stored results"""
        logger.info("Starting daily notification phase...")
        
        try:
            # Load today's summarization results
            daily_results = await self._load_daily_results()
            
            if not daily_results:
                logger.info("No daily results found - skipping notifications")
                return
            
            # Get current subscriptions and email targets
            subscriptions = self._cleanup_invalid_subscriptions()
            email_targets = self._load_email_targets()
            
            # Phase 1: Send Discord notifications
            logger.info("Phase 1: Sending Discord notifications...")
            for user_id, user_subscriptions in subscriptions.items():
                for subscription in user_subscriptions:
                    try:
                        category = subscription.get('category', 'all')
                        topic = subscription.get('topic', '')
                        
                        if not topic:
                            logger.warning(f"Skipping invalid subscription for user {user_id}: {subscription}")
                            continue
                        
                        paper_type = f"{category}.{topic}" if category != 'all' else topic
                        
                        # Get results for this paper type
                        if paper_type not in daily_results:
                            logger.warning(f"No results found for paper type {paper_type} for user {user_id}")
                            continue
                        
                        result_data = daily_results[paper_type]
                        
                        # Skip if no papers or processing failed
                        if not result_data.get('success') or not result_data.get('papers'):
                            if result_data.get('no_new_papers'):
                                logger.info(f"No new papers for {paper_type} for user {user_id}")
                            else:
                                logger.warning(f"No papers or failed processing for {paper_type} for user {user_id}")
                            continue
                        
                        # Send Discord notification using stored results
                        logger.info(f"Sending Discord notification for {paper_type} to user {user_id} with {len(result_data['papers'])} papers")
                        
                        # Create and send embeds
                        header_embed = self._create_summary_header_embed(
                            category, topic, 
                            len(result_data['papers']), 
                            result_data['stats']['new_papers'], 
                            result_data['stats']['cached_papers'], 
                            only_new=True
                        )
                        
                        paper_embeds = []
                        for i, paper in enumerate(result_data['papers'], 1):
                            paper_embed = self._create_paper_embed(paper, i, len(result_data['papers']), category, topic)
                            paper_embeds.append(paper_embed)
                        
                        all_embeds = [header_embed] + paper_embeds
                        await self._send_embeds_with_interval(user_id, all_embeds, interval=2.5)
                        
                        logger.info(f"Discord notification sent successfully for {paper_type} to user {user_id}")
                        
                        # Add delay between users
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        logger.error(f"Error sending Discord notification for {subscription} to user {user_id}: {e}")
                        continue
            
            # Phase 2: Send Email notifications
            logger.info("Phase 2: Sending Email notifications...")
            for email, subscribed_paper_types in email_targets.items():
                if not subscribed_paper_types:
                    logger.info(f"Skipping email {email} - no paper types configured")
                    continue
                
                logger.info(f"Processing email notifications for {email}: {subscribed_paper_types}")
                
                for paper_type in subscribed_paper_types:
                    try:
                        # Get results for this paper type
                        if paper_type not in daily_results:
                            logger.warning(f"No results found for paper type {paper_type} for email {email}")
                            continue
                        
                        result_data = daily_results[paper_type]
                        
                        # Skip if no papers or processing failed
                        if not result_data.get('success') or not result_data.get('papers'):
                            if result_data.get('no_new_papers'):
                                logger.info(f"No new papers for {paper_type} for email {email}")
                            else:
                                logger.warning(f"No papers or failed processing for {paper_type} for email {email}")
                            continue
                        
                        # Send email notification
                        logger.info(f"Sending email for {paper_type} to {email} with {len(result_data['papers'])} papers")
                        
                        email_result = await self.email_service.send_paper_summary_email(
                            to_emails=[email],
                            category=result_data['category'],
                            topic=result_data['topic'],
                            papers=result_data['papers'],
                            stats=result_data['stats']
                        )
                        
                        if email_result['success']:
                            logger.info(f"Email sent successfully for {paper_type} to {email}")
                        else:
                            logger.error(f"Failed to send email for {paper_type} to {email}: {email_result.get('error')}")
                        
                        # Add delay between emails
                        await asyncio.sleep(5)
                        
                    except Exception as e:
                        logger.error(f"Error sending email for {paper_type} to {email}: {e}")
                        continue
                
                # Add delay between different email addresses
                await asyncio.sleep(10)
            
            logger.info("Daily notification phase completed")
            
        except Exception as e:
            logger.error(f"Error in daily notification phase: {e}")
            raise

    async def start_summarization_scheduler(self):
        """Start the daily summarization scheduler"""
        await scheduler_manager.run_summarization_scheduler(
            SUMMARIZATION_SCHEDULE_HOUR, 
            SUMMARIZATION_SCHEDULE_MINUTE, 
            self.daily_summarization
        )

    async def start_notification_scheduler(self):
        """Start the daily notification scheduler"""
        await scheduler_manager.run_notification_scheduler(
            NOTIFICATION_SCHEDULE_HOUR, 
            NOTIFICATION_SCHEDULE_MINUTE, 
            self.daily_notifications
        )

    async def start_scheduler(self):
        """Start both summarization and notification schedulers"""
        await scheduler_manager.run_dual_scheduler(
            SUMMARIZATION_SCHEDULE_HOUR,
            SUMMARIZATION_SCHEDULE_MINUTE,
            NOTIFICATION_SCHEDULE_HOUR,
            NOTIFICATION_SCHEDULE_MINUTE,
            self.daily_summarization,
            self.daily_notifications
        )

    def _get_daily_results_file(self) -> Path:
        """Get path for today's daily results file"""
        return data_manager.get_daily_results_file(self.base_dir)
    
    async def _save_daily_results(self, results: Dict):
        """Save daily summarization results for later notification"""
        await data_manager.save_daily_results(results, self.base_dir)
    
    async def _load_daily_results(self) -> Dict:
        """Load today's daily results for notification"""
        return await data_manager.load_daily_results(self.base_dir)
    
    async def _cleanup_old_results(self):
        """Clean up results files older than 8 days"""
        await data_manager.cleanup_old_results(self.base_dir)

    async def _download_and_convert_paper(self, paper: Dict, download_semaphore: asyncio.Semaphore, processing_queue: asyncio.Queue) -> None:
        """Download and convert a single paper, then put it in processing queue"""
        async with download_semaphore:
            try:
                paper_id = paper['id']
                logger.info(f"Starting download for paper {paper_id}")
                
                # Step 1: Download PDF (limited concurrency)
                logger.debug(f"Downloading PDF for paper {paper_id}")
                pdf_path = await self.download_pdf(paper.get('pdf_url', ''), paper_id)
                if not pdf_path:
                    logger.warning(f"Could not download PDF for paper {paper_id}")
                    await processing_queue.put(None)  # Signal failure
                    return
                
                # Step 2: Convert to markdown (still within download limit)
                logger.debug(f"Converting PDF to markdown for paper {paper_id}")
                markdown_content = await self.pdf_to_markdown(pdf_path)
                if not markdown_content:
                    logger.warning(f"Could not convert PDF to markdown for paper {paper_id}")
                    await processing_queue.put(None)  # Signal failure
                    return
                
                # Put the prepared data into processing queue
                paper_data = {
                    'paper': paper,
                    'markdown_content': markdown_content
                }
                await processing_queue.put(paper_data)
                logger.info(f"Paper {paper_id} ready for summarization")
                
            except Exception as e:
                logger.error(f"Error downloading/converting paper {paper.get('id', 'unknown')}: {e}")
                await processing_queue.put(None)  # Signal failure

    async def _summarize_paper_worker(self, processing_queue: asyncio.Queue, results_list: List, total_papers: int) -> None:
        """Worker that processes papers from the queue and generates summaries (unlimited concurrency)"""
        while True:
            try:
                # Get paper from queue
                paper_data = await processing_queue.get()
                
                # None signals end of processing or failure
                if paper_data is None:
                    processing_queue.task_done()
                    continue
                
                paper = paper_data['paper']
                markdown_content = paper_data['markdown_content']
                paper_id = paper['id']
                
                logger.info(f"Starting summarization for paper {paper_id}")
                
                # Step 3: Summarize with LLM (unlimited concurrency)
                logger.debug(f"Generating AI summary for paper {paper_id}")
                summary = await self.summarize_with_llm(markdown_content, paper['title'])
                if not summary:
                    logger.warning(f"Could not generate summary for paper {paper_id}")
                    processing_queue.task_done()
                    continue
                
                # Step 4: Save summary
                logger.debug(f"Saving summary for paper {paper_id}")
                await self._save_paper_summary(paper, summary)
                
                # Add to results
                result = {
                    'title': paper['title'],
                    'authors': paper['authors'],
                    'summary': summary,
                    'pdf_url': paper.get('pdf_url', ''),
                    'categories': paper.get('categories', []),
                    'id': paper_id
                }
                results_list.append(result)
                
                logger.info(f"Successfully completed summarization for paper {paper_id}")
                
            except Exception as e:
                logger.error(f"Error in summarization worker: {e}")
            finally:
                processing_queue.task_done()

    async def _process_papers_parallel(self, papers_to_process: List[Dict], max_concurrent_downloads: int = 3) -> List[Dict]:
        """Process papers with separated download and summarization phases"""
        if not papers_to_process:
            return []
        
        logger.info(f"Starting separated processing of {len(papers_to_process)} papers with max {max_concurrent_downloads} concurrent downloads")
        
        # Create queue for passing data from download to summarization
        processing_queue = asyncio.Queue()
        results_list = []
        
        # Create semaphore to limit concurrent downloads only
        download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        
        # Start download tasks (limited concurrency)
        download_tasks = []
        for paper in papers_to_process:
            task = asyncio.create_task(
                self._download_and_convert_paper(paper, download_semaphore, processing_queue)
            )
            download_tasks.append(task)
        
        # Start summarization workers (unlimited concurrency - one per paper)
        summarization_tasks = []
        for _ in papers_to_process:
            task = asyncio.create_task(
                self._summarize_paper_worker(processing_queue, results_list, len(papers_to_process))
            )
            summarization_tasks.append(task)
        
        # Wait for all downloads to complete
        await asyncio.gather(*download_tasks, return_exceptions=True)
        
        # Wait for all items in queue to be processed
        await processing_queue.join()
        
        # Cancel summarization workers
        for task in summarization_tasks:
            task.cancel()
        
        # Wait for workers to finish cancelling
        await asyncio.gather(*summarization_tasks, return_exceptions=True)
        
        successful_count = len(results_list)
        failed_count = len(papers_to_process) - successful_count
        
        logger.info(f"Separated processing completed: {successful_count} successful, {failed_count} failed")
        return results_list
