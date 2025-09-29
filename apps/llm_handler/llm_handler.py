import asyncio
import aiohttp
import logging
import re
from typing import Optional, Dict, Any
from bot.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OPENAI_BASE_URL, OPENAI_MODEL, LLM_PROVIDER
from bot.auths import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class LLMHandler:
    """Unified handler for LLM operations supporting both Ollama and OpenAI-compatible endpoints"""
    
    def __init__(self):
        self.provider = LLM_PROVIDER.upper()
        
        if self.provider == "OLLAMA":
            self.base_url = OLLAMA_BASE_URL
            self.model = OLLAMA_MODEL
            self.api_key = None
        elif self.provider == "OPENAI":
            self.base_url = OPENAI_BASE_URL
            self.model = OPENAI_MODEL
            self.api_key = OPENAI_API_KEY
            if not self.api_key:
                logger.warning("OpenAI API key not set in auths.py")
        else:
            logger.error(f"Unsupported LLM provider: {self.provider}")
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        
        logger.info(f"LLM Handler initialized with provider: {self.provider}, model: {self.model}")
    
    async def check_service(self) -> bool:
        """Check if the LLM service is running and accessible"""
        try:
            if self.provider == "OLLAMA":
                return await self._check_ollama_service()
            elif self.provider == "OPENAI":
                return await self._check_openai_service()
            return False
        except Exception as e:
            logger.error(f"Error checking {self.provider} service: {e}")
            return False
    
    async def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=5) as response:
                    if response.status == 200:
                        logger.info("Ollama service is running")
                        return True
                    else:
                        logger.error("Ollama service returned non-200 status")
                        return False
        except Exception as e:
            logger.error(f"Ollama service check failed: {e}")
            return False
    
    async def _check_openai_service(self) -> bool:
        """Check if OpenAI service is accessible"""
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return False
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/models", headers=headers, timeout=10) as response:
                    if response.status == 200:
                        logger.info("OpenAI service is accessible")
                        return True
                    else:
                        logger.error(f"OpenAI service returned status {response.status}")
                        return False
        except Exception as e:
            logger.error(f"OpenAI service check failed: {e}")
            return False
    
    async def summarize_paper(self, paper_content: str, paper_title: str) -> Optional[str]:
        """Summarize paper content using the configured LLM provider"""
        try:
            if self.provider == "OLLAMA":
                return await self._summarize_with_ollama(paper_content, paper_title)
            elif self.provider == "OPENAI":
                return await self._summarize_with_openai(paper_content, paper_title)
            return None
        except Exception as e:
            logger.error(f"Error summarizing with {self.provider}: {e}")
            return None
    
    def _create_summarization_prompt(self, paper_content: str, paper_title: str) -> str:
        """Create the summarization prompt"""
        return f"""请为这篇研究论文提供清晰简洁的总结。重点关注：
1. 主要研究问题
2. 关键方法或途径
3. 主要发现或贡献
4. 实际意义或应用

总结应该便于一般学术读者理解，应该简短同时保留所有重点和部分细节，500字以内。**请用中文而不是英文撰写回答!**

总结应该使用正规的markdown格式书写，条理清晰，但你不需将文本包在```markdown代码框中，并且不要使用表格。如果你想要用"#### 1. 主要研究问题"这种方式给大点加标题，请更改为"__1. 主要研究问题:__"并且**不要在其后加额外的空行**！当且仅当你想要进一步分小点时使用这种形式，否则请使用"- **主要研究问题：**..."这种形式分大点。

论文标题：{paper_title}

论文内容：
{paper_content[:30000]}

再重申一次，请为这篇研究论文提供清晰简洁的总结。重点关注：
1. 主要研究问题
2. 关键方法或途径
3. 主要发现或贡献
4. 实际意义或应用

总结应该便于一般学术读者理解，应该简短同时保留所有重点和部分细节，500字以内。**请用中文而不是英文撰写回答!**

总结应该使用正规的markdown格式书写，条理清晰，但你不需将文本包在```markdown代码框中，并且不要使用表格。如果你想要用"#### 1. 主要研究问题"这种方式给大点加标题，请更改为"__1. 主要研究问题:__"并且**不要在其后加额外的空行**！当且仅当你想要进一步分小点时使用这种形式，否则请使用"- **主要研究问题：**..."这种形式分大点。
"""
    
    async def _summarize_with_ollama(self, paper_content: str, paper_title: str) -> Optional[str]:
        """Summarize paper content using Ollama"""
        try:
            prompt = self._create_summarization_prompt(paper_content, paper_title)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=120) as response:
                    if response.status == 200:
                        result = await response.json()
                        summary = result.get('response', '')
                        
                        # Remove thinking tags if present (for reasoning models)
                        if '<think>' in summary:
                            summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL)
                            summary = summary.strip()
                        
                        logger.info(f"Successfully generated summary with Ollama ({len(summary)} chars)")
                        return summary
                    else:
                        logger.error(f"Ollama API error: {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Ollama request timeout")
            return None
        except Exception as e:
            logger.error(f"Error summarizing with Ollama: {e}")
            return None
    
    async def _summarize_with_openai(self, paper_content: str, paper_title: str) -> Optional[str]:
        """Summarize paper content using OpenAI-compatible endpoint"""
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return None
        
        try:
            prompt = self._create_summarization_prompt(paper_content, paper_title)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的学术论文总结助手，擅长用中文简洁地总结研究论文的核心内容。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.3
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", 
                                      headers=headers, 
                                      json=payload, 
                                      timeout=3000) as response:
                    if response.status == 200:
                        result = await response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            summary = result['choices'][0]['message']['content'].strip()
                            logger.info(f"Successfully generated summary with OpenAI ({len(summary)} chars)")
                            return summary
                        else:
                            logger.error("No choices in OpenAI response")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error {response.status}: {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("OpenAI request timeout")
            return None
        except Exception as e:
            logger.error(f"Error summarizing with OpenAI: {e}")
            return None
    
    async def ask_ai(self, prompt: str) -> Optional[str]:
        """Send a prompt to the AI and return the answer as a string"""
        try:
            if self.provider == "OLLAMA":
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=120) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result.get('response', '').strip()
                        else:
                            logger.error(f"Ollama API error: {response.status}")
                            return None
            elif self.provider == "OPENAI":
                if not self.api_key:
                    logger.error("OpenAI API key not configured")
                    return None
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/chat/completions",
                                           headers=headers,
                                           json=payload,
                                           timeout=aiohttp.ClientTimeout(total=3000000)) as response:
                        if response.status == 200:
                            result = await response.json()
                            if 'choices' in result and len(result['choices']) > 0:
                                return result['choices'][0]['message']['content'].strip()
                            else:
                                logger.error("No choices in OpenAI response")
                                return None
                        else:
                            error_text = await response.text()
                            logger.error(f"OpenAI API error {response.status}: {error_text}")
                            return None
            else:
                logger.error(f"Unsupported provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"Error in ask_ai: {e}")
            return None

    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current LLM provider"""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key) if self.provider == "OPENAI" else None
        }
