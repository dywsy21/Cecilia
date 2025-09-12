# Ollama Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5vl:32b"

# OpenAI Configuration
OPENAI_BASE_URL = "http://192.168.1.106:1234/v1"  # Can be changed to any OpenAI-compatible endpoint
OPENAI_MODEL = "openai/gpt-oss-120b"

# LLM Provider Configuration
LLM_PROVIDER = "OPENAI"  # Options: "OLLAMA" or "OPENAI"

# Subscription Configuration
SUBSCRIPTION_ONLY_NEW = True
