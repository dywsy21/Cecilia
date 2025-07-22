#!/usr/bin/env python3
"""
Simple test for Ollama monitoring functionality
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apps.ollama_monitor.ollama_monitor import OllamaMonitor

async def test_ollama_monitoring():
    """Test Ollama monitoring functionality"""
    print("🔍 Testing Ollama Monitor...")
    print("=" * 50)
    
    monitor = OllamaMonitor()
    
    try:
        async with monitor as m:
            # Test Ollama status
            print("\n📊 Testing Ollama API status...")
            status = await m.check_ollama_status()
            print(f"Status: {status}")
            
            # Test CPU usage
            print("\n💻 Testing CPU monitoring...")
            cpu = m.get_cpu_usage()
            print(f"CPU Usage: {cpu}%")
            
            # Test memory usage
            print("\n🧠 Testing Memory monitoring...")
            memory = m.get_memory_usage()
            print(f"Memory: {memory}")
            
            # Test GPU usage
            print("\n🎮 Testing GPU monitoring...")
            gpu = m.get_gpu_usage()
            print(f"GPU: {gpu}")
            
            # Test Ollama processes
            print("\n🔄 Testing Ollama process detection...")
            processes = m.get_ollama_process_info()
            print(f"Processes: {processes}")
            
            # Test full status
            print("\n📈 Testing full status...")
            full_status = await m.get_full_status()
            print(f"Full Status Keys: {list(full_status.keys())}")
            
            print("\n✅ All tests completed!")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ollama_monitoring())
