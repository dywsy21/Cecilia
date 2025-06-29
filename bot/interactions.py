import asyncio
import json
import logging
from aiohttp import web
import discord
from discord.ext import commands
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import time
from .auths import PUBLIC_KEY
from apps.apps import AppManager

logger = logging.getLogger(__name__)

class InteractionServer:
    """Handles Discord interactions via HTTP webhook"""
    
    def __init__(self, app_manager: AppManager):
        self.app_manager = app_manager
        self.verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        self.app = web.Application()
        self.setup_routes()
        logger.info("InteractionServer initialized")
    
    def setup_routes(self):
        """Setup HTTP routes for interactions"""
        self.app.router.add_post('/interactions', self.handle_interaction)
        self.app.router.add_get('/health', self.health_check)
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "discord_interactions",
            "port": 8010
        })
    
    def verify_signature(self, signature: str, timestamp: str, body: bytes) -> bool:
        """Verify Discord interaction signature"""
        try:
            self.verify_key.verify(
                timestamp.encode() + body,
                bytes.fromhex(signature)
            )
            return True
        except BadSignatureError:
            return False
    
    async def handle_interaction(self, request):
        """Handle Discord interaction webhook"""
        try:
            # Get headers
            signature = request.headers.get('X-Signature-Ed25519')
            timestamp = request.headers.get('X-Signature-Timestamp')
            
            if not signature or not timestamp:
                logger.warning("Missing signature headers")
                return web.Response(status=401, text="Missing signature headers")
            
            # Read body
            body = await request.read()
            
            # Verify signature
            if not self.verify_signature(signature, timestamp, body):
                logger.warning("Invalid signature")
                return web.Response(status=401, text="Invalid signature")
            
            # Parse interaction data
            data = json.loads(body.decode('utf-8'))
            interaction_type = data.get('type')
            
            logger.info(f"Received interaction type: {interaction_type}")
            
            # Handle ping (verification)
            if interaction_type == 1:
                logger.info("Responding to Discord ping")
                return web.json_response({"type": 1})
            
            # Handle application command
            if interaction_type == 2:
                response = await self.handle_application_command(data)
                return web.json_response(response)
            
            # Handle other interaction types
            return web.json_response({
                "type": 4,
                "data": {
                    "content": "Interaction type not supported"
                }
            })
            
        except Exception as e:
            logger.error(f"Error handling interaction: {e}")
            return web.Response(status=500, text="Internal server error")
    
    async def handle_application_command(self, data):
        """Handle application command interactions"""
        try:
            command_name = data['data']['name']
            user = data['member']['user'] if 'member' in data else data['user']
            
            if command_name == 'hello':
                return {
                    "type": 4,
                    "data": {
                        "content": f"Hello <@{user['id']}>! I'm Cecilia, your research assistant bot!"
                    }
                }
            
            elif command_name == 'summarize':
                topic = None
                for option in data['data'].get('options', []):
                    if option['name'] == 'topic':
                        topic = option['value']
                        break
                
                if not topic:
                    return {
                        "type": 4,
                        "data": {
                            "content": "Please provide a topic to summarize."
                        }
                    }
                
                # Defer response for long-running operations
                return {
                    "type": 5
                }
                # Note: You'd need to implement follow-up for the actual summary
            
            elif command_name == 'status':
                status = await self.app_manager.get_status()
                embed = {
                    "title": "Cecilia Bot Status",
                    "description": "I'm online and ready to help!",
                    "color": 0x00FF00,
                    "fields": [
                        {
                            "name": "Available Apps",
                            "value": "• Essay Summarizer\n• Message Pusher",
                            "inline": False
                        },
                        {
                            "name": "Total Apps",
                            "value": str(status['total_apps']),
                            "inline": True
                        }
                    ]
                }
                
                return {
                    "type": 4,
                    "data": {
                        "embeds": [embed]
                    }
                }
            
            else:
                return {
                    "type": 4,
                    "data": {
                        "content": f"Unknown command: {command_name}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return {
                "type": 4,
                "data": {
                    "content": "Sorry, there was an error processing your request."
                }
            }
    
    async def start_server(self, port: int = 8010):
        """Start the interaction server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Interaction server started on port {port}")
        
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Interaction server stopping...")
            await runner.cleanup()

def create_interaction_server(app_manager: AppManager):
    """Factory function to create InteractionServer instance"""
    return InteractionServer(app_manager)
