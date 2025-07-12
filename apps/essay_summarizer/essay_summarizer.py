import asyncio
import aiohttp
import aiofiles
import json
import logging
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

from bot.config import SUBSCRIPTION_ONLY_NEW
from ..email_service.email_service import EmailService

logger = logging.getLogger(__name__)

class EssaySummarizer:
    """Handles essay summarization from ArXiv with subscription management"""
    
    def __init__(self):
        try:
            self.arxiv_base_url = "https://export.arxiv.org/api/query"
            self.ollima_url = "http://localhost:11434/api/generate"
            self.data_dir = Path("data/essay_summarizer")
            self.subscriptions_file = self.data_dir / "subscriptions.json"
            self.email_targets_file = self.data_dir / "email_targets.json"
            self.processed_papers_dir = self.data_dir / "processed"
            self.summaries_dir = self.data_dir / "summaries"
            
            # Create directories
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.processed_papers_dir.mkdir(parents=True, exist_ok=True)
            self.summaries_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize subscriptions file if it doesn't exist
            if not self.subscriptions_file.exists():
                self._save_subscriptions({})
            
            # Initialize email targets file if it doesn't exist
            if not self.email_targets_file.exists():
                self._save_email_targets({})
            
            self.app_manager = None  # Will be set by AppManager
            self.email_service = EmailService()
            logger.info("EssaySummarizer initialized with email support")
        except PermissionError as e:
            logger.error(f"Permission denied creating data directories: {e}")
            from ..apps import CeciliaServiceError
            raise CeciliaServiceError(f"Cannot create data directories: {e}")
        except OSError as e:
            logger.error(f"OS error initializing EssaySummarizer: {e}")
            from ..apps import CeciliaServiceError
            raise CeciliaServiceError(f"System error initializing EssaySummarizer: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize EssaySummarizer: {e}")
            from ..apps import CeciliaServiceError
            raise CeciliaServiceError(f"Cannot initialize EssaySummarizer: {e}")

    def set_app_manager(self, app_manager):
        """Set reference to AppManager for message pushing"""
        self.app_manager = app_manager
    
    async def search_arxiv(self, category: str, topic: str, max_results: int = 10) -> List[Dict]:
        """Search ArXiv for papers on a specific category and topic"""
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
            
            logger.info(f"Searching ArXiv with query: {search_query}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.arxiv_base_url, params=params) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        return await self._parse_arxiv_response(xml_content)
                    else:
                        logger.error(f"ArXiv API returned status {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error searching ArXiv: {e}")
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
                except:
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
    
    async def summarize_with_ollama(self, paper_content: str, paper_title: str) -> Optional[str]:
        """Summarize paper content using Ollama"""
        try:
            prompt = f"""请为这篇研究论文提供清晰简洁的总结。重点关注：
1. 主要研究问题或问题
2. 关键方法或途径
3. 主要发现或贡献
4. 实际意义或应用

总结应该便于一般学术读者理解，应该非常简短并保持重点，持在300字以内。**请用中文而不是英文撰写回答!**

论文标题：{paper_title}

论文内容：
{paper_content[:15000]}

再重申一次，请为这篇研究论文提供清晰简洁的总结。重点关注：
1. 主要研究问题或问题
2. 关键方法或途径
3. 主要发现或贡献
4. 实际意义或应用

总结应该便于一般学术读者理解，应该非常简短并保持重点，持在300字以内。**请用中文而不是英文撰写回答!**
"""

            payload = {
                "model": "deepseek-r1:32b",
                "prompt": prompt,
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.ollima_url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        summary = result.get('response', '')
                        
                        # Remove thinking tags if present
                        if '<think>' in summary:
                            import re
                            summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL)
                            summary = summary.strip()
                        
                        return summary
                    else:
                        logger.error(f"ollima API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error summarizing with ollama: {e}")
            return None
    
    async def check_ollama_service(self) -> bool:
        """Check if ollama service is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=5) as response:
                    if response.status == 200:
                        logger.info("ollima service is running")
                        return True
                    else:
                        logger.error("ollima service returned non-200 status")
                        return False
        except Exception as e:
            logger.error(f"ollima service check failed: {e}")
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

    async def summarize_and_push(self, category: str, topic: str, user_id: str = None, only_new: bool = False, is_scheduled: bool = False) -> Dict:
        """Main workflow for summarizing papers and pushing results"""
        try:
            logger.info(f"Starting summarization workflow for category: '{category}', topic: '{topic}' (user: {user_id}, only_new: {only_new}, scheduled: {is_scheduled})")
            
            # Search for papers
            logger.info(f"Searching ArXiv for papers in category '{category}' on topic: '{topic}'")
            papers = await self.search_arxiv(category, topic, max_results=10)
            if not papers:
                logger.warning(f"No papers found for category: '{category}', topic: '{topic}'")
                return {"success": False, "error": f"No papers found for category: {category}, topic: {topic}"}
            
            logger.info(f"Found {len(papers)} papers for category '{category}', topic '{topic}'")
            for i, paper in enumerate(papers, 1):
                logger.debug(f"Paper {i}: {paper['id']} - {paper['title'][:100]}...")
            
            # Check ollama service
            logger.info("Checking ollama service availability...")
            if not await self.check_ollama_service():
                logger.error("ollama service check failed")
                return {"success": False, "error": "olloma service is not running. Please ensure olloma serve is running."}
            
            summarized_papers = []
            processed_count = 0
            reused_count = 0
            
            for i, paper in enumerate(papers, 1):
                try:
                    paper_id = paper['id']
                    logger.info(f"Processing paper {i}/{len(papers)}: {paper_id}")
                    
                    # Different logic for scheduled vs instant requests
                    if is_scheduled:
                        # For scheduled runs: skip papers processed before today
                        if self._was_paper_processed_before_today(paper_id) and SUBSCRIPTION_ONLY_NEW:
                            logger.info(f"Skipping paper {paper_id} - processed before today")
                            continue
                        
                        # If processed, reuse the summary but still include in results
                        if self._is_paper_processed(paper_id):
                            logger.info(f"Paper {paper_id} processed - reusing summary")
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
                                logger.info(f"Reused today's summary for paper {paper_id}")
                                continue
                        
                        # If not processed at all, proceed to process
                    else:
                        # For instant requests: include all papers, but reuse summaries if available
                        if self._is_paper_processed(paper_id):
                            if only_new:
                                logger.info(f"Skipping already processed paper {paper_id} (only_new=True)")
                                continue
                            else:
                                logger.info(f"Loading existing summary for paper {paper_id} (only_new=False)")
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
                                    logger.info(f"Reused existing summary for paper {paper_id}")
                                    continue
                                else:
                                    logger.warning(f"Paper {paper_id} marked as processed but summary not found, reprocessing")
                    
                    # Download PDF
                    logger.debug(f"Step 1/3: Downloading PDF for paper {paper_id}")
                    pdf_path = await self.download_pdf(paper.get('pdf_url', ''), paper_id)
                    if not pdf_path:
                        logger.warning(f"Could not download PDF for paper {paper_id}, skipping")
                        continue
                    
                    # Convert to markdown
                    logger.debug(f"Step 2/3: Converting PDF to markdown for paper {paper_id}")
                    markdown_content = await self.pdf_to_markdown(pdf_path)
                    if not markdown_content:
                        logger.warning(f"Could not convert PDF to markdown for paper {paper_id}, skipping")
                        continue
                    
                    # Summarize with AI
                    logger.debug(f"Step 3/3: Generating AI summary for paper {paper_id}")
                    summary = await self.summarize_with_ollama(markdown_content, paper['title'])
                    if not summary:
                        logger.warning(f"Could not generate summary for paper {paper_id}, skipping")
                        continue
                    
                    # Save summary
                    logger.debug(f"Saving summary for paper {paper_id}")
                    await self._save_paper_summary(paper, summary)
                    
                    # Add to results
                    summarized_papers.append({
                        'title': paper['title'],
                        'authors': paper['authors'],
                        'summary': summary,
                        'pdf_url': paper.get('pdf_url', ''),
                        'categories': paper.get('categories', [])
                    })
                    
                    processed_count += 1
                    logger.info(f"Successfully processed paper {i}/{len(papers)}: {paper['title'][:50]}...")
                    
                    # Add small delay between papers to be nice to APIs
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing paper {paper.get('id', 'unknown')}: {e}")
                    logger.exception("Full traceback for paper processing error:")
                    continue
            
            logger.info(f"Processing complete: {processed_count} new papers processed, {reused_count} existing summaries reused")
            
            # Create and send embeds if we have papers
            if summarized_papers:
                logger.info(f"Creating and sending {len(summarized_papers)} embed messages")
                
                if user_id:
                    # Create header embed
                    header_embed = self._create_summary_header_embed(category, topic, len(summarized_papers), processed_count, reused_count, only_new)
                    
                    # Create individual paper embeds
                    paper_embeds = []
                    for i, paper in enumerate(summarized_papers, 1):
                        paper_embed = self._create_paper_embed(paper, i, len(summarized_papers), category, topic)
                        paper_embeds.append(paper_embed)
                    
                    # Combine all embeds (header + papers)
                    all_embeds = [header_embed] + paper_embeds
                    
                    # Send all embeds with intervals
                    logger.info(f"Sending {len(all_embeds)} embeds to user {user_id}")
                    await self._send_embeds_with_interval(user_id, all_embeds, interval=2.5)
                
                return {
                    "success": True,
                    "message": f"Found {len(summarized_papers)} papers for category '{category}', topic '{topic}' ({processed_count} newly processed, {reused_count} from cache)",
                    "papers_count": len(summarized_papers),
                    "new_papers": processed_count,
                    "cached_papers": reused_count,
                    "papers": summarized_papers
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
                    "value": "🤖 AI模型: **DeepSeek-R1-32B**\n📡 数据源: **ArXiv API**\n🔍 排序: **最新更新**",
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

        return f"✅ Successfully subscribed to '{topic}' in category '{category}'. You'll receive daily summaries at 7:00 AM."

    async def remove_subscription(self, user_id: str, category: str, topic: str) -> str:
        """Remove a topic subscription for a user"""
        subscriptions = self._cleanup_invalid_subscriptions()

        if user_id not in subscriptions:
            return f"❌ You have no subscriptions to remove."

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

🕰️ Daily summaries are sent at 7:00 AM
💡 Use `/subscribe add [category] [topic]` to add more subscriptions
📝 Use `/subscribe remove [category] [topic]` to remove subscriptions"""
    
    async def summarize_from_subscriptions(self):
        """Process all subscriptions (called by scheduler) - only send new papers and emails"""
        subscriptions = self._cleanup_invalid_subscriptions()
        email_targets = self._load_email_targets()
        
        logger.info(f"Starting scheduled subscription processing for {len(subscriptions)} Discord users and {len(email_targets)} email targets")
        
        # Phase 1: Process Discord subscriptions
        logger.info("Phase 1: Processing Discord subscriptions...")
        for user_id, user_subscriptions in subscriptions.items():
            for subscription in user_subscriptions:
                try:
                    category = subscription.get('category', 'all')
                    topic = subscription.get('topic', '')
                    
                    if not topic:
                        logger.warning(f"Skipping invalid subscription for user {user_id}: {subscription}")
                        continue
                    
                    logger.info(f"Processing Discord subscription: {category}/{topic} for user {user_id}")
                    # Use is_scheduled=True for scheduled subscriptions
                    result = await self.summarize_and_push(category, topic, user_id, only_new=SUBSCRIPTION_ONLY_NEW, is_scheduled=True)
                    
                    # Log the Discord result
                    if result.get('no_new_papers'):
                        logger.info(f"No new papers found for subscription {category}/{topic} for user {user_id}")
                    elif result['success']:
                        logger.info(f"Sent {result['papers_count']} papers to user {user_id} for {category}/{topic}")
                    else:
                        logger.error(f"Failed to process subscription {category}/{topic} for user {user_id}: {result.get('error')}")
                    
                    # Add delay between processing to avoid rate limits
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.error(f"Error processing Discord subscription {subscription} for user {user_id}: {e}")
                    continue
        
        # Phase 2: Process Email subscriptions
        logger.info("Phase 2: Processing Email subscriptions...")
        if email_targets:
            # Get all unique paper types from all email subscriptions
            all_paper_types = set()
            for email, paper_types in email_targets.items():
                all_paper_types.update(paper_types)
            
            logger.info(f"Found {len(all_paper_types)} unique paper types across all email subscriptions: {list(all_paper_types)}")
            
            # Process each unique paper type once and collect results
            paper_type_results = {}
            for paper_type in all_paper_types:
                try:
                    # Parse paper type (e.g., 'cs.ai' -> category='cs', topic='ai')
                    if '.' in paper_type:
                        category, topic = paper_type.split('.', 1)
                    else:
                        category = 'all'
                        topic = paper_type
                    
                    logger.info(f"Processing paper type: {category}/{topic}")
                    
                    # Get papers for this topic (scheduled mode)
                    result = await self.summarize_and_push(category, topic, user_id=None, only_new=SUBSCRIPTION_ONLY_NEW, is_scheduled=True)
                    
                    # Store result for this paper type
                    paper_type_results[paper_type] = {
                        'category': category,
                        'topic': topic,
                        'papers': result.get('papers', []),
                        'stats': {
                            'papers_count': len(result.get('papers', [])),
                            'new_papers': result.get('new_papers', 0),
                            'cached_papers': result.get('cached_papers', 0)
                        },
                        'success': result.get('success', False),
                        'no_new_papers': result.get('no_new_papers', False)
                    }
                    
                    logger.info(f"Paper type {paper_type}: {len(result.get('papers', []))} papers found")
                    
                    # Add delay between paper type processing
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing paper type {paper_type}: {e}")
                    paper_type_results[paper_type] = {
                        'category': category if 'category' in locals() else 'unknown',
                        'topic': topic if 'topic' in locals() else paper_type,
                        'papers': [],
                        'stats': {'papers_count': 0, 'new_papers': 0, 'cached_papers': 0},
                        'success': False,
                        'error': str(e)
                    }
                    continue
            
            # Now send emails to each email address based on their subscriptions
            for email, subscribed_paper_types in email_targets.items():
                if not subscribed_paper_types:
                    logger.info(f"Skipping email {email} - no paper types configured")
                    continue
                
                logger.info(f"Processing email subscriptions for {email}: {subscribed_paper_types}")
                
                for paper_type in subscribed_paper_types:
                    try:
                        # Get the processed result for this paper type
                        if paper_type not in paper_type_results:
                            logger.warning(f"Paper type {paper_type} not found in results for {email}")
                            continue
                        
                        result_data = paper_type_results[paper_type]
                        
                        # Skip if no papers found or processing failed
                        if not result_data['success'] or not result_data['papers']:
                            if result_data.get('no_new_papers'):
                                logger.info(f"No new papers for {paper_type} for email {email}")
                            else:
                                logger.warning(f"No papers or failed processing for {paper_type} for email {email}")
                            continue
                        
                        # Send email for this specific paper type
                        logger.info(f"Sending email for {paper_type} to {email} with {len(result_data['papers'])} papers")
                        
                        email_result = await self.email_service.send_paper_summary_email(
                            to_emails=[email],
                            category=result_data['category'],
                            topic=result_data['topic'],
                            papers=result_data['papers'],
                            stats=result_data['stats']
                        )
                        
                        if email_result['success']:
                            logger.info(f"Email sent successfully for {paper_type} to {email}: {len(result_data['papers'])} papers")
                        else:
                            logger.error(f"Failed to send email for {paper_type} to {email}: {email_result.get('error')}")
                        
                        # Add delay between emails to avoid overwhelming email servers
                        await asyncio.sleep(5)
                        
                    except Exception as e:
                        logger.error(f"Error sending email for {paper_type} to {email}: {e}")
                        continue
                
                # Add delay between different email addresses
                await asyncio.sleep(10)
        else:
            logger.info("No email targets configured, skipping email phase")
        
        logger.info("Scheduled subscription processing completed")

    async def start_scheduler(self):
        """Start the daily scheduler for subscriptions"""
        logger.info("Starting subscription scheduler")
        
        max_consecutive_errors = 5
        consecutive_errors = 0
        
        while True:
            try:
                now = datetime.now()
                target_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
                
                # If it's past 7 AM today, schedule for tomorrow
                if now.time() > time(7, 0):
                    target_time = target_time.replace(day=target_time.day + 1)
                
                # Calculate sleep time
                sleep_seconds = (target_time - now).total_seconds()
                logger.info(f"Next subscription run scheduled for: {target_time}")
                
                await asyncio.sleep(sleep_seconds)
                
                # Run the subscription processing
                logger.info("Starting daily subscription processing")
                await self.summarize_from_subscriptions()
                logger.info("Daily subscription processing completed")
                
                # Reset error counter on successful run
                consecutive_errors = 0
                
            except asyncio.CancelledError:
                logger.info("Subscription scheduler cancelled")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in scheduler (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Scheduler failed {max_consecutive_errors} consecutive times, giving up")
                    from ..apps import CeciliaServiceError
                    raise CeciliaServiceError(f"Subscription scheduler failed repeatedly: {e}")
                
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)
