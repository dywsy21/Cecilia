import asyncio
import aiohttp
import aiofiles
import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

from bot.config import (
    SUBSCRIPTION_ONLY_NEW, 
    SUMMARIZATION_SCHEDULE_HOUR, 
    SUMMARIZATION_SCHEDULE_MINUTE,
    NOTIFICATION_SCHEDULE_HOUR,
    NOTIFICATION_SCHEDULE_MINUTE
)
from ..email_service.email_service import EmailService
from ..llm_handler.llm_handler import LLMHandler

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
        max_retries = 8
        retry_delay = 2  # Start with 2 seconds delay
        
        for attempt in range(max_retries):
            try:
                # Build search query based on category
                search_query = f'{category if category else 'all'}.{topic}'
                
                params = {
                    'search_query': search_query,
                    'sortBy': 'lastUpdatedDate',
                    'sortOrder': 'descending',
                    'start': 0,
                    'max_results': max_results
                }
                
                logger.info(f"Searching ArXiv with query: {search_query} (attempt {attempt + 1}/{max_retries})")
                
                # Use timeout for the request
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.arxiv_base_url, params=params) as response:
                        if response.status == 200:
                            xml_content = await response.text()
                            papers = await self._parse_arxiv_response(xml_content)
                            logger.info(f"Successfully retrieved {len(papers)} papers from ArXiv (attempt {attempt + 1})")
                            return papers
                        else:
                            logger.warning(f"ArXiv API returned status {response.status} on attempt {attempt + 1}")
                            if attempt == max_retries - 1:
                                logger.error(f"Failed to search ArXiv after {max_retries} attempts: HTTP {response.status}")
                                return []
                            
            except asyncio.TimeoutError:
                logger.warning(f"ArXiv search timeout on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to search ArXiv after {max_retries} attempts: timeout")
                    return []
                    
            except aiohttp.ClientError as e:
                logger.warning(f"ArXiv client error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to search ArXiv after {max_retries} attempts: {e}")
                    return []
                    
            except Exception as e:
                logger.warning(f"Unexpected error searching ArXiv on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to search ArXiv after {max_retries} attempts: {e}")
                    return []
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # 2s, 4s, 8s, 16s
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        return []
    
    async def _parse_arxiv_response(self, xml_content: str) -> List[Dict]:
        """Parse XML response from ArXiv API"""
        try:
            root = ET.fromstring(xml_content)
            papers = []
            
            # Define namespaces
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            for entry in root.findall('atom:entry', ns):
                paper = {}
                
                # Extract basic info
                paper['id'] = entry.find('atom:id', ns).text.split('/')[-1]
                paper['title'] = entry.find('atom:title', ns).text.strip()
                paper['summary'] = entry.find('atom:summary', ns).text.strip()
                paper['updated'] = entry.find('atom:updated', ns).text
                paper['published'] = entry.find('atom:published', ns).text
                
                # Extract authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns).text
                    authors.append(name)
                paper['authors'] = authors
                
                # Extract PDF link
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        paper['pdf_url'] = link.get('href')
                        break
                
                # Extract categories
                categories = []
                for category in entry.findall('atom:category', ns):
                    categories.append(category.get('term'))
                paper['categories'] = categories
                
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            logger.error(f"Error parsing ArXiv XML: {e}")
            return []
    
    def _load_email_targets(self) -> Dict[str, List[str]]:
        """Load email targets from disk with new format: {email: [categories]}"""
        try:
            with open(self.email_targets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Handle migration from old format (list of strings) to new format (dict)
                if isinstance(data, list):
                    logger.info("Migrating email_targets.json from old format to new format")
                    # Convert old format to new format with empty subscriptions
                    new_data = {email: [] for email in data}
                    self._save_email_targets(new_data)
                    return new_data
                
                return data
        except Exception as e:
            logger.error(f"Error loading email targets: {e}")
            return {}

    def _save_email_targets(self, email_targets: Dict[str, List[str]]):
        """Save email targets to disk"""
        try:
            with open(self.email_targets_file, 'w', encoding='utf-8') as f:
                json.dump(email_targets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving email targets: {e}")

    def _load_subscriptions(self) -> Dict[str, List[Dict]]:
        """Load subscriptions from disk"""
        try:
            with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Handle migration from old format (list of strings) to new format (list of dicts)
                migrated = False
                for user_id, subscriptions in data.items():
                    if subscriptions and isinstance(subscriptions[0], str):
                        # Convert old format to new format
                        data[user_id] = [{"category": "all", "topic": topic} for topic in subscriptions]
                        migrated = True
                        logger.info(f"Migrated subscriptions for user {user_id} from old format")
                
                if migrated:
                    self._save_subscriptions(data)
                    logger.info("Subscription migration completed")
                
                return data
        except Exception as e:
            logger.error(f"Error loading subscriptions: {e}")
            return {}

    def _save_subscriptions(self, subscriptions: Dict[str, List[Dict]]):
        """Save subscriptions to disk"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(subscriptions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving subscriptions: {e}")

    def _cleanup_invalid_subscriptions(self):
        """Clean up invalid subscription records"""
        try:
            subscriptions = self._load_subscriptions()
            cleaned = False
            
            for user_id, user_subscriptions in list(subscriptions.items()):
                # Remove invalid subscription entries
                valid_subscriptions = []
                for sub in user_subscriptions:
                    if isinstance(sub, dict) and 'category' in sub and 'topic' in sub:
                        valid_subscriptions.append(sub)
                    else:
                        logger.info(f"Removing invalid subscription entry for user {user_id}: {sub}")
                        cleaned = True
                
                subscriptions[user_id] = valid_subscriptions
                
                # Remove users with no valid subscriptions
                if not valid_subscriptions:
                    del subscriptions[user_id]
                    logger.info(f"Removed user {user_id} with no valid subscriptions")
                    cleaned = True
            
            if cleaned:
                self._save_subscriptions(subscriptions)
                logger.info("Subscription cleanup completed")
            
            return subscriptions
        except Exception as e:
            logger.error(f"Error during subscription cleanup: {e}")
            return {}
    
    def _is_valid_pdf(self, pdf_path: Path) -> bool:
        """Check if a PDF file is valid by examining its header and basic structure"""
        try:
            if not pdf_path.exists() or pdf_path.stat().st_size < 100:  # Too small to be a valid PDF
                return False
            
            with open(pdf_path, 'rb') as f:
                # Check PDF header
                header = f.read(10)
                if not header.startswith(b'%PDF-'):
                    return False
                
                # Check if file has EOF marker (basic structure validation)
                f.seek(-100, 2)  # Go to last 100 bytes
                tail = f.read()
                if b'%%EOF' not in tail:
                    return False
                
            return True
        except Exception as e:
            logger.warning(f"Error validating PDF {pdf_path}: {e}")
            return False
    
    async def download_pdf(self, pdf_url: str, paper_id: str) -> Optional[Path]:
        """Download PDF file from ArXiv with timeout and retry logic"""
        pdf_path = self.processed_papers_dir / f"{paper_id}.pdf"
        try:
            # Check if already downloaded and valid
            if pdf_path.exists() and self._is_valid_pdf(pdf_path):
                logger.info(f"Valid PDF already exists: {pdf_path}")
                return pdf_path
            
            # Remove existing invalid PDF if present
            if pdf_path.exists():
                logger.info(f"Removing invalid/incomplete PDF: {pdf_path}")
                pdf_path.unlink()
            
            max_retries = 5
            timeout_seconds = 20
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Downloading PDF attempt {attempt + 1}/{max_retries}: {paper_id}")
                    
                    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(pdf_url) as response:
                            if response.status == 200:
                                async with aiofiles.open(pdf_path, 'wb') as f:
                                    async for chunk in response.content.iter_chunked(8192):
                                        await f.write(chunk)
                                
                                # Validate the downloaded PDF
                                if self._is_valid_pdf(pdf_path):
                                    logger.info(f"Successfully downloaded and validated PDF: {pdf_path} (attempt {attempt + 1})")
                                    return pdf_path
                                else:
                                    logger.warning(f"Downloaded PDF is invalid on attempt {attempt + 1} for {paper_id}")
                                    # Remove invalid PDF before retry
                                    if pdf_path.exists():
                                        pdf_path.unlink()
                                    if attempt == max_retries - 1:
                                        logger.error(f"Failed to download valid PDF after {max_retries} attempts")
                                        return None
                            else:
                                logger.warning(f"HTTP {response.status} on attempt {attempt + 1} for {paper_id}")
                                if attempt == max_retries - 1:
                                    logger.error(f"Failed to download PDF after {max_retries} attempts: HTTP {response.status}")
                                    return None
                                
                except asyncio.TimeoutError:
                    logger.warning(f"Download timeout ({timeout_seconds}s) on attempt {attempt + 1} for {paper_id}")
                    # Remove partial download if exists
                    if pdf_path.exists():
                        pdf_path.unlink()
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to download PDF after {max_retries} attempts: timeout")
                        return None
                    
                except aiohttp.ClientError as e:
                    logger.warning(f"Client error on attempt {attempt + 1} for {paper_id}: {e}")
                    # Remove partial download if exists
                    if pdf_path.exists():
                        pdf_path.unlink()
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to download PDF after {max_retries} attempts: {e}")
                        return None
                
                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt)  # 1s, 2s, 4s
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
            
            return None
                        
        except Exception as e:
            logger.error(f"Unexpected error downloading PDF for {paper_id}: {e}")
            # Clean up any partial download
            if 'pdf_path' in locals() and pdf_path.exists():
                try:
                    pdf_path.unlink()
                except Exception:
                    pass
            return None
    
    async def pdf_to_markdown(self, pdf_path: Path) -> Optional[str]:
        """Convert PDF to markdown using markitdown"""
        try:
            # Use markitdown CLI tool
            result = subprocess.run(
                ['markitdown', str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"markitdown failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("PDF conversion timeout")
            return None
        except FileNotFoundError:
            logger.error("markitdown not found. Please install markitdown: pip install markitdown")
            return None
        except Exception as e:
            logger.error(f"Error converting PDF to markdown: {e}")
            return None
    
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
        return hashlib.md5(paper_id.encode()).hexdigest()
    
    def _is_paper_processed(self, paper_id: str) -> bool:
        """Check if paper has been processed before"""
        paper_hash = self._get_paper_hash(paper_id)
        summary_file = self.summaries_dir / f"{paper_hash}.json"
        return summary_file.exists()
    
    def _is_paper_processed_today(self, paper_id: str) -> bool:
        """Check if paper was processed today"""
        paper_hash = self._get_paper_hash(paper_id)
        summary_file = self.summaries_dir / f"{paper_hash}.json"
        
        if not summary_file.exists():
            return False
        
        try:
            # Check file modification time
            file_mod_time = datetime.fromtimestamp(summary_file.stat().st_mtime)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return file_mod_time >= today_start
        except Exception as e:
            logger.error(f"Error checking file modification time for {paper_id}: {e}")
            return False
    
    def _was_paper_processed_before_today(self, paper_id: str) -> bool:
        """Check if paper was processed before today (not including today)"""
        paper_hash = self._get_paper_hash(paper_id)
        summary_file = self.summaries_dir / f"{paper_hash}.json"
        
        if not summary_file.exists():
            return False
        
        try:
            # Check file modification time
            file_mod_time = datetime.fromtimestamp(summary_file.stat().st_mtime)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return file_mod_time < today_start
        except Exception as e:
            logger.error(f"Error checking file modification time for {paper_id}: {e}")
            return False
    
    async def _save_paper_summary(self, paper: Dict, summary: str):
        """Save paper summary to disk"""
        paper_hash = self._get_paper_hash(paper['id'])
        summary_file = self.summaries_dir / f"{paper_hash}.json"
        
        summary_data = {
            'paper_id': paper['id'],
            'title': paper['title'],
            'authors': paper['authors'],
            'pdf_url': paper.get('pdf_url', ''),
            'summary': summary,
            'processed_at': datetime.now().isoformat(),
            'categories': paper.get('categories', [])
        }
        
        async with aiofiles.open(summary_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(summary_data, indent=2, ensure_ascii=False))
    
    async def _load_existing_summary(self, paper_id: str) -> Optional[Dict]:
        """Load existing summary for a paper"""
        try:
            paper_hash = self._get_paper_hash(paper_id)
            summary_file = self.summaries_dir / f"{paper_hash}.json"
            
            if summary_file.exists():
                async with aiofiles.open(summary_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content)
            return None
        except Exception as e:
            logger.error(f"Error loading existing summary for {paper_id}: {e}")
            return None

    async def _send_message_via_api(self, user_id: str, message_data: Dict) -> Dict:
        """Send message via HTTP API to message pusher"""
        try:
            url = "http://localhost:8011/push"
            headers = {"Content-Type": "application/json"}
            payload = {
                "user_id": str(user_id),
                # "channel_id": "1190649951693316169",
                "message": message_data
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Message sent successfully via API: {result}")
                        return {"success": True, "result": result}
                    else:
                        error_text = await response.text()
                        logger.error(f"Message pusher API error {response.status}: {error_text}")
                        return {"success": False, "error": f"API error {response.status}: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error calling message pusher API: {e}")
            return {"success": False, "error": str(e)}

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length while preserving word boundaries"""
        if len(text) <= max_length:
            return text
        
        # Find the last space before the limit
        truncated = text[:max_length-3]
        last_space = truncated.rfind(' ')
        
        if last_space > 0:
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."

    def _create_paper_embed(self, paper: Dict, index: int, total_count: int, category: str, topic: str) -> Dict:
        """Create individual embed for a single paper with full utilization of embed limits"""
        
        # Prepare authors string
        authors_str = ", ".join(paper['authors'])
        if len(authors_str) > 200:  # Limit for field value
            authors_str = self._truncate_text(authors_str, 200)
        
        # Prepare categories string
        categories_str = ", ".join(paper['categories'])
        if len(categories_str) > 200:
            categories_str = self._truncate_text(categories_str, 200)
        
        # Truncate title for embed title (256 char limit)
        title = self._truncate_text(paper['title'], 250)
        
        # Use full 4096 character limit for description with the AI summary
        description = f"**论文总结：**\n\n{paper['summary']}"
        description = self._truncate_text(description, 4090)  # Leave some buffer
        
        # Create rich embed with visual appeal
        embed = {
            "title": f"📄 {title}",
            "description": description,
            "color": self._get_paper_color(index),
            "fields": [
                {
                    "name": "👥 作者",
                    "value": authors_str,
                    "inline": False
                },
                {
                    "name": "🏷️ 分类",
                    "value": categories_str or "未分类",
                    "inline": True
                },
                {
                    "name": "📊 进度",
                    "value": f"{index}/{total_count}",
                    "inline": True
                },
                {
                    "name": "🔗 链接",
                    "value": f"[📖 阅读原文]({paper['pdf_url']})",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"类别: {category} • 主题: {topic} • Cecilia 研究助手 • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            },
            # "thumbnail": {
            #     "url": "https://arxiv.org/static/browse/0.3.4/images/arxiv-logo-fb.png"
            # }
        }
        
        return embed

    def _get_paper_color(self, index: int) -> str:
        """Get color for paper embed based on index"""
        colors = [
            "#1f8b4c",  # Green
            "#3498db",  # Blue  
            "#9b59b6",  # Purple
            "#e91e63",  # Pink
            "#f39c12",  # Orange
            "#e74c3c",  # Red
            "#1abc9c",  # Teal
            "#34495e",  # Dark gray
            "#16a085",  # Dark teal
            "#8e44ad"   # Dark purple
        ]
        return colors[index % len(colors)]

    async def _send_embeds_with_interval(self, user_id: str, embeds: List[Dict], interval: float = 2.0):
        """Send multiple embeds with time intervals to avoid rate limits"""
        
        for i, embed in enumerate(embeds):
            try:
                message_data = {"embed": embed}
                api_result = await self._send_message_via_api(user_id, message_data)
                
                if api_result["success"]:
                    logger.info(f"Sent embed {i+1}/{len(embeds)} successfully")
                else:
                    logger.error(f"Failed to send embed {i+1}/{len(embeds)}: {api_result.get('error', 'Unknown error')}")
                
                # Add interval between messages to avoid rate limits (except for last message)
                if i < len(embeds) - 1:
                    await asyncio.sleep(interval)
                    
            except Exception as e:
                logger.error(f"Error sending embed {i+1}/{len(embeds)}: {e}")
                continue

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
                newly_processed_papers = await self._process_papers_parallel(papers_to_process, max_concurrent=5)
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
        
        # Create description with processing stats
        if only_new:
            # For scheduled subscriptions, emphasize new papers only
            if new_count > 0:
                status_text = f"🆕 新发现论文: {new_count} 篇"
                description = f"""🔍 **搜索类别:** {category}
🎯 **搜索主题:** {topic}
📅 **定时推送模式:** 仅显示新论文
📈 **处理状态:** 
{status_text}

⏰ **处理时间:** {datetime.now().strftime('%Y年%m月%d日 %H:%M')}

📚 为您展示最新发现的论文总结..."""
            else:
                description = f"""🔍 **搜索类别:** {category}
🎯 **搜索主题:** {topic}
📅 **定时推送模式:** 仅显示新论文
📈 **处理状态:** 
📊 暂无新论文发现

⏰ **检查时间:** {datetime.now().strftime('%Y年%m月%d日 %H:%M')}

💡 所有相关论文均已在之前处理过，请等待新论文发布。"""
        else:
            # For instant requests, show all papers
            if new_count > 0 and cached_count > 0:
                status_text = f"🆕 新处理: {new_count} 篇\n💾 缓存获取: {cached_count} 篇"
            elif new_count > 0:
                status_text = f"🆕 全部新处理: {new_count} 篇"
            elif cached_count > 0:
                status_text = f"💾 全部来自缓存: {cached_count} 篇"
            else:
                status_text = f"📊 共找到: {total_papers} 篇"

            description = f"""🔍 **搜索类别:** {category}
🎯 **搜索主题:** {topic}
⚡ **即时查询模式:** 显示所有相关论文
📈 **处理状态:** 
{status_text}

⏰ **处理时间:** {datetime.now().strftime('%Y年%m月%d日 %H:%M')}

📚 即将为您展示每篇论文的详细总结..."""

        embed = {
            "title": "🎯 ArXiv 论文总结报告",
            "description": description,
            "color": "#2ecc71" if total_papers > 0 else "#95a5a6",
            "fields": [
                {
                    "name": "📊 统计信息",
                    "value": f"📄 总论文数: **{total_papers}**\n🔄 处理状态: **完成**\n⚡ 响应时间: **实时**",
                    "inline": True
                },
                {
                    "name": "🛠️ 技术信息", 
                    "value": f"🤖 AI模型: **{self.llm_handler.model}**\n📡 数据源: **ArXiv API**\n🔍 排序: **最新更新**",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Cecilia 研究助手 • 基于最新 ArXiv 数据"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return embed

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
        logger.info("Starting summarization scheduler")
        
        max_consecutive_errors = 5
        consecutive_errors = 0
        
        while True:
            try:
                now = datetime.now()
                target_time = now.replace(hour=SUMMARIZATION_SCHEDULE_HOUR, minute=SUMMARIZATION_SCHEDULE_MINUTE, second=0, microsecond=0)
                
                # If it's past scheduled time today, schedule for tomorrow
                if now.time() > time(SUMMARIZATION_SCHEDULE_HOUR, SUMMARIZATION_SCHEDULE_MINUTE):
                    target_time = target_time + timedelta(days=1)
                
                # Calculate sleep time
                sleep_seconds = (target_time - now).total_seconds()
                logger.info(f"Next summarization run scheduled for: {target_time}")
                
                await asyncio.sleep(sleep_seconds)
                
                # Run the summarization phase
                logger.info("Starting daily summarization phase")
                await self.daily_summarization()
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
                    from ..apps import CeciliaServiceError
                    raise CeciliaServiceError(f"Summarization scheduler failed repeatedly: {e}")
                
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)

    async def start_notification_scheduler(self):
        """Start the daily notification scheduler"""
        logger.info("Starting notification scheduler")
        
        max_consecutive_errors = 5
        consecutive_errors = 0
        
        while True:
            try:
                now = datetime.now()
                target_time = now.replace(hour=NOTIFICATION_SCHEDULE_HOUR, minute=NOTIFICATION_SCHEDULE_MINUTE, second=0, microsecond=0)
                
                # If it's past scheduled time today, schedule for tomorrow
                if now.time() > time(NOTIFICATION_SCHEDULE_HOUR, NOTIFICATION_SCHEDULE_MINUTE):
                    target_time = target_time + timedelta(days=1)
                
                # Calculate sleep time
                sleep_seconds = (target_time - now).total_seconds()
                logger.info(f"Next notification run scheduled for: {target_time}")
                
                await asyncio.sleep(sleep_seconds)
                
                # Run the notification phase
                logger.info("Starting daily notification phase")
                await self.daily_notifications()
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
                    from ..apps import CeciliaServiceError
                    raise CeciliaServiceError(f"Notification scheduler failed repeatedly: {e}")
                
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)

    async def start_scheduler(self):
        """Start both summarization and notification schedulers"""
        logger.info("Starting both summarization and notification schedulers")
        
        # Create tasks for both schedulers
        summarization_task = asyncio.create_task(self.start_summarization_scheduler())
        notification_task = asyncio.create_task(self.start_notification_scheduler())
        
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

    def _get_daily_results_file(self) -> Path:
        """Get path for today's daily results file"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.base_dir / f"daily_results_{today}.json"
    
    async def _save_daily_results(self, results: Dict):
        """Save daily summarization results for later notification"""
        try:
            results_file = self._get_daily_results_file()
            
            # Load existing results if any
            existing_results = {}
            if results_file.exists():
                async with aiofiles.open(results_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    existing_results = json.loads(content)
            
            # Merge new results
            existing_results.update(results)
            
            # Save updated results
            async with aiofiles.open(results_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_results, indent=2, ensure_ascii=False))
            
            logger.info(f"Saved daily results to {results_file}")
            
        except Exception as e:
            logger.error(f"Error saving daily results: {e}")
    
    async def _load_daily_results(self) -> Dict:
        """Load today's daily results for notification"""
        try:
            results_file = self._get_daily_results_file()
            
            if not results_file.exists():
                logger.info("No daily results file found for today")
                return {}
            
            async with aiofiles.open(results_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                results = json.loads(content)
            
            logger.info(f"Loaded daily results from {results_file}")
            return results
            
        except Exception as e:
            logger.error(f"Error loading daily results: {e}")
            return {}
    
    async def _cleanup_old_results(self):
        """Clean up results files older than 8 days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=8)
            
            for file_path in self.base_dir.glob("daily_results_*.json"):
                try:
                    # Extract date from filename
                    date_str = file_path.stem.replace("daily_results_", "")
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    if file_date < cutoff_date:
                        file_path.unlink()
                        logger.info(f"Cleaned up old results file: {file_path}")
                        
                except Exception as e:
                    logger.warning(f"Error processing results file {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during results cleanup: {e}")

    async def _process_paper_pipeline(self, paper: Dict, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """Process a single paper through the complete pipeline with concurrency control"""
        async with semaphore:
            try:
                paper_id = paper['id']
                logger.info(f"Starting pipeline for paper {paper_id}")
                
                # Step 1: Download PDF
                logger.debug(f"Downloading PDF for paper {paper_id}")
                pdf_path = await self.download_pdf(paper.get('pdf_url', ''), paper_id)
                if not pdf_path:
                    logger.warning(f"Could not download PDF for paper {paper_id}")
                    return None
                
                # Step 2: Convert to markdown
                logger.debug(f"Converting PDF to markdown for paper {paper_id}")
                markdown_content = await self.pdf_to_markdown(pdf_path)
                if not markdown_content:
                    logger.warning(f"Could not convert PDF to markdown for paper {paper_id}")
                    return None
                
                # Step 3: Summarize with LLM
                logger.debug(f"Generating AI summary for paper {paper_id}")
                summary = await self.summarize_with_llm(markdown_content, paper['title'])
                if not summary:
                    logger.warning(f"Could not generate summary for paper {paper_id}")
                    return None
                
                # Step 4: Save summary
                logger.debug(f"Saving summary for paper {paper_id}")
                await self._save_paper_summary(paper, summary)
                
                logger.info(f"Successfully completed pipeline for paper {paper_id}")
                return {
                    'title': paper['title'],
                    'authors': paper['authors'],
                    'summary': summary,
                    'pdf_url': paper.get('pdf_url', ''),
                    'categories': paper.get('categories', []),
                    'id': paper_id
                }
                
            except Exception as e:
                logger.error(f"Error in pipeline for paper {paper.get('id', 'unknown')}: {e}")
                return None

    async def _process_papers_parallel(self, papers_to_process: List[Dict], max_concurrent: int = 2) -> List[Dict]:
        """Process multiple papers in parallel with controlled concurrency"""
        if not papers_to_process:
            return []
        
        logger.info(f"Starting parallel processing of {len(papers_to_process)} papers with max {max_concurrent} concurrent tasks")
        
        # Create semaphore to limit concurrent downloads/processing
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Create tasks for all papers
        tasks = []
        for paper in papers_to_process:
            task = asyncio.create_task(self._process_paper_pipeline(paper, semaphore))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        successful_papers = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {result}")
                failed_count += 1
            elif result is not None:
                successful_papers.append(result)
            else:
                failed_count += 1
        
        logger.info(f"Parallel processing completed: {len(successful_papers)} successful, {failed_count} failed")
        return successful_papers
