import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging
import re
import markdown
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from bot.auths import (
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_SECURE,
    EMAIL_SMTP_USER, EMAIL_SMTP_PASS, EMAIL_SMTP_NAME,
    EMAIL_SMTP_LOGGER, EMAIL_SMTP_TLS_REJECT_UNAUTH,
    EMAIL_SMTP_IGNORE_TLS, CUSTOM_EMAIL_FOOTER
)

logger = logging.getLogger(__name__)

class EmailService:
    """Handles email operations for essay summarizer"""
    
    def __init__(self):
        self.smtp_host = EMAIL_SMTP_HOST
        self.smtp_port = EMAIL_SMTP_PORT
        self.smtp_secure = EMAIL_SMTP_SECURE
        self.smtp_user = EMAIL_SMTP_USER
        self.smtp_pass = EMAIL_SMTP_PASS
        self.smtp_name = EMAIL_SMTP_NAME
        self.smtp_logger = EMAIL_SMTP_LOGGER
        self.tls_reject_unauth = EMAIL_SMTP_TLS_REJECT_UNAUTH
        self.ignore_tls = EMAIL_SMTP_IGNORE_TLS
        self.custom_footer = CUSTOM_EMAIL_FOOTER
        
        if self.smtp_logger:
            logging.getLogger('email').setLevel(logging.DEBUG)
    
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        required_fields = [self.smtp_host, self.smtp_user, self.smtp_pass]
        if not all(required_fields):
            logger.error("Email configuration incomplete")
            return False
        return True
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage"""
        # Remove or replace invalid characters for file names
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove excessive whitespace and limit length
        filename = re.sub(r'\s+', ' ', filename).strip()
        # Limit filename length (keeping some buffer for extension)
        if len(filename) > 200:
            filename = filename[:200] + "..."
        return filename
    
    def _get_paper_pdf_path(self, paper_url: str) -> Optional[Path]:
        """Get the PDF path for a paper from its ArXiv URL"""
        try:
            # Extract paper ID from URL (e.g., "http://arxiv.org/pdf/2101.00001v1" -> "2101.00001v1")
            if 'arxiv.org/pdf/' in paper_url:
                paper_id = paper_url.split('arxiv.org/pdf/')[-1]
                if paper_id.endswith('.pdf'):
                    paper_id = paper_id[:-4]
            else:
                # Handle other URL formats
                paper_id = paper_url.split('/')[-1]
                if paper_id.endswith('.pdf'):
                    paper_id = paper_id[:-4]
            
            # Look for the PDF in the processed papers directory
            processed_papers_dir = Path("data/essay_summarizer/processed")
            pdf_path = processed_papers_dir / f"{paper_id}.pdf"
            
            if pdf_path.exists():
                return pdf_path
            else:
                logger.warning(f"PDF not found for paper: {paper_id} at {pdf_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting PDF path for {paper_url}: {e}")
            return None
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """Convert markdown text to HTML"""
        try:
            # Use markdown library to convert markdown to HTML
            html = markdown.markdown(markdown_text, extensions=['nl2br', 'tables', 'fenced_code'])
            return html
        except Exception as e:
            logger.warning(f"Error converting markdown to HTML: {e}")
            # Fallback to simple text conversion
            return markdown_text.replace('\n', '<br>')
    
    async def send_paper_summary_email(self, 
                                     to_emails: List[str], 
                                     category: str, 
                                     topic: str, 
                                     papers: List[Dict], 
                                     stats: Dict) -> Dict:
        """Send paper summary email to multiple recipients with PDF attachments"""
        if not self._validate_config():
            return {"success": False, "error": "Email configuration is incomplete"}
        
        try:
            subject = f"Cecilia 研究推送: {category}.{topic} - {len(papers)}篇论文 ({datetime.now().strftime('%m月%d日')})"
            
            msg = MIMEMultipart('mixed')  # Changed to 'mixed' for attachments
            msg['Subject'] = subject
            msg['From'] = f"{self.smtp_name} <{self.smtp_user}>" if self.smtp_name else self.smtp_user
            msg['To'] = ', '.join(to_emails)
            
            # Add PDF attachments first and track size
            attached_count = 0
            removed_attachments = 0
            total_size = 0
            max_size_mb = 45
            max_size_bytes = max_size_mb * 1024 * 1024  # 50MB in bytes
            
            attachments = []
            
            for i, paper in enumerate(papers, 1):
                try:
                    pdf_url = paper.get('pdf_url', '')
                    if not pdf_url:
                        logger.warning(f"No PDF URL for paper {i}: {paper.get('title', 'Unknown')}")
                        continue
                    
                    pdf_path = self._get_paper_pdf_path(pdf_url)
                    if not pdf_path:
                        logger.warning(f"PDF file not found for paper {i}: {paper.get('title', 'Unknown')}")
                        continue
                    
                    # Check file size
                    try:
                        file_size = pdf_path.stat().st_size
                    except Exception as e:
                        logger.warning(f"Could not get file size for {pdf_path}: {e}")
                        continue
                    
                    # Check if adding this attachment would exceed the limit
                    if total_size + file_size > max_size_bytes:
                        logger.info(f"Skipping attachment {i} to keep email size under {max_size_mb}MB")
                        removed_attachments += 1
                        continue
                    
                    # Create sanitized filename with paper number and title
                    paper_title = paper.get('title', 'Unknown Paper')
                    sanitized_title = self._sanitize_filename(paper_title)
                    attachment_filename = f"{i}. {sanitized_title}.pdf"
                    
                    # Read and attach the PDF
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_data = pdf_file.read()
                    
                    pdf_attachment = MIMEApplication(pdf_data, _subtype='pdf')
                    pdf_attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=attachment_filename
                    )
                    
                    attachments.append(pdf_attachment)
                    total_size += file_size
                    attached_count += 1
                    logger.info(f"Attached PDF {i}: {attachment_filename} ({file_size / 1024 / 1024:.1f}MB)")
                    
                except Exception as e:
                    logger.error(f"Error attaching PDF for paper {i} ({paper.get('title', 'Unknown')}): {e}")
                    continue
            
            # Create HTML content with size warning if needed
            html_content = self._create_email_html(category, topic, papers, stats, removed_attachments)
            
            # Create the main email body
            body_part = MIMEMultipart('alternative')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            body_part.attach(html_part)
            msg.attach(body_part)
            
            # Add all approved attachments
            for attachment in attachments:
                msg.attach(attachment)
            
            # Send the email
            if self.smtp_secure:
                context = ssl.create_default_context()
                if self.ignore_tls:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                elif not self.tls_reject_unauth:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_OPTIONAL
                
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    if self.smtp_logger:
                        server.set_debuglevel(1)
                    server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_logger:
                        server.set_debuglevel(1)
                    
                    if not self.ignore_tls:
                        context = ssl.create_default_context()
                        if not self.tls_reject_unauth:
                            context.check_hostname = False
                            context.verify_mode = ssl.CERT_OPTIONAL
                        server.starttls(context=context)
                    
                    server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
            
            size_warning = f" (removed {removed_attachments} attachments due to size limit)" if removed_attachments > 0 else ""
            logger.info(f"Email sent successfully to {len(to_emails)} recipients for {category}.{topic} with {attached_count} PDF attachments{size_warning}")
            
            return {
                "success": True, 
                "message": f"Email sent to {len(to_emails)} recipients with {attached_count} PDF attachments{size_warning}",
                "recipients": to_emails,
                "subject": subject,
                "attachments": attached_count,
                "removed_attachments": removed_attachments,
                "total_size_mb": round(total_size / 1024 / 1024, 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}

    def _create_email_html(self, category: str, topic: str, papers: List[Dict], stats: Dict, removed_attachments: int = 0) -> str:
        """Create HTML email content for paper summaries with size warning if needed"""
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .stats {{ background: #f8f9fa; padding: 20px; border-left: 4px solid #667eea; margin: 20px; border-radius: 5px; }}
                .stats h3 {{ margin-top: 0; color: #667eea; }}
                .size-warning {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px; border-radius: 5px; color: #856404; }}
                .size-warning h4 {{ margin-top: 0; color: #856404; }}
                .paper {{ margin: 20px; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa; }}
                .paper-title {{ color: #2c3e50; font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .paper-authors {{ color: #7f8c8d; font-size: 14px; margin-bottom: 10px; }}
                .paper-categories {{ background: #ecf0f1; padding: 5px 10px; border-radius: 15px; font-size: 12px; color: #2c3e50; display: inline-block; margin-bottom: 15px; }}
                .paper-summary {{ margin: 15px 0; line-height: 1.8; }}
                .paper-summary h1, .paper-summary h2, .paper-summary h3 {{ color: #2c3e50; margin-top: 20px; margin-bottom: 10px; }}
                .paper-summary h1 {{ font-size: 1.2em; }}
                .paper-summary h2 {{ font-size: 1.1em; }}
                .paper-summary h3 {{ font-size: 1.05em; }}
                .paper-summary ul, .paper-summary ol {{ margin: 10px 0; padding-left: 20px; }}
                .paper-summary li {{ margin: 5px 0; }}
                .paper-summary strong {{ color: #2c3e50; }}
                .paper-summary em {{ font-style: italic; color: #555; }}
                .paper-summary code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: 'Courier New', monospace; }}
                .paper-summary blockquote {{ border-left: 3px solid #ddd; margin: 15px 0; padding-left: 15px; color: #666; }}
                .paper-link {{ background: #3498db; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; font-size: 14px; }}
                .paper-link:hover {{ background: #2980b9; }}
                .footer {{ background: #2c3e50; color: white; padding: 20px; text-align: center; font-size: 14px; }}
                .no-papers {{ text-align: center; padding: 40px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 Cecilia 研究助手</h1>
                    <p>ArXiv 论文每日推送 - {current_time}</p>
                </div>
                
                <div class="stats">
                    <h3>📊 推送统计</h3>
                    <p><strong>搜索类别:</strong> {category}</p>
                    <p><strong>搜索主题:</strong> {topic}</p>
                    <p><strong>论文数量:</strong> {stats.get('papers_count', 0)} 篇</p>
                    <p><strong>新处理:</strong> {stats.get('new_papers', 0)} 篇</p>
                    <p><strong>缓存获取:</strong> {stats.get('cached_papers', 0)} 篇</p>
                </div>
        """
        
        if papers:
            for i, paper in enumerate(papers, 1):
                authors_str = ", ".join(paper.get('authors', []))
                categories_str = ", ".join(paper.get('categories', []))
                
                # Convert markdown summary to HTML
                summary_html = self._markdown_to_html(paper['summary'])
                
                html += f"""
                <div class="paper">
                    <div class="paper-title">📄 {paper['title']}</div>
                    <div class="paper-authors">👥 作者: {authors_str}</div>
                    <div class="paper-categories">🏷️ {categories_str or '未分类'}</div>
                    <div class="paper-summary">
                        <strong>论文总结:</strong><br>
                        {summary_html}
                    </div>
                    <div style="text-align: center; margin-top: 15px;">
                        <a href="{paper.get('pdf_url', '#')}" style="background: #3498db; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; font-size: 14px; display: inline-block;" target="_blank">📖 阅读原文</a>
                    </div>
                </div>
                """
                
                # 在最后一篇论文之后不添加分界线
                if i < len(papers):
                    html += '<hr style="border: none; border-top: 2px solid #e0e0e0; margin: 30px 20px; opacity: 0.6;">'
        else:
            html += """
            <div class="no-papers">
                <h3>📝 暂无新论文</h3>
                <p>今日该主题暂无新论文发布，请明日继续关注。</p>
            </div>
            """
                
        # Add size warning if attachments were removed
        if removed_attachments > 0:
            html += f"""
                <div class="size-warning">
                    <h4>⚠️ 邮件大小限制提醒</h4>
                    <p>为确保邮件能够正常发送，本次邮件已移除最后 <strong>{removed_attachments}</strong> 篇论文的PDF附件以控制邮件大小在50MB以内。</p>
                    <p>您仍可通过每篇论文下方的"阅读原文"链接访问完整PDF文档。</p>
                </div>
            """
        
        footer_text = self.custom_footer if self.custom_footer else "感谢使用 Cecilia 研究助手"
        html += f"""
                <div class="footer">
                    <p>{footer_text}</p>
                    <p>🤖 本邮件由 Cecilia Discord Bot 自动发送</p>
                    <p>📡 数据来源: ArXiv • AI模型: LLM </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
