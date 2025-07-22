import asyncio
import aiohttp
import psutil
import logging
import json
import subprocess
from typing import Dict, Optional

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
        """Get GPU usage using nvidia-smi"""
        try:
            # Try to run nvidia-smi command
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return {'available': False, 'gpus': [], 'error': 'nvidia-smi failed'}
            
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 6:
                        try:
                            gpu_info = {
                                'id': int(parts[0]),
                                'name': parts[1],
                                'load': float(parts[2]),
                                'memory_used': float(parts[3]),
                                'memory_total': float(parts[4]),
                                'memory_percent': round((float(parts[3]) / float(parts[4]) * 100), 1),
                                'temperature': float(parts[5]) if parts[5] != '[Not Supported]' else None
                            }
                            gpus.append(gpu_info)
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse GPU info: {parts}, error: {e}")
            
            return {
                'available': len(gpus) > 0,
                'count': len(gpus),
                'gpus': gpus
            }
            
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi command timed out")
            return {'available': False, 'gpus': [], 'error': 'timeout'}
        except FileNotFoundError:
            logger.debug("nvidia-smi not found, no NVIDIA GPU available")
            return {'available': False, 'gpus': [], 'error': 'nvidia-smi not found'}
        except Exception as e:
            logger.error(f"Error getting GPU usage with nvidia-smi: {e}")
            return {'available': False, 'gpus': [], 'error': str(e)}
    
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
