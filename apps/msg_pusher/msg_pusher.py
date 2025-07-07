import asyncio
import json
import logging
from aiohttp import web, ClientSession
import jsonschema
from jsonschema import validate
import discord
from typing import Dict, Any, Optional
from .schema import MESSAGE_SCHEMA

logger = logging.getLogger(__name__)

class MessagePusher:
    """Handles incoming HTTP messages and pushes them to Discord users"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.app = web.Application()
        self.setup_routes()
        logger.info("MessagePusher initialized")
    
    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_post('/push', self.handle_message)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/schema', self.get_schema)
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "msg_pusher",
            "port": 8011
        })
    
    async def get_schema(self, request):
        """Return the JSON schema for message format"""
        return web.json_response(MESSAGE_SCHEMA)
    
    async def handle_message(self, request):
        """Handle incoming message push requests"""
        try:
            # Parse JSON payload
            data = await request.json()
            logger.info(f"Received message push request: {data.get('user_id', 'unknown')}")
            
            # Validate against schema
            validate(instance=data, schema=MESSAGE_SCHEMA)
            
            # Process the message
            result = await self.process_message(data)
            
            if result['success']:
                return web.json_response({
                    "status": "success",
                    "message": "Message sent successfully",
                    "message_id": result.get('message_id')
                }, status=200)
            else:
                return web.json_response({
                    "status": "error",
                    "message": result['error']
                }, status=400)
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request")
            return web.json_response({
                "status": "error",
                "message": "Invalid JSON format"
            }, status=400)
            
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Schema validation error: {e.message}")
            return web.json_response({
                "status": "error",
                "message": f"Schema validation failed: {e.message}",
                "schema_path": list(e.absolute_path)
            }, status=400)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)
    
    async def process_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and send the message to Discord"""
        try:
            user_id = int(data['user_id'])
            message_data = data['message']
            channel_id = data.get('channel_id')
            priority = data.get('priority', 'normal')
            
            # Use fallback channel if no channel_id provided
            fallback_channel_id = "1190649951693316169"
            
            # Get user or channel
            if channel_id:
                target = self.bot.get_channel(int(channel_id))
                if not target:
                    return {"success": False, "error": f"Channel {channel_id} not found"}
            else:
                # Try to get user from cache first
                target = self.bot.get_user(user_id)
                
                # If not in cache, try to fetch from Discord API
                if not target:
                    try:
                        target = await self.bot.fetch_user(user_id)
                        logger.info(f"Fetched user {user_id} from Discord API")
                    except discord.NotFound:
                        logger.warning(f"User {user_id} not found, using fallback channel {fallback_channel_id}")
                        target = self.bot.get_channel(int(fallback_channel_id))
                        if not target:
                            return {"success": False, "error": f"User {user_id} does not exist and fallback channel {fallback_channel_id} not found"}
                    except discord.Forbidden:
                        logger.warning(f"Cannot access user {user_id}, using fallback channel {fallback_channel_id}")
                        target = self.bot.get_channel(int(fallback_channel_id))
                        if not target:
                            return {"success": False, "error": f"Bot cannot access user {user_id} and fallback channel {fallback_channel_id} not found"}
                    except Exception as e:
                        logger.warning(f"Failed to fetch user {user_id}: {e}, using fallback channel {fallback_channel_id}")
                        target = self.bot.get_channel(int(fallback_channel_id))
                        if not target:
                            return {"success": False, "error": f"Failed to fetch user {user_id} and fallback channel {fallback_channel_id} not found: {e}"}
            
            # Build Discord message
            discord_message = await self.build_discord_message(message_data)
            
            # Send message
            sent_message = await target.send(**discord_message)
            
            logger.info(f"Message sent successfully to {target} (ID: {sent_message.id})")
            return {
                "success": True,
                "message_id": str(sent_message.id),
                "target": str(target)
            }
            
        except discord.Forbidden as e:
            # If DM fails, try fallback channel
            if not channel_id:  # Only try fallback if we were originally trying DM
                try:
                    fallback_channel_id = "1190649951693316169"
                    fallback_target = self.bot.get_channel(int(fallback_channel_id))
                    if fallback_target:
                        discord_message = await self.build_discord_message(message_data)
                        # Add mention to the message content for fallback channel
                        if 'content' in discord_message:
                            discord_message['content'] = f"<@{user_id}> {discord_message['content']}"
                        else:
                            discord_message['content'] = f"<@{user_id}>"
                        
                        sent_message = await fallback_target.send(**discord_message)
                        logger.info(f"Message sent to fallback channel {fallback_target} for user {user_id}")
                        return {
                            "success": True,
                            "message_id": str(sent_message.id),
                            "target": str(fallback_target),
                            "fallback": True
                        }
                except Exception as fallback_error:
                    logger.error(f"Fallback channel also failed: {fallback_error}")
            
            return {"success": False, "error": "Bot doesn't have permission to message this user/channel. The user may have DMs disabled or doesn't share a server with the bot."}
        except discord.HTTPException as e:
            return {"success": False, "error": f"Discord API error: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}
    
    async def build_discord_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Discord message from message data"""
        result = {}
        
        # Add content if present
        if 'content' in message_data:
            result['content'] = message_data['content']
        
        # Add embed if present
        if 'embed' in message_data:
            embed_data = message_data['embed']
            embed = discord.Embed()
            
            if 'title' in embed_data:
                embed.title = embed_data['title']
            if 'description' in embed_data:
                embed.description = embed_data['description']
            if 'color' in embed_data:
                # Convert hex color to int
                color_str = embed_data['color'].lstrip('#')
                embed.color = int(color_str, 16)
            
            # Add fields
            if 'fields' in embed_data:
                for field in embed_data['fields']:
                    embed.add_field(
                        name=field['name'],
                        value=field['value'],
                        inline=field.get('inline', False)
                    )
            
            # Add footer
            if 'footer' in embed_data:
                embed.set_footer(text=embed_data['footer']['text'])
            
            result['embed'] = embed
        
        # Add view with components if present
        if 'components' in message_data:
            view = discord.ui.View()
            for component in message_data['components']:
                if component['type'] == 'button':
                    if 'url' in component:
                        button = discord.ui.Button(
                            label=component['label'],
                            url=component['url'],
                            style=discord.ButtonStyle.link
                        )
                        view.add_item(button)
            
            if len(view.children) > 0:
                result['view'] = view
        
        return result
    
    async def start_server(self, port: int = 8011):
        """Start the HTTP server"""
        try:
            runner = web.AppRunner(self.app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            logger.info(f"MessagePusher server started on port {port}")
            
            # Keep the server running
            try:
                while True:
                    await asyncio.sleep(3600)  # Sleep for 1 hour
            except asyncio.CancelledError:
                logger.info("MessagePusher server stopping...")
                await runner.cleanup()
                
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"Port {port} already in use - cannot start MessagePusher server")
                from ..apps import CeciliaServiceError
                raise CeciliaServiceError(f"Cannot bind to port {port} - address already in use")
            else:
                logger.error(f"OS error starting MessagePusher server: {e}")
                from ..apps import CeciliaServiceError
                raise CeciliaServiceError(f"System error starting MessagePusher server: {e}")
        except Exception as e:
            logger.error(f"Failed to start MessagePusher server: {e}")
            from ..apps import CeciliaServiceError
            raise CeciliaServiceError(f"Cannot start MessagePusher server: {e}")

def create_message_pusher(bot_instance):
    """Factory function to create MessagePusher instance"""
    return MessagePusher(bot_instance)
