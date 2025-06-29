import asyncio
import aiohttp
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class EssaySummarizer:
    """Handles essay summarization from ArXiv"""
    
    def __init__(self):
        self.arxiv_base_url = "http://export.arxiv.org/api/query"
        logger.info("EssaySummarizer initialized")
    
    async def search_arxiv(self, topic: str, max_results: int = 5) -> List[Dict]:
        """
        Search ArXiv for papers on a specific topic
        
        Args:
            topic (str): The research topic to search for
            max_results (int): Maximum number of results to return
            
        Returns:
            List[Dict]: List of paper information
        """
        try:
            # Format search query
            search_query = f"all:{topic}"
            params = {
                'search_query': search_query,
                'start': 0,
                'max_results': max_results,
                'sortBy': 'lastUpdatedDate',
                'sortOrder': 'descending'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.arxiv_base_url, params=params) as response:
                    if response.status == 200:
                        # For now, return a mock response
                        # In a real implementation, you'd parse the XML response
                        return await self._parse_arxiv_response(await response.text(), topic)
                    else:
                        logger.error(f"ArXiv API returned status {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error searching ArXiv: {e}")
            return []
    
    async def _parse_arxiv_response(self, xml_content: str, topic: str) -> List[Dict]:
        """Parse XML response from ArXiv API"""
        # This is a simplified mock implementation
        # In reality, you'd use xml.etree.ElementTree or similar to parse the XML
        mock_papers = [
            {
                "title": f"Recent Advances in {topic.title()}",
                "authors": ["Dr. Smith", "Dr. Johnson"],
                "abstract": f"This paper discusses recent developments in {topic} research...",
                "url": "https://arxiv.org/abs/2024.00001"
            },
            {
                "title": f"A Comprehensive Survey of {topic.title()} Methods",
                "authors": ["Prof. Wilson", "Dr. Brown"],
                "abstract": f"We present a comprehensive survey of current {topic} methodologies...",
                "url": "https://arxiv.org/abs/2024.00002"
            }
        ]
        return mock_papers
    
    async def summarize_topic(self, topic: str) -> str:
        """
        Summarize recent papers on a given topic
        
        Args:
            topic (str): The research topic to summarize
            
        Returns:
            str: Formatted summary of papers
        """
        try:
            papers = await self.search_arxiv(topic, max_results=5)
            
            if not papers:
                return f"No recent papers found for topic: '{topic}'"
            
            summary = f"📚 **Recent Papers on '{topic.title()}'**\n\n"
            
            for i, paper in enumerate(papers, 1):
                authors_str = ", ".join(paper['authors'][:3])  # Show first 3 authors
                if len(paper['authors']) > 3:
                    authors_str += " et al."
                
                summary += f"**{i}. {paper['title']}**\n"
                summary += f"*Authors*: {authors_str}\n"
                summary += f"*Abstract*: {paper['abstract'][:200]}...\n"
                summary += f"*Link*: {paper['url']}\n\n"
            
            summary += f"✨ Found {len(papers)} recent papers on {topic}!"
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing topic {topic}: {e}")
            return f"Error occurred while summarizing papers for '{topic}': {str(e)}"
