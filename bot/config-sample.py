# Ollama Configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5vl:32b"

# OpenAI Configuration
OPENAI_BASE_URL = "http://localhost:1234/v1"  # Can be changed to any OpenAI-compatible endpoint
OPENAI_MODEL = "qwen/qwen3-30b-a3b-2507"

# LLM Provider Configuration
LLM_PROVIDER = "OLLAMA"  # Options: "OLLAMA" or "OPENAI"

# Scheduler Configuration
# Note: Times are in 24-hour format (0-23 for hours, 0-59 for minutes)
SUMMARIZATION_SCHEDULE_HOUR = 6    # Hour to start paper summarization (24-hour format)
SUMMARIZATION_SCHEDULE_MINUTE = 0  # Minute to start paper summarization
NOTIFICATION_SCHEDULE_HOUR = 7     # Hour to send notifications (Discord + Email)
NOTIFICATION_SCHEDULE_MINUTE = 0   # Minute to send notifications

# Subscription Configuration
SUBSCRIPTION_ONLY_NEW = True  # Only send papers that haven't been processed before today

# Scheduler Explanation:
# 
# The system uses two separate schedulers:
# 
# 1. SUMMARIZATION SCHEDULER (default: 6:00 AM)
#    - Downloads and processes all papers from ArXiv
#    - Generates AI summaries using configured LLM
#    - Stores results for later notification
#    - This is the heavy processing phase
# 
# 2. NOTIFICATION SCHEDULER (default: 7:00 AM) 
#    - Sends Discord messages to subscribed users
#    - Sends email notifications to configured addresses
#    - Uses the results from the summarization phase
#    - This is the lightweight delivery phase
