import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional
import aiohttp
import markdown
from weasyprint import HTML, CSS
from datetime import datetime
from pytz import timezone

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from aiohttp import web

from .markdown2pdf import convert_markdown_to_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeepResearchWrapper:
    """Wrapper for Deep Research MCP server that integrates with Discord bot"""
    
    def __init__(self, inner_port: int, discord_channel_id: str, bot_instance=None):
        self.inner_port = inner_port
        self.discord_channel_id = discord_channel_id
        self.bot_instance = bot_instance
        self.server = Server("deep-research-wrapper")
        self.tools = []  # Store tools for direct access
        self.setup_tools()
        
    def setup_tools(self):
        """Setup MCP tools"""
        # Define tools with complete schema for N8N compatibility
        deep_research_tool = types.Tool(
            name="deep-research",
            description="Conduct comprehensive research on any topic and automatically deliver results to Discord",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research topic or question, fill in the clarifying questions and answers into here too"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language of the response",
                        "default": "en",
                        "enum": ["en", "zh", "es", "fr", "de", "ja", "ko", "ru"]
                    },
                    "max_result": {
                        "type": "integer",
                        "description": "Maximum search results",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20
                    },
                    "enable_citation_image": {
                        "type": "boolean",
                        "description": "Include citation images",
                        "default": False
                    },
                    "enable_references": {
                        "type": "boolean",
                        "description": "Include references",
                        "default": True
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        )
        
        # Add missing outputSchema and annotations for N8N compatibility
        # We need to manually add these to the tool's model dump
        self.tools = [deep_research_tool]
        
        # Setup MCP server handlers
        @self.server.list_tools()
        async def list_tools() -> List[types.Tool]:
            return self.tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            if name == "deep-research":
                return await self.handle_deep_research(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def handle_deep_research(self, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """Handle deep research request"""
        try:
            query = arguments.get("query", "")
            if not query:
                return [types.TextContent(type="text", text="❌ Error: Research query is required")]
            
            logger.info(f"Starting deep research for query: {query}")
            
            # Create data/deep_research directory if it doesn't exist
            data_dir = os.path.join('.', "data", "deep_research")
            os.makedirs(data_dir, exist_ok=True)
            
            # Ensure hosted-files directory exists
            os.makedirs('/home/ubuntu/hosted-files/deep-research/', exist_ok=True)
            
            # Generate filename with timestamp
            tz = timezone('Asia/Shanghai')
            timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
            
            filename = f"resp_{timestamp}"
            pdf_filename = filename + '.pdf'
            txtpath = os.path.join(data_dir, filename + '.txt')
            pdfpath = '/home/ubuntu/hosted-files/deep-research/' + pdf_filename
            
            # Start deep research via inner MCP server
            research_result = await self.call_inner_deep_research(arguments, txtpath)
            
            if not research_result:
                return [types.TextContent(type="text", text="❌ Error: Failed to get research results from inner server")]
            
            # Convert markdown to PDF
            try:
                pdf_path = await convert_markdown_to_pdf(txtpath, query, pdfpath)
                logger.info(f"PDF conversion completed: {pdf_path}")
            except Exception as pdf_error:
                logger.error(f"PDF conversion failed: {pdf_error}")
                return [types.TextContent(type="text", text=f"❌ Error: PDF conversion failed: {str(pdf_error)}")]
            
            # Send to Discord
            try:
                await self.send_to_discord(pdf_path, query)
                logger.info("Discord notification sent successfully")
            except Exception as discord_error:
                logger.error(f"Discord notification failed: {discord_error}")
                # Don't fail the whole operation if Discord fails
        
        # Create hosted URL
        hosted_url = f"https://files.dywsy21.cn:18080/deep-research/{pdf_filename}"
        
        # Return success message with proper TextContent format
        success_message = f"✅ Deep research session on '{query}' has successfully finished. Results have been delivered to Discord channel. The PDF can be viewed at {hosted_url}."
        
        return [types.TextContent(type="text", text=success_message)]
        
        except Exception as e:
            logger.error(f"Error in deep research: {e}")
            return [types.TextContent(type="text", text=f"❌ Error: {str(e)}")]
    
    async def call_inner_deep_research(self, arguments: Dict[str, Any], txtpath) -> Optional[str]:
        """Call the inner deep research MCP server via HTTP MCP protocol"""
        try:
            url = f"http://localhost:{self.inner_port}/api/mcp"
            
            # Prepare MCP request payload
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "deep-research",
                    "arguments": {
                        "query": arguments.get("query", ""),
                        "language": arguments.get("language", "en"),
                        "maxResult": arguments.get("max_result", 10),
                        "enableCitationImage": arguments.get("enable_citation_image", False),
                        "enableReferences": arguments.get("enable_references", True)
                    }
                }
            }
            
            headers = {"Content-Type": "application/json"}
            timeout = aiohttp.ClientTimeout(total=360000)  # 100 hours timeout
            
            full_response = ""
            
            # Create connector with unlimited read buffer size and no chunk limit
            connector = aiohttp.TCPConnector(
                limit=100000000,  # No connection limit
                limit_per_host=100000000,  # No per-host limit
            )
            
            async with aiohttp.ClientSession(
                timeout=timeout, 
                connector=connector,
                read_bufsize=100000000  # Unlimited read buffer
            ) as session:
                async with session.post(
                    url, 
                    json=mcp_request, 
                    headers=headers,
                    max_line_size=100000000,  # No line size limit
                    max_field_size=100000000  # No field size limit
                ) as response:
                    if response.status != 200:
                        logger.error(f"Inner server error: {response.status}")
                        error_text = await response.text()
                        logger.error(f"Inner server error response: {error_text}")
                        return None
                    
                    # Read response content without chunk limits
                    try:
                        # Read the entire response at once to avoid chunking issues
                        response_data = await response.read()
                        response_text = response_data.decode('utf-8')
                        
                        # Save response to file for debugging and archival
                        try:
                            # Save the raw response
                            with open(txtpath, 'w', encoding='utf-8') as f:
                                f.write(response_text)
                            
                            logger.info(f"Response saved to: {txtpath + '.txt'}")
                            
                        except Exception as save_error:
                            logger.warning(f"Could not save response to file: {save_error}")
                        
                        # Handle multiple JSON responses if they exist
                        for line in response_text.strip().split('\n'):
                            line = line.strip()
                            
                            # Skip empty lines
                            if not line:
                                continue
                                
                            try:
                                # Parse JSON-RPC response
                                json_response = json.loads(line)
                                
                                # Handle different response types
                                if "result" in json_response:
                                    # Final result
                                    result = json_response["result"]
                                    if isinstance(result, list) and len(result) > 0:
                                        # Extract content from TextContent
                                        content_item = result[0]
                                        if isinstance(content_item, dict) and "text" in content_item:
                                            full_response = content_item["text"]
                                        elif isinstance(content_item, str):
                                            full_response = content_item
                                    break
                                elif "method" in json_response and json_response["method"] == "notifications/progress":
                                    # Progress notification - can be logged but we continue waiting
                                    logger.info(f"Deep research progress: {json_response.get('params', {})}")
                                    continue
                                elif "error" in json_response:
                                    # Error response
                                    logger.error(f"Inner server returned error: {json_response['error']}")
                                    return None
                                    
                            except json.JSONDecodeError:
                                # If it's not JSON, treat as raw content
                                full_response += line + "\n"
                        
                    except Exception as e:
                        logger.error(f"Error reading response data: {e}")
                        return None
            
            return full_response.strip() if full_response else None
            
        except Exception as e:
            logger.error(f"Error calling inner deep research: {e}")
            return None
    
    
    async def send_to_discord(self, pdf_path: str, topic: str):
        """Send PDF report link to Discord channel with preview embed"""
        try:
            if not self.bot_instance:
                logger.error("Bot instance not available for Discord sending")
                return
            
            channel = self.bot_instance.get_channel(int(self.discord_channel_id))
            if not channel:
                logger.error(f"Discord channel {self.discord_channel_id} not found")
                return
            
            # Extract PDF filename from path
            pdf_filename = os.path.basename(pdf_path)
            hosted_url = f"https://files.dywsy21.cn:18080/deep-research/{pdf_filename}"
            
            # Create cute greeting message
            greeting_messages = [
                f"🔬✨ Hey there! I just finished a super deep research session on **{topic}**! 📚",
                f"🎉 Woohoo! Your research report on **{topic}** is ready! 🤓",
                f"📖💫 Ta-da! I've completed an amazing deep dive into **{topic}** for you! 🌟",
                f"🚀🧠 Boom! Just wrapped up some serious research on **{topic}**! 💡",
                f"🎯📊 Mission accomplished! Here's your comprehensive research on **{topic}**! ✨"
            ]
            
            import random
            greeting = random.choice(greeting_messages)
            
            # Create embed with PDF preview
            import discord
            embed = discord.Embed(
                title="🔬 Deep Research Report Completed!",
                description=f"I've conducted a thorough research analysis on your requested topic and compiled everything into a beautiful PDF report! 📄✨",
                color=0x00ff9f,  # Bright mint green
                timestamp=datetime.utcnow(),
                url=hosted_url  # Make the embed title clickable
            )
            
            embed.add_field(
                name="📝 Research Topic",
                value=f"```{topic}```",
                inline=False
            )
            
            embed.add_field(
                name="📊 Report Details", 
                value="• Comprehensive analysis\n• Multiple sources\n• AI-powered insights\n• Professional formatting",
                inline=True
            )
            
            embed.add_field(
                name="📅 Generated",
                value=f"<t:{int(datetime.utcnow().timestamp())}:R>",
                inline=True
            )
            
            # Add download link field
            embed.add_field(
                name="📥 Access Report",
                value=f"[🔗 **View & Download PDF**]({hosted_url})\n📱 *Click to open in browser*",
                inline=False
            )
            
            # Set PDF as image for Discord preview (Discord will attempt to show PDF preview)
            embed.set_image(url=hosted_url)
            
            embed.set_footer(
                text=f"PDF: {pdf_filename} • Powered by Cecilia's Deep Research System 🤖",
                icon_url="https://files.dywsy21.cn:18080/homepage/avatar.png"  # Optional: Add bot avatar
            )
            
            # Send message with embed containing PDF link
            await channel.send(
                content=greeting,
                embed=embed
            )
            
            logger.info(f"Successfully sent research report link to Discord channel {self.discord_channel_id}")
            logger.info(f"PDF accessible at: {hosted_url}")
            
        except Exception as e:
            logger.error(f"Error sending to Discord: {e}")
            raise

    async def start_http_server(self, port: int = 3334):
        """Start HTTP server with MCP endpoints for the deep research wrapper"""
        try:
            app = web.Application()
            
            # Health check endpoint
            async def health_check(request):
                return web.json_response({
                    'status': 'healthy',
                    'service': 'deep-research-wrapper',
                    'inner_port': self.inner_port,
                    'discord_channel': self.discord_channel_id,
                    'mcp_protocol': '2024-11-05',
                    'tools_available': len(self.tools)
                })
            
            # MCP HTTP endpoint with proper streaming and error handling
            async def handle_mcp_request(request):
                data = None
                try:
                    # Parse JSON-RPC request
                    data = await request.json()
                    request_id = data.get("id")
                    method = data.get("method")
                    
                    logger.info(f"MCP Request: {method} (ID: {request_id})")
                    
                    # Handle initialization
                    if method == "initialize":
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {
                                    "tools": {"listChanged": False},
                                    "resources": {},
                                    "prompts": {}
                                },
                                "serverInfo": {
                                    "name": "deep-research-wrapper",
                                    "version": "1.0.0"
                                }
                            }
                        }
                        return web.json_response(response)
                    
                    # Handle tools listing
                    elif method == "tools/list":
                        try:
                            # Create N8N-compatible tool definitions with required fields
                            tools_for_n8n = []
                            for tool in self.tools:
                                tool_dict = tool.model_dump()
                                # Add missing fields that N8N expects
                                tool_dict["outputSchema"] = {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "description": "Content type"
                                        },
                                        "text": {
                                            "type": "string",
                                            "description": "Research completion status message"
                                        }
                                    },
                                    "required": ["type", "text"]
                                }
                                tool_dict["annotations"] = {
                                    "audience": ["general"],
                                    "category": "research",
                                    "tags": ["research", "ai", "analysis", "pdf", "discord"]
                                }
                                tools_for_n8n.append(tool_dict)
                            
                            response = {
                                "jsonrpc": "2.0", 
                                "id": request_id,
                                "result": {"tools": tools_for_n8n}
                            }
                            logger.info(f"Returning {len(tools_for_n8n)} tools with complete schemas")
                            return web.json_response(response)
                        except Exception as e:
                            logger.error(f"Error listing tools: {e}")
                            error_response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32603,
                                    "message": f"Internal error listing tools: {str(e)}"
                                }
                            }
                            return web.json_response(error_response, status=500)
                    
                    # Handle tool calls
                    elif method == "tools/call":
                        params = data.get("params", {})
                        tool_name = params.get("name")
                        arguments = params.get("arguments", {})
                        
                        logger.info(f"Tool call request: {tool_name} with args: {arguments}")
                        
                        if tool_name != "deep-research":
                            error_response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32601,
                                    "message": f"Unknown tool: {tool_name}. Available tools: {[t.name for t in self.tools]}"
                                }
                            }
                            return web.json_response(error_response, status=400)
                        
                        # Validate input arguments against schema
                        try:
                            # Basic validation
                            if not arguments.get("query"):
                                error_response = {
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32602,
                                        "message": "Invalid params: 'query' is required"
                                    }
                                }
                                return web.json_response(error_response, status=400)
                            
                            # Execute deep research
                            logger.info(f"Executing deep research with arguments: {arguments}")
                            result = await self.handle_deep_research(arguments)
                            
                            # Convert TextContent objects to proper format for N8N
                            response_content = []
                            for item in result:
                                if hasattr(item, 'model_dump'):
                                    response_content.append(item.model_dump())
                                elif hasattr(item, '__dict__'):
                                    response_content.append(item.__dict__)
                                else:
                                    # Fallback: create proper TextContent structure
                                    response_content.append({
                                        "type": "text",
                                        "text": str(item)
                                    })
                            
                            # Return standard JSON-RPC response for N8N compatibility
                            final_response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": response_content
                            }
                            
                            logger.info(f"Deep research completed successfully, returning response with {len(response_content)} items")
                            return web.json_response(final_response)
                            
                        except Exception as e:
                            logger.error(f"Error in tool execution: {e}")
                            error_response = {
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32603,
                                    "message": f"Internal error: {str(e)}"
                                }
                            }
                            return web.json_response(error_response, status=500)
                    
                    # Handle notifications (for compatibility)
                    elif method.startswith("notifications/"):
                        # Just acknowledge notifications
                        return web.json_response({"jsonrpc": "2.0", "id": request_id, "result": {}})
                    
                    else:
                        # Unknown method
                        logger.warning(f"Unknown method: {method}")
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {method}. Available methods: initialize, tools/list, tools/call"
                            }
                        }
                        return web.json_response(error_response, status=400)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: Invalid JSON - {str(e)}"
                        }
                    }
                    return web.json_response(error_response, status=400)
                except Exception as e:
                    logger.error(f"Error handling MCP request: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id", None) if data and isinstance(data, dict) else None,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
                    return web.json_response(error_response, status=500)
            
            # Handle OPTIONS requests for CORS preflight
            async def options_handler(request):
                response = web.Response(status=204)
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                response.headers['Access-Control-Max-Age'] = '86400'
                return response
            
            # Test endpoint to verify server is working
            async def test_endpoint(request):
                # Test tool schema compliance
                test_tool = self.tools[0].model_dump()
                test_tool["outputSchema"] = {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "text": {"type": "string"}
                    }
                }
                test_tool["annotations"] = {
                    "audience": ["general"],
                    "category": "research"
                }
                
                return web.json_response({
                    'service': 'deep-research-wrapper-mcp',
                    'status': 'operational',
                    'tools': [tool.name for tool in self.tools],
                    'endpoints': ['/api/mcp', '/health', '/test'],
                    'mcp_protocol': '2024-11-05',
                    'sample_tool_schema': test_tool
                })
            
            # Add routes
            app.router.add_get('/health', health_check)
            app.router.add_get('/status', health_check)
            app.router.add_get('/test', test_endpoint)
            app.router.add_post('/api/mcp', handle_mcp_request)
            app.router.add_route('OPTIONS', '/api/mcp', options_handler)
            
            # Simple CORS middleware for non-streaming responses
            @web.middleware
            async def cors_middleware(request, handler):
                if request.method == 'OPTIONS':
                    return await handler(request)
                
                try:
                    response = await handler(request)
                    
                    # Add CORS headers to all responses
                    if hasattr(response, 'headers'):
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                    
                    return response
                except Exception as e:
                    logger.error(f"Error in CORS middleware: {e}")
                    raise
            
            app.middlewares.append(cors_middleware)
            
            # Start server
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', port)
            await site.start()
            
            logger.info(f"Deep Research Wrapper HTTP MCP server started on port {port}")
            logger.info(f"MCP endpoint available at: http://127.0.0.1:{port}/api/mcp")
            logger.info(f"Health check available at: http://127.0.0.1:{port}/health")
            logger.info(f"Test endpoint available at: http://127.0.0.1:{port}/test")
            logger.info(f"Available tools: {[tool.name for tool in self.tools]}")
            
            # Keep the server running
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                logger.info("Deep Research Wrapper server stopping...")
                await runner.cleanup()
                
        except Exception as e:
            logger.error(f"Error starting Deep Research Wrapper HTTP server: {e}")
            raise

async def create_deep_research_wrapper_server(inner_port: int, discord_channel_id: str, bot_instance=None):
    """Create and return the deep research wrapper server"""
    wrapper = DeepResearchWrapper(inner_port, discord_channel_id, bot_instance)
    return wrapper.server

async def run_deep_research_wrapper_server(outer_port: int, inner_port: int, discord_channel_id: str, bot_instance=None):
    """Run the deep research wrapper HTTP server"""
    try:
        wrapper = DeepResearchWrapper(inner_port, discord_channel_id, bot_instance)
        await wrapper.start_http_server(outer_port)
            
    except Exception as e:
        logger.error(f"Error running deep research wrapper server: {e}")
        raise

if __name__ == "__main__":
    # For standalone testing
    import sys
    if len(sys.argv) < 3:
        print("Usage: python deep_research_wrapper.py <inner_port> <discord_channel_id>")
        sys.exit(1)
    
    inner_port = int(sys.argv[1])
    discord_channel_id = sys.argv[2]
    
    asyncio.run(run_deep_research_wrapper_server(3334, inner_port, discord_channel_id))
