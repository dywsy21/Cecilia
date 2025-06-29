import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from .auths import DISCORD_TOKEN, APP_ID
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
