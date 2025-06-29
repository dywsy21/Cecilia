import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from aiohttp import web
import json
import nacl.signing
import nacl.encoding
from .auths import DISCORD_TOKEN, APP_ID, PUBLIC_KEY
from apps.apps import AppManager

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
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

    def verify_signature(self, signature: str, timestamp: str, body: bytes) -> bool:
        """Verify Discord interaction signature"""
        try:
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(PUBLIC_KEY))
            verify_key.verify(
                timestamp.encode() + body, 
                bytes.fromhex(signature),
                encoder=nacl.encoding.HexEncoder
            )
            return True
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    def create_interactions_app(self):
        """Create aiohttp app for Discord interactions"""
        app = web.Application()
        app.router.add_post('/interactions', self.handle_interaction)
        app.router.add_get('/health', self.health_check)
        return app

    async def handle_interaction(self, request):
        """Handle Discord interactions webhook"""
        try:
            # Get headers for verification
            signature = request.headers.get('X-Signature-Ed25519')
            timestamp = request.headers.get('X-Signature-Timestamp')
            
            if not signature or not timestamp:
                logger.error("Missing signature headers")
                return web.json_response({'error': 'Missing signature headers'}, status=401)
            
            # Get raw body for verification
            body = await request.read()
            
            # Verify signature
            if not self.verify_signature(signature, timestamp, body):
                logger.error("Invalid signature")
                return web.json_response({'error': 'Invalid signature'}, status=401)
            
            # Parse JSON data
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in request body")
                return web.json_response({'error': 'Invalid JSON'}, status=400)
            
            interaction_type = data.get('type')
            
            # Handle PING (type 1)
            if interaction_type == 1:
                logger.info("Received PING from Discord")
                return web.json_response({'type': 1})
            
            # Handle Application Command (type 2)
            if interaction_type == 2:
                logger.info(f"Received application command: {data.get('data', {}).get('name', 'unknown')}")
                
                command_name = data.get('data', {}).get('name')
                
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
                                'value': 'Webhook Active',
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
                
                elif command_name == 'summarize':
                    # For complex commands that need async processing, defer and use followup
                    return web.json_response({
                        'type': 5,  # Deferred response
                        'data': {
                            'content': 'Processing your request...'
                        }
                    })
                
                else:
                    return web.json_response({
                        'type': 4,
                        'data': {
                            'content': f'Command `{command_name}` received via webhook!'
                        }
                    })
            
            # Handle other interaction types
            logger.warning(f"Unhandled interaction type: {interaction_type}")
            return web.json_response({'error': 'Unhandled interaction type'}, status=400)
            
        except Exception as e:
            logger.error(f"Error handling interaction: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)

    async def health_check(self, request):
        """Health check for interactions endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'discord_interactions',
            'bot_ready': self.is_ready(),
            'verification': 'enabled'
        })

    async def start_interactions_server(self, port: int = 8010):
        """Start the Discord interactions webhook server"""
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
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    run_bot()
