"""ArXiv client for searching and parsing papers"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

async def search_arxiv(category: str, topic: str, max_results: int = 10) -> List[Dict]:
    """Search for papers on a specific category and topic with retry logic"""
    arxiv_base_url = "https://export.arxiv.org/api/query"
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
                async with session.get(arxiv_base_url, params=params) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        papers = await parse_arxiv_response(xml_content)
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

async def parse_arxiv_response(xml_content: str) -> List[Dict]:
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
            
            # Extract basic info with null checks
            id_elem = entry.find('atom:id', ns)
            title_elem = entry.find('atom:title', ns)
            summary_elem = entry.find('atom:summary', ns)
            updated_elem = entry.find('atom:updated', ns)
            published_elem = entry.find('atom:published', ns)
            
            if id_elem is not None and id_elem.text:
                paper['id'] = id_elem.text.split('/')[-1]
            else:
                continue  # Skip entries without ID
                
            if title_elem is not None and title_elem.text:
                paper['title'] = title_elem.text.strip()
            else:
                paper['title'] = "Untitled"
                
            if summary_elem is not None and summary_elem.text:
                paper['summary'] = summary_elem.text.strip()
            else:
                paper['summary'] = "No summary available"
                
            if updated_elem is not None and updated_elem.text:
                paper['updated'] = updated_elem.text
            else:
                paper['updated'] = ""
                
            if published_elem is not None and published_elem.text:
                paper['published'] = published_elem.text
            else:
                paper['published'] = ""
            
            # Extract authors
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text)
            paper['authors'] = authors
            
            # Extract PDF link
            paper['pdf_url'] = ""
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'pdf':
                    paper['pdf_url'] = link.get('href', '')
                    break
            
            # Extract categories
            categories = []
            for category in entry.findall('atom:category', ns):
                term = category.get('term')
                if term:
                    categories.append(term)
            paper['categories'] = categories
            
            papers.append(paper)
        
        return papers
        
    except Exception as e:
        logger.error(f"Error parsing ArXiv XML: {e}")
        return []
