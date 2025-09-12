# Ollama Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5vl:32b"

# OpenAI Configuration
OPENAI_BASE_URL = "http://localhost:1234/v1"  # Can be changed to any OpenAI-compatible endpoint
OPENAI_MODEL = "qwen/qwen3-30b-a3b-2507"

# LLM Provider Configuration
LLM_PROVIDER = "OPENAI"  # Options: "OLLAMA" or "OPENAI"

# Subscription Configuration
SUBSCRIPTION_ONLY_NEW = True
