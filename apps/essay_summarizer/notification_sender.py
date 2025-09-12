"""Notification sender for Discord and email messages"""
import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

def truncate_text(text: str, max_length: int) -> str:
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

def get_paper_color(index: int) -> str:
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

def create_paper_embed(paper: Dict, index: int, total_count: int, category: str, topic: str) -> Dict:
    """Create individual embed for a single paper with full utilization of embed limits"""
    
    # Prepare authors string with Discord field limit (1024 chars)
    authors_str = ", ".join(paper['authors']) if paper['authors'] else ""
    if len(authors_str) > 1024:  # Discord field value limit
        authors_str = truncate_text(authors_str, 1021)  # Leave space for "..."
    
    # Prepare categories string with Discord field limit (1024 chars)
    categories_str = ", ".join(paper['categories']) if paper['categories'] else ""
    if len(categories_str) > 1024:  # Discord field value limit
        categories_str = truncate_text(categories_str, 1021)  # Leave space for "..."
    
    # Truncate title for embed title (Discord limit: 256 chars)
    title = paper['title']
    if len(title) > 256:
        title = truncate_text(title, 253)  # Leave space for "..."
    
    # Use full 4096 character limit for description with the AI summary
    description = f"**论文总结：**\n\n{paper['summary']}"
    
    # Check if description exceeds Discord's limit and truncate if needed
    if len(description) > 4096:
        # Calculate available space for summary (4096 - "**论文总结：**\n\n" - "...")
        header_text = "**论文总结：**\n\n"
        ellipsis = "..."
        available_space = 4096 - len(header_text) - len(ellipsis)
        
        # Truncate summary at word boundary
        truncated_summary = truncate_text(paper['summary'], available_space)
        description = f"{header_text}{truncated_summary}"
        
        # If still too long (shouldn't happen), force truncate
        if len(description) > 4096:
            description = description[:4093] + "..."
    
    # Create rich embed with visual appeal
    embed = {
        "title": f"📄 {title}",
        "description": description,
        "color": get_paper_color(index),
        "fields": [
            {
                "name": "👥 作者",
                "value": authors_str if authors_str else "未知作者",
                "inline": False
            },
            {
                "name": "🏷️ 分类", 
                "value": categories_str if categories_str else "未分类",
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
    }
    
    return embed


def create_summary_header_embed(category: str, topic: str, total_papers: int, new_count: int, cached_count: int, model_name: str, only_new: bool = False) -> Dict:
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
                "value": f"🤖 AI模型: **{model_name}**\n📡 数据源: **ArXiv API**\n🔍 排序: **最新更新**",
                "inline": True
            }
        ],
        "footer": {
            "text": "Cecilia 研究助手 • 基于最新 ArXiv 数据"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return embed

async def send_message_via_api(user_id: str, message_data: Dict) -> Dict:
    """Send message via HTTP API to message pusher"""
    try:
        url = "http://localhost:8011/push"
        headers = {"Content-Type": "application/json"}
        payload = {
            "user_id": str(user_id),
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

async def send_embeds_with_interval(user_id: str, embeds: List[Dict], interval: float = 2.0):
    """Send multiple embeds with time intervals to avoid rate limits"""
    
    for i, embed in enumerate(embeds):
        try:
            message_data = {"embed": embed}
            api_result = await send_message_via_api(user_id, message_data)
            
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
