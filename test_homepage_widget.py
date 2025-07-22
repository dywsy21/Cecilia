#!/usr/bin/env python3
"""
Test script for Cecilia Homepage Widget API endpoints
"""

import asyncio
import aiohttp
import json
import sys

async def test_endpoints(base_url="http://localhost:8010"):
    """Test the /status, /stats, and /ollama endpoints"""
    
    endpoints = [
        f"{base_url}/status",
        f"{base_url}/stats",
        f"{base_url}/ollama",
        f"{base_url}/health"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            try:
                print(f"\n🔍 Testing {endpoint}")
                async with session.get(endpoint) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Status: {response.status}")
                        print(f"📊 Response: {json.dumps(data, indent=2)}")
                    else:
                        print(f"❌ Status: {response.status}")
                        text = await response.text()
                        print(f"📝 Response: {text}")
            except aiohttp.ClientConnectorError:
                print(f"❌ Cannot connect to {endpoint}")
                print("   Make sure Cecilia is running on port 8010")
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8010"
    
    print(f"Testing Cecilia Homepage Widget API endpoints (including Ollama monitoring) at {base_url}")
    print("=" * 80)
    
    asyncio.run(test_endpoints(base_url))

if __name__ == "__main__":
    main()
