import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Dict, Optional
from datetime import datetime
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
    
    def _create_email_html(self, category: str, topic: str, papers: List[Dict], stats: Dict) -> str:
        """Create HTML email content for paper summaries"""
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
                .paper {{ margin: 20px; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa; }}
                .paper-title {{ color: #2c3e50; font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .paper-authors {{ color: #7f8c8d; font-size: 14px; margin-bottom: 10px; }}
                .paper-categories {{ background: #ecf0f1; padding: 5px 10px; border-radius: 15px; font-size: 12px; color: #2c3e50; display: inline-block; margin-bottom: 15px; }}
                .paper-summary {{ margin: 15px 0; line-height: 1.8; }}
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
                
                html += f"""
                <div class="paper">
                    <div class="paper-title">📄 {paper['title']}</div>
                    <div class="paper-authors">👥 作者: {authors_str}</div>
                    <div class="paper-categories">🏷️ {categories_str or '未分类'}</div>
                    <div class="paper-summary">
                        <strong>论文总结:</strong><br>
                        {paper['summary'].replace('\n', '<br>')}
                    </div>
                    <div style="text-align: center; margin-top: 15px;">
                        <a href="{paper.get('pdf_url', '#')}" class="paper-link" target="_blank">📖 阅读原文</a>
                    </div>
                </div>
                """
        else:
            html += """
            <div class="no-papers">
                <h3>📝 暂无新论文</h3>
                <p>今日该主题暂无新论文发布，请明日继续关注。</p>
            </div>
            """
        
        footer_text = self.custom_footer if self.custom_footer else "感谢使用 Cecilia 研究助手"
        html += f"""
                <div class="footer">
                    <p>{footer_text}</p>
                    <p>🤖 本邮件由 Cecilia Discord Bot 自动发送</p>
                    <p>📡 数据来源: ArXiv • AI模型: DeepSeek-R1-32B</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def send_paper_summary_email(self, 
                                     to_emails: List[str], 
                                     category: str, 
                                     topic: str, 
                                     papers: List[Dict], 
                                     stats: Dict) -> Dict:
        """Send paper summary email to multiple recipients"""
        if not self._validate_config():
            return {"success": False, "error": "Email configuration is incomplete"}
        
        try:
            subject = f"Cecilia 研究推送: {category}.{topic} - {len(papers)}篇论文 ({datetime.now().strftime('%m月%d日')})"
            html_content = self._create_email_html(category, topic, papers, stats)
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.smtp_name} <{self.smtp_user}>" if self.smtp_name else self.smtp_user
            msg['To'] = ', '.join(to_emails)
            
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
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
            
            logger.info(f"Email sent successfully to {len(to_emails)} recipients for {category}.{topic}")
            return {
                "success": True, 
                "message": f"Email sent to {len(to_emails)} recipients",
                "recipients": to_emails,
                "subject": subject
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}
