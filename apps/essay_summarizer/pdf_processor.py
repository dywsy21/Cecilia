"""PDF processing utilities for downloading and converting papers"""
import asyncio
import aiohttp
import aiofiles
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def is_valid_pdf(pdf_path: Path) -> bool:
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

async def download_pdf(pdf_url: str, paper_id: str, output_dir: Path) -> Optional[Path]:
    """Download PDF file from ArXiv with timeout and retry logic"""
    pdf_path = output_dir / f"{paper_id}.pdf"
    try:
        # Check if already downloaded and valid
        if pdf_path.exists() and is_valid_pdf(pdf_path):
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
                            if is_valid_pdf(pdf_path):
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
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
        return None

async def pdf_to_markdown(pdf_path: Path) -> Optional[str]:
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
