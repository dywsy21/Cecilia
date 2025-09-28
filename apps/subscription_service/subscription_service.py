import asyncio
import json
import logging
import random
import re
import smtplib
import ssl
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Set
from aiohttp import web
import hashlib
import secrets

from bot.auths import (
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_SECURE,
    EMAIL_SMTP_USER, EMAIL_SMTP_PASS, EMAIL_SMTP_NAME,
    EMAIL_SMTP_LOGGER, EMAIL_SMTP_TLS_REJECT_UNAUTH,
    EMAIL_SMTP_IGNORE_TLS
)

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Handles email subscription creation and verification with 6-digit codes"""
    
    def __init__(self):
        self.data_dir = Path("data/essay_summarizer")
        self.email_targets_file = self.data_dir / "email_targets.json"
        self.verification_sessions_file = self.data_dir / "verification_sessions.json"
        self.rate_limit_file = self.data_dir / "rate_limits.json"
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if they don't exist
        self._init_files()
        
        # Rate limiting settings
        self.rate_limits = {
            'create_subscription': {'requests': 5, 'window': 900},  # 5 requests per 15 minutes
            'verify_email': {'requests': 10, 'window': 300},        # 10 attempts per 5 minutes
            'resend_code': {'requests': 3, 'window': 900}           # 3 resends per 15 minutes
        }
        
        # Load rate limit data
        self.rate_limit_data = self._load_rate_limits()
        
        # Cleanup task
        self.cleanup_task = None
        
        logger.info("SubscriptionService initialized")
    
    def _init_files(self):
        """Initialize data files if they don't exist"""
        try:
            if not self.email_targets_file.exists():
                with open(self.email_targets_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)
            
            if not self.verification_sessions_file.exists():
                with open(self.verification_sessions_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)
            
            if not self.rate_limit_file.exists():
                with open(self.rate_limit_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error initializing files: {e}")
            raise
    
    def _load_email_targets(self) -> Dict[str, List[str]]:
        """Load email targets from disk"""
        try:
            with open(self.email_targets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle migration from old format (list) to new format (dict)
            if isinstance(data, list):
                logger.info("Migrating email_targets.json from old format")
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
            raise
    
    def _load_verification_sessions(self) -> Dict[str, Dict]:
        """Load verification sessions from disk"""
        try:
            with open(self.verification_sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading verification sessions: {e}")
            return {}
    
    def _save_verification_sessions(self, sessions: Dict[str, Dict]):
        """Save verification sessions to disk"""
        try:
            with open(self.verification_sessions_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving verification sessions: {e}")
            raise
    
    def _load_rate_limits(self) -> Dict[str, Dict]:
        """Load rate limit data from disk"""
        try:
            with open(self.rate_limit_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading rate limits: {e}")
            return {}
    
    def _save_rate_limits(self):
        """Save rate limit data to disk"""
        try:
            with open(self.rate_limit_file, 'w', encoding='utf-8') as f:
                json.dump(self.rate_limit_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limits: {e}")
    
    def _check_rate_limit(self, client_ip: str, endpoint: str) -> bool:
        """Check if client has exceeded rate limit for endpoint"""
        current_time = time.time()
        limit_config = self.rate_limits.get(endpoint, {'requests': 5, 'window': 900})
        
        # Clean old entries
        self._cleanup_rate_limits(current_time)
        
        # Get client's request history for this endpoint
        client_key = f"{client_ip}:{endpoint}"
        client_requests = self.rate_limit_data.get(client_key, [])
        
        # Filter requests within the time window
        window_start = current_time - limit_config['window']
        recent_requests = [req_time for req_time in client_requests if req_time > window_start]
        
        # Check if limit exceeded
        if len(recent_requests) >= limit_config['requests']:
            return False
        
        # Record this request
        recent_requests.append(current_time)
        self.rate_limit_data[client_key] = recent_requests
        self._save_rate_limits()
        
        return True
    
    def _cleanup_rate_limits(self, current_time: float):
        """Remove expired rate limit entries"""
        max_window = max(config['window'] for config in self.rate_limits.values())
        cutoff_time = current_time - max_window - 3600  # Extra hour buffer
        
        # Remove old entries
        for client_key in list(self.rate_limit_data.keys()):
            requests = self.rate_limit_data[client_key]
            self.rate_limit_data[client_key] = [req for req in requests if req > cutoff_time]
            
            # Remove empty entries
            if not self.rate_limit_data[client_key]:
                del self.rate_limit_data[client_key]
    
    def _generate_verification_code(self) -> str:
        """Generate a secure 6-digit verification code"""
        return f"{random.randint(100000, 999999):06d}"
    
    def _generate_session_token(self) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email.strip()) is not None
    
    def _validate_topics(self, topics: List[str]) -> tuple[bool, str]:
        """Validate ArXiv topics"""
        if not topics or len(topics) < 5:
            return False, "At least 5 topics are required"
        
        if len(topics) > 20:
            return False, "Maximum 20 topics allowed"
        
        # Define valid ArXiv categories
        valid_categories = {
            'cs', 'math', 'physics', 'stat', 'eess', 'q-bio', 'q-fin', 
            'econ', 'astro-ph', 'cond-mat', 'gr-qc', 'hep-ex', 'hep-lat',
            'hep-ph', 'hep-th', 'math-ph', 'nlin', 'nucl-ex', 'nucl-th',
            'quant-ph'
        }
        
        for topic in topics:
            if '.' not in topic:
                continue  # Allow topics without subcategories
            
            category = topic.split('.')[0]
            if category not in valid_categories:
                return False, f"Invalid category: {category}"
        
        return True, ""
    
    async def _send_verification_email(self, email: str, verification_code: str) -> bool:
        """Send verification email with 6-digit code"""
        try:
            # Validate email configuration
            if not all([EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASS]):
                logger.error("Email configuration incomplete")
                return False
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Cecilia 订阅验证码: {verification_code}"
            msg['From'] = f"{EMAIL_SMTP_NAME} <{EMAIL_SMTP_USER}>" if EMAIL_SMTP_NAME else EMAIL_SMTP_USER
            msg['To'] = email
            
            # Create HTML email content
            html_content = self._create_verification_email_html(verification_code)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            if EMAIL_SMTP_SECURE:
                context = ssl.create_default_context()
                if EMAIL_SMTP_IGNORE_TLS:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                elif not EMAIL_SMTP_TLS_REJECT_UNAUTH:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_OPTIONAL
                
                with smtplib.SMTP_SSL(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, context=context) as server:
                    if EMAIL_SMTP_LOGGER:
                        server.set_debuglevel(1)
                    server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASS)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                    if EMAIL_SMTP_LOGGER:
                        server.set_debuglevel(1)
                    
                    if not EMAIL_SMTP_IGNORE_TLS:
                        context = ssl.create_default_context()
                        if not EMAIL_SMTP_TLS_REJECT_UNAUTH:
                            context.check_hostname = False
                            context.verify_mode = ssl.CERT_OPTIONAL
                        server.starttls(context=context)
                    
                    server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASS)
                    server.send_message(msg)
            
            logger.info(f"Verification email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            return False
    
    def _create_verification_email_html(self, verification_code: str) -> str:
        """Create HTML content for verification email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 30px; }}
                .code-box {{ background: #f8f9fa; border: 2px solid #667eea; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
                .code {{ font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 8px; margin: 10px 0; }}
                .instructions {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 14px; color: #666; }}
                .warning {{ color: #e74c3c; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 Cecilia 邮箱验证</h1>
                    <p>ArXiv 论文订阅服务</p>
                </div>
                
                <div class="content">
                    <h2>验证您的邮箱地址</h2>
                    <p>感谢您订阅 Cecilia 研究助手的 ArXiv 论文推送服务！</p>
                    
                    <p>请在订阅页面输入以下 6 位验证码来完成邮箱验证：</p>
                    
                    <div class="code-box">
                        <div>您的验证码是：</div>
                        <div class="code">{verification_code}</div>
                    </div>
                    
                    <div class="instructions">
                        <h3>📝 使用说明：</h3>
                        <ul>
                            <li>返回订阅页面，输入这个 6 位数字验证码</li>
                            <li>验证码有效期为 <strong>10 分钟</strong></li>
                            <li>验证成功后，您将开始接收每日论文推送</li>
                            <li>推送时间：每天早上 7:00 AM</li>
                        </ul>
                    </div>
                    
                    <p class="warning">⚠️ 重要提醒：</p>
                    <ul>
                        <li>如果您没有请求此验证码，请忽略此邮件</li>
                        <li>请勿将验证码分享给他人</li>
                        <li>如有疑问，请联系我们的技术支持</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>🤖 此邮件由 Cecilia Discord Bot 自动发送</p>
                    <p>📡 服务时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
                    <p>💡 这是一封自动邮件，请勿回复</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def create_subscription(self, request):
        """Handle subscription creation and send verification email"""
        try:
            # Get client IP for rate limiting
            client_ip = request.remote
            
            # Check rate limit
            if not self._check_rate_limit(client_ip, 'create_subscription'):
                return web.json_response({
                    'success': False,
                    'error': 'Too many requests. Please try again in 15 minutes.'
                }, status=429)
            
            # Parse request data
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON format'
                }, status=400)
            
            email = data.get('email', '').strip().lower()
            topics = data.get('topics', [])
            
            # Validate input
            if not email or not topics:
                return web.json_response({
                    'success': False,
                    'error': 'Email and topics are required'
                }, status=400)
            
            if not self._validate_email(email):
                return web.json_response({
                    'success': False,
                    'error': 'Please enter a valid email address'
                }, status=400)
            
            topics_valid, topics_error = self._validate_topics(topics)
            if not topics_valid:
                return web.json_response({
                    'success': False,
                    'error': topics_error
                }, status=400)
            
            # Check for existing subscription conflicts
            email_targets = self._load_email_targets()
            if email in email_targets:
                existing_topics = set(email_targets[email])
                new_topics = set(topics)
                overlap = existing_topics & new_topics
                
                if overlap:
                    return web.json_response({
                        'success': False,
                        'error': f'Email already subscribed to: {", ".join(sorted(overlap))}'
                    }, status=409)
            
            # Generate verification code and session token
            verification_code = self._generate_verification_code()
            session_token = self._generate_session_token()
            
            # Create verification session
            session_data = {
                'email': email,
                'topics': topics,
                'verification_code': verification_code,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(minutes=10)).isoformat(),
                'attempts': 0,
                'verified': False
            }
            
            # Save session
            sessions = self._load_verification_sessions()
            sessions[session_token] = session_data
            self._save_verification_sessions(sessions)
            
            # Send verification email
            email_sent = await self._send_verification_email(email, verification_code)
            
            if not email_sent:
                return web.json_response({
                    'success': False,
                    'error': 'Failed to send verification email. Please try again.'
                }, status=500)
            
            logger.info(f"Subscription verification email sent to {email} for {len(topics)} topics")
            
            return web.json_response({
                'success': True,
                'message': 'Verification email sent successfully',
                'session_token': session_token,
                'verification_required': True,
                'expires_in': 600  # 10 minutes in seconds
            })
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return web.json_response({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    async def verify_email(self, request):
        """Handle email verification with 6-digit code"""
        try:
            # Get client IP for rate limiting
            client_ip = request.remote
            
            # Check rate limit
            if not self._check_rate_limit(client_ip, 'verify_email'):
                return web.json_response({
                    'success': False,
                    'error': 'Too many verification attempts. Please try again in 5 minutes.'
                }, status=429)
            
            # Parse request data
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON format'
                }, status=400)
            
            session_token = data.get('session_token', '').strip()
            verification_code = data.get('verification_code', '').strip()
            
            # Validate input
            if not session_token or not verification_code:
                return web.json_response({
                    'success': False,
                    'error': 'Session token and verification code are required'
                }, status=400)
            
            if not re.match(r'^\d{6}$', verification_code):
                return web.json_response({
                    'success': False,
                    'error': 'Please enter a valid 6-digit verification code'
                }, status=400)
            
            # Load and check session
            sessions = self._load_verification_sessions()
            
            if session_token not in sessions:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid or expired verification session'
                }, status=404)
            
            session = sessions[session_token]
            
            # Check if session expired
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now() > expires_at:
                # Clean up expired session
                del sessions[session_token]
                self._save_verification_sessions(sessions)
                
                return web.json_response({
                    'success': False,
                    'error': 'Verification code expired. Please request a new one.'
                }, status=400)
            
            # Check attempt count
            if session['attempts'] >= 5:
                return web.json_response({
                    'success': False,
                    'error': 'Too many verification attempts. Please request a new code.'
                }, status=429)
            
            # Increment attempt count
            session['attempts'] += 1
            sessions[session_token] = session
            self._save_verification_sessions(sessions)
            
            # Verify code
            if verification_code != session['verification_code']:
                attempts_left = 5 - session['attempts']
                return web.json_response({
                    'success': False,
                    'error': f'Invalid verification code. {attempts_left} attempts remaining.'
                }, status=400)
            
            # Success! Add to email targets
            email_targets = self._load_email_targets()
            
            if session['email'] in email_targets:
                # Merge topics
                existing_topics = set(email_targets[session['email']])
                new_topics = set(session['topics'])
                email_targets[session['email']] = list(existing_topics | new_topics)
            else:
                # New subscription
                email_targets[session['email']] = session['topics']
            
            self._save_email_targets(email_targets)
            
            # Mark session as verified and clean up
            session['verified'] = True
            session['verified_at'] = datetime.now().isoformat()
            sessions[session_token] = session
            self._save_verification_sessions(sessions)
            
            # Schedule session cleanup
            asyncio.create_task(self._cleanup_session_later(session_token, 300))  # 5 minutes
            
            logger.info(f"Email verification successful for {session['email']} with {len(session['topics'])} topics")
            
            return web.json_response({
                'success': True,
                'message': f'Email verified successfully! You are now subscribed to {len(session["topics"])} research topics.',
                'subscribed_topics': session['topics'],
                'email': session['email']
            })
            
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return web.json_response({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    async def resend_verification_code(self, request):
        """Resend verification code"""
        try:
            # Get client IP for rate limiting
            client_ip = request.remote
            
            # Check rate limit
            if not self._check_rate_limit(client_ip, 'resend_code'):
                return web.json_response({
                    'success': False,
                    'error': 'Too many resend attempts. Please try again in 15 minutes.'
                }, status=429)
            
            # Parse request data
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid JSON format'
                }, status=400)
            
            session_token = data.get('session_token', '').strip()
            
            if not session_token:
                return web.json_response({
                    'success': False,
                    'error': 'Session token is required'
                }, status=400)
            
            # Load and check session
            sessions = self._load_verification_sessions()
            
            if session_token not in sessions:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid or expired verification session'
                }, status=404)
            
            session = sessions[session_token]
            
            # Check if session expired
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now() > expires_at:
                return web.json_response({
                    'success': False,
                    'error': 'Verification session expired. Please start over.'
                }, status=400)
            
            # Generate new verification code
            new_code = self._generate_verification_code()
            session['verification_code'] = new_code
            session['attempts'] = 0  # Reset attempts
            session['resent_at'] = datetime.now().isoformat()
            
            # Save updated session
            sessions[session_token] = session
            self._save_verification_sessions(sessions)
            
            # Send new verification email
            email_sent = await self._send_verification_email(session['email'], new_code)
            
            if not email_sent:
                return web.json_response({
                    'success': False,
                    'error': 'Failed to resend verification email. Please try again.'
                }, status=500)
            
            logger.info(f"Verification code resent to {session['email']}")
            
            return web.json_response({
                'success': True,
                'message': 'New verification code sent successfully',
                'expires_in': int((expires_at - datetime.now()).total_seconds())
            })
            
        except Exception as e:
            logger.error(f"Error resending verification code: {e}")
            return web.json_response({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    async def _cleanup_session_later(self, session_token: str, delay_seconds: int):
        """Clean up verification session after delay"""
        try:
            await asyncio.sleep(delay_seconds)
            sessions = self._load_verification_sessions()
            if session_token in sessions:
                del sessions[session_token]
                self._save_verification_sessions(sessions)
                logger.info(f"Cleaned up verification session: {session_token}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_token}: {e}")
    
    def setup_routes(self, app: web.Application):
        """Setup HTTP routes"""
        app.router.add_post('/api/subscription/create', self.create_subscription)
        app.router.add_post('/api/subscription/verify', self.verify_email)
        app.router.add_post('/api/subscription/resend', self.resend_verification_code)
        app.router.add_options('/api/subscription/create', self._handle_cors)
        app.router.add_options('/api/subscription/verify', self._handle_cors)
        app.router.add_options('/api/subscription/resend', self._handle_cors)
    
    async def _handle_cors(self, request):
        """Handle CORS preflight requests"""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            }
        )
    
    async def start_cleanup_task(self):
        """Start periodic cleanup of expired sessions and rate limits"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # 5 minutes
                    await self._cleanup_expired_data()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}")
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started cleanup task")
    
    async def _cleanup_expired_data(self):
        """Clean up expired verification sessions and old rate limit data"""
        try:
            current_time = datetime.now()
            
            # Clean up expired verification sessions
            sessions = self._load_verification_sessions()
            expired_sessions = []
            
            for token, session in sessions.items():
                expires_at = datetime.fromisoformat(session['expires_at'])
                if current_time > expires_at:
                    expired_sessions.append(token)
            
            for token in expired_sessions:
                del sessions[token]
            
            if expired_sessions:
                self._save_verification_sessions(sessions)
                logger.info(f"Cleaned up {len(expired_sessions)} expired verification sessions")
            
            # Clean up old rate limit data
            self._cleanup_rate_limits(time.time())
            if expired_sessions:  # Save if we cleaned anything
                self._save_rate_limits()
            
        except Exception as e:
            logger.error(f"Error cleaning up expired data: {e}")
    
    async def shutdown(self):
        """Shutdown the subscription service"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("SubscriptionService shut down")
