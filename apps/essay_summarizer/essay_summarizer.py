import asyncio
import aiohttp
import aiofiles
import json
import logging
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, time
from pathlib import Path
from typing import List, Dict, Optional
import hashlib

logger = logging.getLogger(__name__)

class EssaySummarizer:
    """Handles essay summarization from ArXiv with subscription management"""
    
    def __init__(self):
        self.arxiv_base_url = "https://export.arxiv.org/api/query"
        self.ollama_url = "http://localhost:11434/api/generate"
        self.data_dir = Path("data/essay_summarizer")
        self.subscriptions_file = self.data_dir / "subscriptions.json"
        self.processed_papers_dir = self.data_dir / "processed"
        self.summaries_dir = self.data_dir / "summaries"
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_papers_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize subscriptions file if it doesn't exist
        if not self.subscriptions_file.exists():
            self._save_subscriptions({})
        
        self.app_manager = None  # Will be set by AppManager
        logger.info("EssaySummarizer initialized")
    
    def set_app_manager(self, app_manager):
        """Set reference to AppManager for message pushing"""
        self.app_manager = app_manager
    
    async def search_arxiv(self, topic: str, max_results: int = 10) -> List[Dict]:
        """Search ArXiv for papers on a specific topic"""
        try:
            params = {
                'search_query': f'all:{topic}',
                'sortBy': 'lastUpdatedDate',
                'sortOrder': 'descending',
                'start': 0,
                'max_results': max_results
            }
            
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
    
    async def download_pdf(self, pdf_url: str, paper_id: str) -> Optional[Path]:
        """Download PDF file from ArXiv"""
        try:
            pdf_path = self.processed_papers_dir / f"{paper_id}.pdf"
            
            # Check if already downloaded
            if pdf_path.exists():
                return pdf_path
            
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url) as response:
                    if response.status == 200:
                        async with aiofiles.open(pdf_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        logger.info(f"Downloaded PDF: {pdf_path}")
                        return pdf_path
                    else:
                        logger.error(f"Failed to download PDF: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
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

总结应该便于一般学术读者理解，保持在300字以内。

论文标题：{paper_title}

论文内容：
{paper_content[:18000]}"""

            payload = {
                "model": "deepseek-r1:32b",
                "prompt": prompt,
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.ollama_url, json=payload) as response:
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
                        logger.error(f"Ollama API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error summarizing with Ollama: {e}")
            return None
    
    async def check_ollama_service(self) -> bool:
        """Check if Ollama service is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=5) as response:
                    if response.status == 200:
                        logger.info("Ollama service is running")
                        return True
                    else:
                        logger.error("Ollama service returned non-200 status")
                        return False
        except Exception as e:
            logger.error(f"Ollama service check failed: {e}")
            return False
    
    def _get_paper_hash(self, paper_id: str) -> str:
        """Get hash for paper to check if already processed"""
        return hashlib.md5(paper_id.encode()).hexdigest()
    
    def _is_paper_processed(self, paper_id: str) -> bool:
        """Check if paper has been processed before"""
        paper_hash = self._get_paper_hash(paper_id)
        summary_file = self.summaries_dir / f"{paper_hash}.json"
        return summary_file.exists()
    
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

    async def summarize_and_push(self, topic: str, user_id: str = None) -> Dict:
        """Main workflow for summarizing papers and pushing results"""
        try:
            logger.info(f"Starting summarization workflow for topic: '{topic}' (user: {user_id})")
            
            # Search for papers
            logger.info(f"Searching ArXiv for papers on topic: '{topic}'")
            papers = await self.search_arxiv(topic, max_results=10)
            if not papers:
                logger.warning(f"No papers found for topic: '{topic}'")
                return {"success": False, "error": f"No papers found for topic: {topic}"}
            
            logger.info(f"Found {len(papers)} papers for topic '{topic}'")
            for i, paper in enumerate(papers, 1):
                logger.debug(f"Paper {i}: {paper['id']} - {paper['title'][:100]}...")
            
            # Check Ollama service
            logger.info("Checking Ollama service availability...")
            if not await self.check_ollama_service():
                logger.error("Ollama service check failed")
                return {"success": False, "error": "Ollama service is not running. Please ensure ollama serve is running."}
            
            summarized_papers = []
            processed_count = 0
            reused_count = 0
            
            for i, paper in enumerate(papers, 1):
                try:
                    paper_id = paper['id']
                    logger.info(f"Processing paper {i}/{len(papers)}: {paper_id}")
                    
                    # Check if already processed
                    if self._is_paper_processed(paper_id):
                        logger.info(f"Paper {paper_id} already processed, loading existing summary")
                        existing_summary = await self._load_existing_summary(paper_id)
                        
                        if existing_summary:
                            # Add existing summary to results
                            summarized_papers.append({
                                'title': existing_summary['title'],
                                'authors': existing_summary['authors'][:3],  # Limit authors
                                'summary': existing_summary['summary'],
                                'pdf_url': existing_summary.get('pdf_url', ''),
                                'categories': existing_summary.get('categories', [])[:3]  # Limit categories
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
                        'authors': paper['authors'][:3],  # Limit authors
                        'summary': summary,
                        'pdf_url': paper.get('pdf_url', ''),
                        'categories': paper.get('categories', [])[:3]  # Limit categories
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
            
            # Create Discord message - now always create if we have any papers (new or existing)
            if summarized_papers:
                logger.info(f"Creating Discord message for {len(summarized_papers)} papers")
                message_data = self._create_summary_message(topic, summarized_papers, processed_count, reused_count)
                
                # Send via message pusher if user_id provided
                if user_id and self.app_manager and self.app_manager.msg_pusher:
                    logger.info(f"Sending results to user {user_id} via message pusher")
                    push_data = {
                        "user_id": str(user_id),
                        "message": message_data
                    }
                    push_result = await self.app_manager.msg_pusher.process_message(push_data)
                    logger.debug(f"Message pusher result: {push_result}")
                
                return {
                    "success": True,
                    "message": f"Found {len(summarized_papers)} papers for topic '{topic}' ({processed_count} newly processed, {reused_count} from cache)",
                    "papers_count": len(summarized_papers),
                    "new_papers": processed_count,
                    "cached_papers": reused_count
                }
            else:
                logger.info(f"No papers could be processed for topic '{topic}'")
                return {
                    "success": False,
                    "error": f"No papers could be processed for topic '{topic}' - all papers failed processing",
                    "papers_count": 0
                }
                
        except Exception as e:
            logger.error(f"Error in summarize_and_push for topic '{topic}': {e}")
            logger.exception("Full traceback for summarize_and_push error:")
            return {"success": False, "error": str(e)}
    
    def _create_summary_message(self, topic: str, papers: List[Dict], new_count: int = 0, cached_count: int = 0) -> Dict:
        """Create a Discord message with paper summaries"""
        # Create description with processing stats
        if new_count > 0 and cached_count > 0:
            description = f"Found {len(papers)} papers ({new_count} newly processed, {cached_count} from cache):"
        elif new_count > 0:
            description = f"Found {len(papers)} papers (all newly processed):"
        elif cached_count > 0:
            description = f"Found {len(papers)} papers (all from cache):"
        else:
            description = f"Found {len(papers)} papers:"
        
        embed = {
            "title": f"📚 Latest Research on '{topic.title()}'",
            "description": description,
            "color": "#1f8b4c",
            "fields": [],
            "footer": {
                "text": f"Cecilia Research Assistant • Processed at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }
        
        for i, paper in enumerate(papers, 1):
            authors_str = ", ".join(paper['authors'])
            if len(paper['authors']) > 3:
                authors_str += " et al."
            
            field_value = f"**Authors:** {authors_str}\n"
            field_value += f"**Categories:** {', '.join(paper['categories'])}\n"
            field_value += f"**Summary:** {paper['summary']}\n"
            field_value += f"[📄 Read Paper]({paper['pdf_url']})"
            
            embed["fields"].append({
                "name": f"{i}. {paper['title'][:100]}{'...' if len(paper['title']) > 100 else ''}",
                "value": field_value,
                "inline": False
            })
        
        return {"embed": embed}
    
    async def instantly_summarize_and_push(self, topic: str, user_id: str) -> Dict:
        """Instantly summarize papers for a topic and push to user"""
        result = await self.summarize_and_push(topic, user_id)
        return result
    
    # Subscription Management
    def _load_subscriptions(self) -> Dict[str, List[str]]:
        """Load subscriptions from disk"""
        try:
            with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading subscriptions: {e}")
            return {}
    
    def _save_subscriptions(self, subscriptions: Dict[str, List[str]]):
        """Save subscriptions to disk"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(subscriptions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving subscriptions: {e}")
    
    async def add_subscription(self, user_id: str, topic: str) -> str:
        """Add a topic subscription for a user"""
        subscriptions = self._load_subscriptions()
        
        if user_id not in subscriptions:
            subscriptions[user_id] = []
        
        if topic.lower() in [t.lower() for t in subscriptions[user_id]]:
            return f"❌ You're already subscribed to '{topic}'"
        
        subscriptions[user_id].append(topic)
        self._save_subscriptions(subscriptions)
        
        return f"✅ Successfully subscribed to '{topic}'. You'll receive daily summaries at 7:00 AM."
    
    async def remove_subscription(self, user_id: str, topic: str) -> str:
        """Remove a topic subscription for a user"""
        subscriptions = self._load_subscriptions()
        
        if user_id not in subscriptions:
            return f"❌ You have no subscriptions to remove."
        
        # Find and remove topic (case insensitive)
        original_topics = subscriptions[user_id][:]
        subscriptions[user_id] = [t for t in subscriptions[user_id] if t.lower() != topic.lower()]
        
        if len(subscriptions[user_id]) == len(original_topics):
            return f"❌ You're not subscribed to '{topic}'"
        
        self._save_subscriptions(subscriptions)
        return f"✅ Successfully unsubscribed from '{topic}'"
    
    async def list_subscriptions(self, user_id: str) -> str:
        """List all subscriptions for a user"""
        subscriptions = self._load_subscriptions()
        
        if user_id not in subscriptions or not subscriptions[user_id]:
            return "📝 You have no active subscriptions.\nUse `/subscribe add [topic]` to add a subscription!"
        
        topics = subscriptions[user_id]
        topics_list = "\n".join([f"• {topic}" for topic in topics])
        
        return f"📚 **Your Research Subscriptions:**\n{topics_list}\n\n🕰️ Daily summaries are sent at 7:00 AM"
    
    async def summarize_from_subscriptions(self):
        """Process all subscriptions (called by scheduler)"""
        subscriptions = self._load_subscriptions()
        
        for user_id, topics in subscriptions.items():
            for topic in topics:
                try:
                    logger.info(f"Processing subscription: {topic} for user {user_id}")
                    await self.summarize_and_push(topic, user_id)
                    # Add delay between processing to avoid rate limits
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Error processing subscription {topic} for user {user_id}: {e}")
                    continue
    
    async def start_scheduler(self):
        """Start the daily scheduler for subscriptions"""
        logger.info("Starting subscription scheduler")
        
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
                
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)
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
                
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)
                # Sleep for an hour before retrying
                await asyncio.sleep(3600)
