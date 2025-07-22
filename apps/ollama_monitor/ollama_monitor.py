import asyncio
import aiohttp
import psutil
import logging
import json
from typing import Dict, Optional

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    print("Warning: GPUtil not available. GPU monitoring disabled.")

logger = logging.getLogger(__name__)

class OllamaMonitor:
    """Monitor Ollama service and system resources"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_ollama_status(self) -> Dict:
        """Check if Ollama is running and get basic info"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('models', [])
                    return {
                        'status': 'online',
                        'models_count': len(models),
                        'models': [model.get('name', 'unknown') for model in models[:5]]  # Top 5 models
                    }
                else:
                    return {'status': 'error', 'models_count': 0, 'models': []}
        except asyncio.TimeoutError:
            logger.warning("Ollama API timeout")
            return {'status': 'timeout', 'models_count': 0, 'models': []}
        except Exception as e:
            logger.warning(f"Cannot connect to Ollama: {e}")
            return {'status': 'offline', 'models_count': 0, 'models': []}
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            return psutil.cpu_percent(interval=1)
        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return 0.0
    
    def get_memory_usage(self) -> Dict:
        """Get current memory usage"""
        try:
            memory = psutil.virtual_memory()
            return {
                'percent': memory.percent,
                'total_gb': round(memory.total / (1024**3), 1),
                'used_gb': round(memory.used / (1024**3), 1),
                'available_gb': round(memory.available / (1024**3), 1)
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {'percent': 0.0, 'total_gb': 0.0, 'used_gb': 0.0, 'available_gb': 0.0}
    
    def get_gpu_usage(self) -> Dict:
        """Get GPU usage if available"""
        if not GPU_AVAILABLE:
            return {'available': False, 'gpus': []}
        
        try:
            gpus = GPUtil.getGPUs()
            gpu_info = []
            
            for gpu in gpus:
                gpu_info.append({
                    'id': gpu.id,
                    'name': gpu.name,
                    'load': round(gpu.load * 100, 1),  # Convert to percentage
                    'memory_used': round(gpu.memoryUsed, 1),
                    'memory_total': round(gpu.memoryTotal, 1),
                    'memory_percent': round((gpu.memoryUsed / gpu.memoryTotal * 100), 1),
                    'temperature': gpu.temperature if hasattr(gpu, 'temperature') else None
                })
            
            return {
                'available': True,
                'count': len(gpus),
                'gpus': gpu_info
            }
        except Exception as e:
            logger.error(f"Error getting GPU usage: {e}")
            return {'available': False, 'gpus': []}
    
    def get_ollama_process_info(self) -> Dict:
        """Get Ollama process information"""
        try:
            ollama_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        ollama_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_mb': round(proc.info['memory_info'].rss / (1024**2), 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                'processes_found': len(ollama_processes),
                'processes': ollama_processes,
                'total_cpu': sum(p['cpu_percent'] for p in ollama_processes),
                'total_memory_mb': sum(p['memory_mb'] for p in ollama_processes)
            }
        except Exception as e:
            logger.error(f"Error getting Ollama process info: {e}")
            return {'processes_found': 0, 'processes': [], 'total_cpu': 0.0, 'total_memory_mb': 0.0}
    
    async def get_full_status(self) -> Dict:
        """Get comprehensive Ollama and system status"""
        ollama_status = await self.check_ollama_status()
        cpu_usage = self.get_cpu_usage()
        memory_usage = self.get_memory_usage()
        gpu_usage = self.get_gpu_usage()
        process_info = self.get_ollama_process_info()
        
        return {
            'ollama': ollama_status,
            'system': {
                'cpu_percent': cpu_usage,
                'memory': memory_usage,
                'gpu': gpu_usage
            },
            'ollama_processes': process_info,
            'timestamp': psutil.boot_time()
        }
