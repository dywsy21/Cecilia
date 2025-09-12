"""Data management utilities for persistence and file operations"""
import json
import aiofiles
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def get_paper_hash(paper_id: str) -> str:
    """Get hash for paper to check if already processed"""
    return hashlib.md5(paper_id.encode()).hexdigest()

def is_paper_processed(paper_id: str, summaries_dir: Path) -> bool:
    """Check if paper has been processed before"""
    paper_hash = get_paper_hash(paper_id)
    summary_file = summaries_dir / f"{paper_hash}.json"
    return summary_file.exists()

def is_paper_processed_today(paper_id: str, summaries_dir: Path) -> bool:
    """Check if paper was processed today"""
    paper_hash = get_paper_hash(paper_id)
    summary_file = summaries_dir / f"{paper_hash}.json"
    
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

def was_paper_processed_before_today(paper_id: str, summaries_dir: Path) -> bool:
    """Check if paper was processed before today (not including today)"""
    paper_hash = get_paper_hash(paper_id)
    summary_file = summaries_dir / f"{paper_hash}.json"
    
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

async def save_paper_summary(paper: Dict, summary: str, summaries_dir: Path):
    """Save paper summary to disk"""
    paper_hash = get_paper_hash(paper['id'])
    summary_file = summaries_dir / f"{paper_hash}.json"
    
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

async def load_existing_summary(paper_id: str, summaries_dir: Path) -> Optional[Dict]:
    """Load existing summary for a paper"""
    try:
        paper_hash = get_paper_hash(paper_id)
        summary_file = summaries_dir / f"{paper_hash}.json"
        
        if summary_file.exists():
            async with aiofiles.open(summary_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        return None
    except Exception as e:
        logger.error(f"Error loading existing summary for {paper_id}: {e}")
        return None

def load_email_targets(email_targets_file: Path) -> Dict[str, List[str]]:
    """Load email targets from disk with new format: {email: [categories]}"""
    try:
        with open(email_targets_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Handle migration from old format (list of strings) to new format (dict)
            if isinstance(data, list):
                logger.info("Migrating email_targets.json from old format to new format")
                # Convert old format to new format with empty subscriptions
                new_data = {email: [] for email in data}
                save_email_targets(new_data, email_targets_file)
                return new_data
            
            return data
    except Exception as e:
        logger.error(f"Error loading email targets: {e}")
        return {}

def save_email_targets(email_targets: Dict[str, List[str]], email_targets_file: Path):
    """Save email targets to disk"""
    try:
        with open(email_targets_file, 'w', encoding='utf-8') as f:
            json.dump(email_targets, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving email targets: {e}")

def load_subscriptions(subscriptions_file: Path) -> Dict[str, List[Dict]]:
    """Load subscriptions from disk"""
    try:
        with open(subscriptions_file, 'r', encoding='utf-8') as f:
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
                save_subscriptions(data, subscriptions_file)
                logger.info("Subscription migration completed")
            
            return data
    except Exception as e:
        logger.error(f"Error loading subscriptions: {e}")
        return {}

def save_subscriptions(subscriptions: Dict[str, List[Dict]], subscriptions_file: Path):
    """Save subscriptions to disk"""
    try:
        with open(subscriptions_file, 'w', encoding='utf-8') as f:
            json.dump(subscriptions, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving subscriptions: {e}")

def cleanup_invalid_subscriptions(subscriptions_file: Path) -> Dict[str, List[Dict]]:
    """Clean up invalid subscription records"""
    try:
        subscriptions = load_subscriptions(subscriptions_file)
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
            save_subscriptions(subscriptions, subscriptions_file)
            logger.info("Subscription cleanup completed")
        
        return subscriptions
    except Exception as e:
        logger.error(f"Error during subscription cleanup: {e}")
        return {}

def get_daily_results_file(base_dir: Path) -> Path:
    """Get path for today's daily results file"""
    today = datetime.now().strftime('%Y-%m-%d')
    return base_dir / f"daily_results_{today}.json"

async def save_daily_results(results: Dict, base_dir: Path):
    """Save daily summarization results for later notification"""
    try:
        results_file = get_daily_results_file(base_dir)
        
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

async def load_daily_results(base_dir: Path) -> Dict:
    """Load today's daily results for notification"""
    try:
        results_file = get_daily_results_file(base_dir)
        
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

async def cleanup_old_results(base_dir: Path):
    """Clean up results files older than 8 days"""
    try:
        cutoff_date = datetime.now() - timedelta(days=8)
        
        for file_path in base_dir.glob("daily_results_*.json"):
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
