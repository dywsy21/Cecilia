import time
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from aiohttp import web
import json
import nacl.signing
import nacl.encoding
from nacl.exceptions import BadSignatureError
from .auths import DISCORD_TOKEN, APP_ID, PUBLIC_KEY, ADMIN_USER_ID
from apps.apps import AppManager
import aiohttp
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CeciliaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.app_manager = AppManager()
        self.webhook_app = None
        # Setup verification key
        self.verify_key = nacl.signing.VerifyKey(bytes.fromhex(PUBLIC_KEY))

    async def setup_hook(self):
        """Called when the bot is starting up"""
        try:
            # For webhook-only mode, we need to register commands via HTTP API
            await self.register_slash_commands()
            logger.info("Slash commands registered via HTTP API")
        except Exception as e:
            logger.error(f"Failed to register commands: {e}")

    async def register_slash_commands(self):
        """Register slash commands via Discord HTTP API"""
        commands_to_register = [
            {
                "name": "hello",
                "type": 1,  # CHAT_INPUT
                "description": "Say hello to Cecilia!"
            },
            {
                "name": "subscribe",
                "type": 1,
                "description": "Manage your research topic subscriptions",
                "options": [
                    {
                        "name": "action",
                        "description": "Action to perform",
                        "type": 3,  # STRING
                        "required": True,
                        "choices": [
                            {"name": "list", "value": "list"},
                            {"name": "add", "value": "add"},
                            {"name": "remove", "value": "remove"},
                            {"name": "now", "value": "now"}
                        ]
                    },
                    {
                        "name": "category",
                        "description": "ArXiv category (e.g., cs, math, physics). Leave empty for 'all'",
                        "type": 3,  # STRING
                        "required": False
                    },
                    {
                        "name": "topic",
                        "description": "Research topic/keyword",
                        "type": 3,  # STRING
                        "required": False
                    }
                ]
            },
            {
                "name": "status",
                "type": 1,
                "description": "Check bot status and available apps"
            },
            {
                "name": "get_my_id",
                "type": 1,
                "description": "Get your Discord user ID for message pusher testing"
            },
            {
                "name": "test_message",
                "type": 1,
                "description": "Test the message pusher by sending yourself a message"
            },
            {
                "name": "debug",
                "type": 1,
                "description": "Admin debug commands",
                "options": [
                    {
                        "name": "type",
                        "description": "Debug type to execute",
                        "type": 3,  # STRING
                        "required": True,
                        "choices": [
                            {"name": "discord", "value": "discord"},
                            {"name": "email", "value": "email"}
                        ]
                    }
                ]
            }
        ]

        url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"
        headers = {
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            for command in commands_to_register:
                time.sleep(1)
                try:
                    async with session.post(url, headers=headers, json=command) as response:
                        if response.status == 200 or response.status == 201:
                            logger.info(f"Successfully registered command: {command['name']}")
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to register command {command['name']}: {response.status} - {error_text}")
                except Exception as e:
                    logger.error(f"Error registering command {command['name']}: {e}")

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

    def verify_signature(self, signature: str, timestamp: str, body: str) -> bool:
        """Verify Discord interaction signature according to Discord docs"""
        try:
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(PUBLIC_KEY))
            # Discord expects timestamp + body as per their documentation
            message = f'{timestamp}{body}'.encode()
            logger.debug(f"Verifying signature for message length: {len(message)}")
            logger.debug(f"Timestamp: {timestamp}")
            logger.debug(f"Signature: {signature[:16]}...")
            
            verify_key.verify(
                message, 
                bytes.fromhex(signature)
            )
            logger.info("Signature verification successful")
            return True
        except BadSignatureError:
            logger.error("Signature verification failed: BadSignatureError")
            logger.error(f"PUBLIC_KEY: {PUBLIC_KEY[:16]}...")
            logger.error(f"Timestamp: {timestamp}")
            logger.error(f"Body length: {len(body)}")
            return False
        except Exception as e:
            logger.error(f"Signature verification failed with exception: {e}")
            return False

    def create_interactions_app(self):
        """Create aiohttp app for Discord interactions"""
        app = web.Application()
        # Add routes for both /interactions and /bot/interactions to handle Nginx proxy
        app.router.add_post('/interactions', self.handle_interaction)
        app.router.add_post('/bot/interactions', self.handle_interaction)
        app.router.add_get('/health', self.health_check)
        app.router.add_get('/bot/health', self.health_check)
        return app

    async def handle_interaction(self, request):
        """Handle Discord interactions webhook"""
        try:
            # Get headers for verification
            signature = request.headers.get('X-Signature-Ed25519')
            timestamp = request.headers.get('X-Signature-Timestamp')
            
            if not signature or not timestamp:
                logger.error("Missing signature headers")
                return web.json_response(
                    {'error': 'Missing signature headers'}, 
                    status=401
                )
            
            # Get body as string for verification (Discord expects string, not bytes)
            body_bytes = await request.read()
            body = body_bytes.decode('utf-8')
            
            # Verify signature
            if not self.verify_signature(signature, timestamp, body):
                logger.error("Invalid signature")
                return web.json_response(
                    {'error': 'invalid request signature'}, 
                    status=401
                )
            
            # Parse JSON data
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in request body")
                return web.json_response(
                    {'error': 'Invalid JSON'}, 
                    status=400
                )
            
            interaction_type = data.get('type')
            
            # Handle PING (type 1) - Must return type 1 with proper Content-Type
            if interaction_type == 1:
                logger.info("Received PING from Discord - responding with PONG")
                return web.json_response({'type': 1})
            
            # Handle Application Command (type 2)
            if interaction_type == 2:
                command_data = data.get('data', {})
                command_name = command_data.get('name')
                logger.info(f"Received application command: {command_name}")
                
                if command_name == 'hello':
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    username = user.get('username', 'User')
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'content': f'Hello {username}! I\'m Cecilia, your research assistant bot! 👋'
                        }
                    })
                
                elif command_name == 'status':
                    embed = {
                        'title': 'Cecilia Bot Status',
                        'description': 'I\'m online and ready to help!',
                        'color': 0x00FF00,
                        'fields': [
                            {
                                'name': 'Available Apps',
                                'value': '• Essay Summarizer\n• Message Pusher',
                                'inline': False
                            },
                            {
                                'name': 'Service',
                                'value': 'Webhook Active ✅',
                                'inline': True
                            }
                        ]
                    }
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'embeds': [embed]
                        }
                    })
                
                elif command_name == 'debug':
                    # Check if user is admin
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    user_id = user.get('id')
                    
                    if not ADMIN_USER_ID or str(user_id) != str(ADMIN_USER_ID):
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': '❌ This command is only available for administrators.',
                                'flags': 64  # Ephemeral
                            }
                        })
                    
                    # Get debug type parameter
                    options = command_data.get('options', [])
                    debug_type = None
                    for option in options:
                        if option.get('name') == 'type':
                            debug_type = option.get('value')
                            break
                    
                    if not debug_type:
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': '❌ Please specify debug type (discord or email)!',
                                'flags': 64
                            }
                        })
                    
                    # Start background task for debug command
                    asyncio.create_task(self.handle_debug_command(data, debug_type, user_id))
                    
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'content': f'🔧 Starting debug execution for {debug_type} subscriptions... Results will be sent to you.',
                            'flags': 64  # Ephemeral
                        }
                    })
                
                elif command_name == 'summarize':
                    # Get the topic parameter
                    options = command_data.get('options', [])
                    topic = None
                    for option in options:
                        if option.get('name') == 'topic':
                            topic = option.get('value')
                            break
                    
                    if not topic:
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': 'Please provide a topic to summarize!'
                            }
                        })
                    
                    # For webhook-only mode, we need to defer and handle async
                    # Start background task to process and send followup
                    asyncio.create_task(self.handle_summarize_command(data, topic))
                    
                    return web.json_response({
                        'type': 5,  # Deferred response
                    })
                
                elif command_name == 'get_my_id':
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    user_id = user.get('id', 'Unknown')
                    channel_id = data.get('channel_id', 'Unknown')
                    guild_id = data.get('guild_id', 'DM')
                    
                    embed = {
                        'title': 'Your Discord Information',
                        'description': 'Use these IDs for testing',
                        'color': 0x0099FF,
                        'fields': [
                            {'name': 'User ID', 'value': f'`{user_id}`', 'inline': False},
                            {'name': 'Channel ID', 'value': f'`{channel_id}`', 'inline': False},
                            {'name': 'Server ID', 'value': f'`{guild_id}`', 'inline': False}
                        ]
                    }
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'embeds': [embed],
                            'flags': 64  # Ephemeral flag
                        }
                    })
                
                elif command_name == 'test_message':
                    # Start background task for test message
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    user_id = user.get('id')
                    
                    if user_id:
                        asyncio.create_task(self.handle_test_message_command(data, user_id))
                        
                    return web.json_response({
                        'type': 5,  # Deferred response
                    })
                
                elif command_name == 'instantlyshow':
                    # Get the topic parameter
                    options = command_data.get('options', [])
                    topic = None
                    for option in options:
                        if option.get('name') == 'topic':
                            topic = option.get('value')
                            break
                    
                    if not topic:
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': 'Please provide a topic to summarize!'
                            }
                        })
                    
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    user_id = user.get('id')
                    
                    # Send immediate response
                    asyncio.create_task(self.handle_instantly_show_command(data, topic, user_id))
                    
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'content': f'🔄 Processing... Analyzing latest papers on "{topic}". Results will be sent to you shortly!'
                        }
                    })
                
                elif command_name == 'subscribe':
                    # Get parameters
                    options = command_data.get('options', [])
                    action = None
                    category = None
                    topic = None
                    
                    for option in options:
                        if option.get('name') == 'action':
                            action = option.get('value')
                        elif option.get('name') == 'category':
                            category = option.get('value')
                        elif option.get('name') == 'topic':
                            topic = option.get('value')
                    
                    if not action:
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': 'Please specify an action (list, add, remove, or now)!'
                            }
                        })
                    
                    user = data.get('member', {}).get('user', data.get('user', {}))
                    user_id = user.get('id')
                    
                    # Handle subscription management
                    if action == 'now':
                        # Instant show functionality
                        if not topic:
                            return web.json_response({
                                'type': 4,
                                'data': {
                                    'content': 'Please provide a topic for instant search!'
                                }
                            })
                        
                        asyncio.create_task(self.handle_instantly_show_command(data, category or 'all', topic, user_id))
                        
                        return web.json_response({
                            'type': 4,
                            'data': {
                                'content': f'🔄 Processing... Analyzing latest papers on "{category or "all"}.{topic}". Results will be sent to you shortly!'
                            }
                        })
                    else:
                        # Regular subscription management
                        asyncio.create_task(self.handle_subscribe_command(data, action, category, topic, user_id))
                        
                        return web.json_response({
                            'type': 5,  # Deferred response
                        })

                else:
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'content': f'Command `{command_name}` received via webhook! 🚀'
                        }
                    })
            
            # Handle other interaction types
            logger.warning(f"Unhandled interaction type: {interaction_type}")
            return web.json_response(
                {'error': 'Unhandled interaction type'}, 
                status=400
            )
            
        except Exception as e:
            logger.error(f"Error handling interaction: {e}")
            return web.json_response(
                {'error': 'Internal server error'}, 
                status=500
            )

    async def handle_summarize_command(self, interaction_data, topic):
        """Handle summarize command with followup response"""
        try:
            # Process the summarization
            result = await self.app_manager.summarize_essays(topic)
            
            # Send followup response
            await self.send_followup_response(interaction_data, {
                'content': result
            })
            
        except Exception as e:
            logger.error(f"Error in summarize command: {e}")
            await self.send_followup_response(interaction_data, {
                'content': f'Sorry, there was an error processing your request: {str(e)}'
            })

    async def handle_test_message_command(self, interaction_data, user_id):
        """Handle test message command with followup response"""
        try:
            test_data = {
                "user_id": str(user_id),
                "message": {
                    "embed": {
                        "title": "🧪 Message Pusher Test",
                        "description": "This message was sent via the HTTP message pusher API!",
                        "color": "#00FF00",
                        "fields": [
                            {
                                "name": "Test Status",
                                "value": "✅ Success",
                                "inline": True
                            }
                        ],
                        "footer": {
                            "text": "Cecilia Message Pusher"
                        }
                    }
                }
            }
            
            result = await self.app_manager.msg_pusher.process_message(test_data)
            
            if result['success']:
                await self.send_followup_response(interaction_data, {
                    'content': f'✅ Test message sent successfully! Message ID: `{result["message_id"]}`',
                    'flags': 64  # Ephemeral
                })
            else:
                await self.send_followup_response(interaction_data, {
                    'content': f'❌ Test failed: {result["error"]}',
                    'flags': 64
                })
                
        except Exception as e:
            logger.error(f"Error in test_message command: {e}")
            await self.send_followup_response(interaction_data, {
                'content': f'❌ Test failed with error: {str(e)}',
                'flags': 64
            })

    async def handle_subscribe_command(self, interaction_data, action, category, topic, user_id):
        """Handle subscription management command"""
        try:
            if action == 'list':
                result = await self.app_manager.essay_summarizer.list_subscriptions(user_id)
            elif action == 'add':
                if not topic:
                    result = "❌ Please provide a topic to add to your subscriptions!"
                else:
                    result = await self.app_manager.essay_summarizer.add_subscription(user_id, category or 'all', topic)
            elif action == 'remove':
                if not topic:
                    result = "❌ Please provide a topic to remove from your subscriptions!"
                else:
                    result = await self.app_manager.essay_summarizer.remove_subscription(user_id, category or 'all', topic)
            else:
                result = "❌ Invalid action. Use 'list', 'add', 'remove', or 'now'."
            
            # Send followup response
            await self.send_followup_response(interaction_data, {
                'content': result
            })
            
        except Exception as e:
            logger.error(f"Error in subscribe command: {e}")
            await self.send_followup_response(interaction_data, {
                'content': f'❌ Sorry, there was an error: {str(e)}'
            })

    async def handle_instantly_show_command(self, interaction_data, category, topic, user_id):
        """Handle instantly show command with message pusher"""
        try:
            # Start the summarization process
            result = await self.app_manager.essay_summarizer.instantly_summarize_and_push(category, topic, user_id)
            
            # The result is sent via message pusher, so we don't need to send a followup
            logger.info(f"Instantly show command completed for category: {category}, topic: {topic}")
            
        except Exception as e:
            logger.error(f"Error in instantly show command: {e}")
            # Send error via message pusher API
            error_message = f"❌ Sorry, there was an error processing your request for '{topic}' in category '{category}': {str(e)}"
            await self._send_error_via_api(user_id, error_message)

    async def send_followup_response(self, interaction_data, response_data):
        """Send a followup response to an interaction"""
        try:
            interaction_token = interaction_data.get('token')
            if not interaction_token:
                logger.error("No interaction token found for followup")
                return
            
            url = f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}"
            headers = {
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=response_data) as response:
                    if response.status == 200:
                        logger.info("Followup response sent successfully")
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send followup: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"Error sending followup response: {e}")
            
    async def start_interactions_server(self, port: int = 8010):
        """Start the Discord interactions webhook server"""
        try:
            self.webhook_app = self.create_interactions_app()
            runner = web.AppRunner(self.webhook_app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', port)
            await site.start()
            logger.info(f"Discord interactions server started on port {port}")
            
            # Keep the server running
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                logger.info("Interactions server stopping...")
                await runner.cleanup()
                
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"Port {port} already in use - cannot start interactions server")
                raise CeciliaServiceError(f"Cannot bind to port {port} - address already in use")
            else:
                logger.error(f"OS error starting interactions server: {e}")
                raise CeciliaServiceError(f"System error starting interactions server: {e}")
        except Exception as e:
            logger.error(f"Failed to start interactions server: {e}")
            raise CeciliaServiceError(f"Cannot start interactions server: {e}")

    async def health_check(self, request):
        """Health check for interactions endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'discord_interactions',
            'bot_ready': self.is_ready(),
            'verification': 'enabled',
            'public_key': PUBLIC_KEY[:8] + '...',  # Show first 8 chars for verification
        })
    async def handle_debug_command(self, interaction_data, debug_type, user_id):
        """Handle admin debug command execution"""
        try:
            logger.info(f"Admin debug command executed by user {user_id}: {debug_type}")
            
            if debug_type == 'discord':
                # Execute Discord subscription processing
                logger.info("Starting debug execution of Discord subscriptions...")
                await self._debug_discord_subscriptions(user_id)
                
            elif debug_type == 'email':
                # Execute Email subscription processing
                logger.info("Starting debug execution of Email subscriptions...")
                await self._debug_email_subscriptions(user_id)
                
            else:
                await self._send_error_via_api(user_id, f"❌ Unknown debug type: {debug_type}")
                
        except Exception as e:
            logger.error(f"Error in debug command: {e}")
            await self._send_error_via_api(user_id, f"❌ Debug command failed: {str(e)}")

    async def _debug_discord_subscriptions(self, admin_user_id):
        """Debug execute Discord subscription processing"""
        try:
            # Get all Discord subscriptions
            subscriptions = self.app_manager.essay_summarizer._cleanup_invalid_subscriptions()
            
            if not subscriptions:
                await self._send_message_via_api(admin_user_id, {
                    "embed": {
                        "title": "🔧 Discord Debug - No Subscriptions",
                        "description": "No Discord subscriptions found to process.",
                        "color": "#ffa500"
                    }
                })
                return
            
            # Send start notification
            total_subscriptions = sum(len(user_subs) for user_subs in subscriptions.values())
            await self._send_message_via_api(admin_user_id, {
                "embed": {
                    "title": "🔧 Discord Debug Started",
                    "description": f"Processing {total_subscriptions} Discord subscriptions for {len(subscriptions)} users...",
                    "color": "#0099ff"
                }
            })
            
            processed = 0
            failed = 0
            
            # Process each subscription
            for user_id, user_subscriptions in subscriptions.items():
                for subscription in user_subscriptions:
                    try:
                        category = subscription.get('category', 'all')
                        topic = subscription.get('topic', '')
                        
                        if not topic:
                            failed += 1
                            continue
                        
                        logger.info(f"Debug processing Discord subscription: {category}/{topic} for user {user_id}")
                        result = await self.app_manager.essay_summarizer.summarize_and_push(
                            category, topic, user_id, only_new=True, is_scheduled=True
                        )
                        
                        if result['success']:
                            processed += 1
                        else:
                            failed += 1
                            
                        # Add delay to avoid rate limits
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error processing subscription {subscription}: {e}")
                        failed += 1
                        continue
            
            # Send completion notification
            await self._send_message_via_api(admin_user_id, {
                "embed": {
                    "title": "✅ Discord Debug Completed",
                    "description": f"Discord subscription processing finished.\n\n**Results:**\n• Processed: {processed}\n• Failed: {failed}\n• Total: {processed + failed}",
                    "color": "#00ff00"
                }
            })
            
        except Exception as e:
            logger.error(f"Error in Discord debug: {e}")
            await self._send_error_via_api(admin_user_id, f"❌ Discord debug failed: {str(e)}")

    async def _debug_email_subscriptions(self, admin_user_id):
        """Debug execute Email subscription processing"""
        try:
            # Get all email targets
            email_targets = self.app_manager.essay_summarizer._load_email_targets()
            
            if not email_targets:
                await self._send_message_via_api(admin_user_id, {
                    "embed": {
                        "title": "🔧 Email Debug - No Targets",
                        "description": "No email targets found to process.",
                        "color": "#ffa500"
                    }
                })
                return
            
            # Send start notification
            total_subscriptions = sum(len(paper_types) for paper_types in email_targets.values())
            await self._send_message_via_api(admin_user_id, {
                "embed": {
                    "title": "🔧 Email Debug Started", 
                    "description": f"Processing {total_subscriptions} email subscriptions for {len(email_targets)} email addresses...",
                    "color": "#0099ff"
                }
            })
            
            processed = 0
            failed = 0
            
            # Process each email subscription
            for email, paper_types in email_targets.items():
                if not paper_types:
                    continue
                    
                for paper_type in paper_types:
                    try:
                        # Parse paper type (e.g., 'cs.ai' -> category='cs', topic='ai')
                        if '.' in paper_type:
                            category, topic = paper_type.split('.', 1)
                        else:
                            category = 'all'
                            topic = paper_type
                        
                        logger.info(f"Debug processing email subscription: {category}/{topic} for {email}")
                        
                        # Get papers for this topic
                        result = await self.app_manager.essay_summarizer.summarize_and_push(
                            category, topic, user_id=None, only_new=True, is_scheduled=True
                        )
                        
                        # Prepare papers for email
                        email_papers = result.get('papers', [])
                        email_stats = {
                            'papers_count': len(email_papers),
                            'new_papers': result.get('new_papers', 0),
                            'cached_papers': result.get('cached_papers', 0)
                        }
                        
                        # Skip if no papers found
                        if not email_papers:
                            logger.info(f"No papers found for debug email topic {paper_type} for {email}")
                            continue
                        
                        # Send email
                        email_result = await self.app_manager.essay_summarizer.email_service.send_paper_summary_email(
                            to_emails=[email],
                            category=category,
                            topic=topic,
                            papers=email_papers,
                            stats=email_stats
                        )
                        
                        if email_result['success']:
                            processed += 1
                        else:
                            failed += 1
                            
                        # Add delay between emails
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        logger.error(f"Error processing email subscription {paper_type} for {email}: {e}")
                        failed += 1
                        continue
                
                # Add delay between email addresses
                await asyncio.sleep(5)
            
            # Send completion notification
            await self._send_message_via_api(admin_user_id, {
                "embed": {
                    "title": "✅ Email Debug Completed",
                    "description": f"Email subscription processing finished.\n\n**Results:**\n• Processed: {processed}\n• Failed: {failed}\n• Total: {processed + failed}",
                    "color": "#00ff00"
                }
            })
            
        except Exception as e:
            logger.error(f"Error in Email debug: {e}")
            await self._send_error_via_api(admin_user_id, f"❌ Email debug failed: {str(e)}")

    async def _send_error_via_api(self, user_id, error_message):
        """Send error message via message pusher API"""
        try:
            await self._send_message_via_api(user_id, {
                "embed": {
                    "title": "❌ Error",
                    "description": error_message,
                    "color": "#ff0000"
                }
            })
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def _send_message_via_api(self, user_id, message_data):
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
                        logger.info(f"Debug message sent successfully via API")
                        return {"success": True, "result": result}
                    else:
                        error_text = await response.text()
                        logger.error(f"Message pusher API error {response.status}: {error_text}")
                        return {"success": False, "error": f"API error {response.status}: {error_text}"}
                        
        except Exception as e:
            logger.error(f"Error calling message pusher API: {e}")
            return {"success": False, "error": str(e)}

    
bot = CeciliaBot()

@bot.tree.command(name="hello", description="Say hello to Cecilia!")
async def hello(interaction: discord.Interaction):
    """Basic hello command"""
    await interaction.response.send_message(f"Hello {interaction.user.mention}! I'm Cecilia, your research assistant bot!")

@bot.tree.command(name="summarize", description="Summarize essays on ArXiv about a specific topic")
@app_commands.describe(topic="The research topic to search for")
async def summarize_essays(interaction: discord.Interaction, topic: str):
    """Summarize essays command"""
    await interaction.response.defer()
    
    try:
        # Get summary from app manager
        result = await bot.app_manager.summarize_essays(topic)
        
        # Discord has a 2000 character limit for messages
        if len(result) > 2000:
            # Split into chunks
            chunks = [result[i:i+2000] for i in range(0, len(result), 2000)]
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)
        else:
            await interaction.followup.send(result)
            
    except Exception as e:
        logger.error(f"Error in summarize command: {e}")
        await interaction.followup.send(f"Sorry, there was an error processing your request: {str(e)}")

@bot.tree.command(name="status", description="Check bot status and available apps")
async def status(interaction: discord.Interaction):
    """Status command"""
    embed = discord.Embed(
        title="Cecilia Bot Status",
        description="I'm online and ready to help!",
        color=discord.Color.green()
    )
    embed.add_field(name="Available Apps", value="• Essay Summarizer\n• Message Pusher", inline=False)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="get_my_id", description="Get your Discord user ID for message pusher testing")
async def get_my_id(interaction: discord.Interaction):
    """Get user ID for message pusher testing"""
    embed = discord.Embed(
        title="Your Discord Information",
        description="Use these IDs for message pusher testing",
        color=discord.Color.blue()
    )
    embed.add_field(name="User ID", value=f"`{interaction.user.id}`", inline=False)
    embed.add_field(name="Channel ID", value=f"`{interaction.channel.id}`", inline=False)
    embed.add_field(name="Server ID", value=f"`{interaction.guild.id if interaction.guild else 'DM'}`", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="test_message", description="Test the message pusher by sending yourself a message")
async def test_message(interaction: discord.Interaction):
    """Test message pusher functionality"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Send a test message via the message pusher
        test_data = {
            "user_id": str(interaction.user.id),
            "message": {
                "embed": {
                    "title": "🧪 Message Pusher Test",
                    "description": "This message was sent via the HTTP message pusher API!",
                    "color": "#00FF00",
                    "fields": [
                        {
                            "name": "Test Status",
                            "value": "✅ Success",
                            "inline": True
                        },
                        {
                            "name": "Timestamp",
                            "value": f"<t:{int(interaction.created_at.timestamp())}:f>",
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "Cecilia Message Pusher"
                    }
                }
            }
        }
        
        # Use the message pusher directly
        result = await bot.app_manager.msg_pusher.process_message(test_data)
        
        if result['success']:
            await interaction.followup.send(f"✅ Test message sent successfully! Message ID: `{result['message_id']}`", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Test failed: {result['error']}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in test_message command: {e}")
        await interaction.followup.send(f"❌ Test failed with error: {str(e)}", ephemeral=True)


def run_bot():
    """Function to run the bot"""
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure as e:
        logger.error(f"Discord login failed - invalid token: {e}")
        sys.exit(2)  # Authentication error
    except discord.ConnectionClosed as e:
        logger.error(f"Discord connection closed unexpectedly: {e}")
        sys.exit(7)  # Connection error
    except discord.HTTPException as e:
        if e.status == 401:
            logger.error(f"Discord authentication failed: {e}")
            sys.exit(2)  # Authentication error
        else:
            logger.error(f"Discord HTTP error: {e}")
            sys.exit(8)  # API error
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)  # General error

if __name__ == "__main__":
    run_bot()
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    run_bot()
