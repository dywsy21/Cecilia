# Cecilia

![Cecilia](pics/bot.jpg)

A Discord bot deployable on server with message pushing capabilities!

## Structure

The bot runs multiple services:

- **Port 8010**: Discord interactions webhook endpoint (accessible via `/bot`)
- **Port 8011**: Internal message pusher (localhost only)

File structure:

- `bot`: Discord bot integration and interactions handling
- `apps`: Backend functionalities
  - `msg_pusher`: Internal message pushing service
  - `email_service`: SMTP email service for automated notifications
  - `essay_summarizer`: ArXiv paper summarization subscription service

## Services

### Discord Bot

Handles slash commands and Discord API interactions via webhook.

**Available Commands:**

- `/hello` - Greet the bot
- `/status` - Check bot status
- `/get_my_id` - Get your Discord IDs for testing
- Arxiv Essay Summarizer commands, see below

**Note:** Commands are registered automatically via HTTP API when the bot starts.

### Message Pusher (Internal)

Accepts HTTP POST requests from other server processes to send Discord messages.

**Internal API Endpoint:** `http://localhost:8011/push`

Other services on your server can send messages through Cecilia Bot via curl-ing 8011 port:

```bash
curl -X POST http://localhost:8011/push \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_DISCORD_ID",
    "message": {
      "content": "Hello from internal service!"
    }
  }'
```

**Complete JSON Schema:** To know the complete supported JSON Format, see `apps/msg_pusher/schema.py`.

### Essay Summarizer Services

#### Overview

This service lets the user subscribe to a specific field of academic researches and informs them of the latest progress (summarize the latest arxiv papers regarding that field using AI) on a regular basis.

#### Subscription & Registered Commands

The subscribed topics' Summarizing work will begin every 07:00 am in the morning, and once done, results will be pushed to the user **via Message Pusher** and **via Email** (if configured).

1. `/subscribe list`: list all subscribed topics
2. `/subscribe add [CATEGORY] [TOPIC]`: add a specific topic to subscription. The topics added will be stored on the disk. 
3. `/subscribe remove [CATEGORY] [TOPIC]`: remove this subscription.
4. `/subscribe now [CATEGORY] [TOPIC]`: instantly start an Essay Summarizer job on the given topic, reply to the user with "Processing..." and push the results to the user via the Message Pusher once done. Specially, /subscribe now will push you all 10 essays regardless of whether they have been sent to the user before.

An example of '[CATEGORY].[TOPIC]' will be 'cs.ai'.

#### Email Notification System

**Configuration:** Configure your preferred LLM provider in `bot/config.py`:

```python
# Choose your LLM provider
LLM_PROVIDER = "OPENAI"  # Options: "OLLAMA" or "OPENAI"

# Ollama Configuration (for local models)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1:32b"

# OpenAI Configuration (for OpenAI or compatible APIs)
OPENAI_BASE_URL = "https://api.openai.com/v1"  # Can be changed to any OpenAI-compatible endpoint
OPENAI_MODEL = "gpt-4o-mini"
```

Add your OpenAI API key in `bot/auths.py` if using OpenAI:
```python
OPENAI_API_KEY = "your-api-key-here"
```

**Setup:**
1. **Configure Email Settings:** Fill in email credentials in `bot/auths.py`:
   ```python
   EMAIL_SMTP_HOST='smtp.qq.com'
   EMAIL_SMTP_PORT=465
   EMAIL_SMTP_SECURE=True
   EMAIL_SMTP_USER='your-email@example.com'
   EMAIL_SMTP_PASS='your-app-password'
   EMAIL_SMTP_NAME='Cecilia Bot'
   EMAIL_SMTP_LOGGER=True
   EMAIL_SMTP_TLS_REJECT_UNAUTH=True
   EMAIL_SMTP_IGNORE_TLS=False
   CUSTOM_EMAIL_FOOTER='Your custom footer message'
   ```

2. **Configure Email Recipients:** Add email addresses to `data/essay_summarizer/email_targets.json`:
   ```json
   [
     "researcher1@university.edu",
     "researcher2@company.com",
     "team@research-group.org"
   ]
   ```

**Email Features:**

- **Rich HTML Emails:** Beautiful, responsive email templates with paper summaries
- **Daily Automated Delivery:** Emails sent at 7:00 AM along with Discord notifications
- **Comprehensive Content:** Each email includes:
  - Paper titles, authors, and categories
  - AI-generated Chinese summaries
  - Direct links to ArXiv PDFs
  - Processing statistics (new vs cached papers)
  - Professional formatting optimized for academic content

**Email Sending Availability Testing:**

```bash
python test_email_sending.py
```

This test script will:

- Verify email configuration completeness
- Test SMTP connection and authentication
- Send sample emails with paper summaries
- Validate email formatting and delivery

And the email system will:

- Send emails for each subscribed topic during the daily 7:00 AM run
- Include recent papers context even when no new papers are found
- Provide detailed delivery logs and error reporting
- Support multiple SMTP providers (Gmail, Outlook, QQ Mail, etc.)

#### Arxiv api

Refer to [Arxiv api User Manual](https://info.arxiv.org/help/api/user-manual.html) for more info.

Use the `http://export.arxiv.org/api/{method_name}?{parameters}` api port to get essays regarding the topic.

We'll just use this: `https://export.arxiv.org/api/query?search_query=[CATEGORY]:[TOPIC]&sortBy=lastUpdatedDate&sortOrder=descending`, where [CATEGORY] and [TOPIC] are the user provided params in their command.

For example: `https://export.arxiv.org/api/query?search_query=all:ai&sortBy=lastUpdatedDate&sortOrder=descending` yields:

```
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <link href="http://arxiv.org/api/query?search_query%3Dall%3Aai%26id_list%3D%26start%3D0%26max_results%3D10" rel="self" type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:ai&amp;id_list=&amp;start=0&amp;max_results=10</title>
  <id>http://arxiv.org/api/84VvdLEAVGq1lbittOBlSKC4Ow8</id>
  <updated>2025-07-01T00:00:00-04:00</updated>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">38373</opensearch:totalResults>
  <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
  <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">10</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2409.12922v1</id>
    <updated>2024-08-26T04:41:21Z</updated>
    <published>2024-08-26T04:41:21Z</published>
    <title>AI Thinking: A framework for rethinking artificial intelligence in
  practice</title>
    <summary>  Artificial intelligence is transforming the way we work with information
across disciplines and practical contexts. A growing range of disciplines are
now involved in studying, developing, and assessing the use of AI in practice,
but these disciplines often employ conflicting understandings of what AI is and
what is involved in its use. New, interdisciplinary approaches are needed to
bridge competing conceptualisations of AI in practice and help shape the future
of AI use. I propose a novel conceptual framework called AI Thinking, which
models key decisions and considerations involved in AI use across disciplinary
perspectives. The AI Thinking model addresses five practice-based competencies
involved in applying AI in context: motivating AI use in information processes,
formulating AI methods, assessing available tools and technologies, selecting
appropriate data, and situating AI in the sociotechnical contexts it is used
in. A hypothetical case study is provided to illustrate the application of AI
Thinking in practice. This article situates AI Thinking in broader
cross-disciplinary discourses of AI, including its connections to ongoing
discussions around AI literacy and AI-driven innovation. AI Thinking can help
to bridge divides between academic disciplines and diverse contexts of AI use,
and to reshape the future of AI in practice.
</summary>
    <author>
      <name>Denis Newman-Griffis</name>
    </author>
    <arxiv:comment xmlns:arxiv="http://arxiv.org/schemas/atom">30 pages, 2 figures</arxiv:comment>
    <link href="http://arxiv.org/abs/2409.12922v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2409.12922v1" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.CY" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.CY" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.HC" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
 ...
 </feed>
```

The pdf file can be downloaded from `<link title="pdf" href="http://arxiv.org/pdf/2409.12922v1" rel="related" type="application/pdf"/>`.

#### AI Usage Guides

The system supports multiple LLM providers for paper summarization:

**1. Ollama (Local):**
```sh
sudo systemctl start ollama
sudo systemctl enable ollama
```

**2. OpenAI-Compatible APIs:**
Configure in `bot/config.py`:
```python
LLM_PROVIDER = "OPENAI"  # or "OLLAMA"
OPENAI_BASE_URL = "https://api.openai.com/v1"  # or your custom endpoint
OPENAI_MODEL = "gpt-4o-mini"
```

Add your API key in `bot/auths.py`:
```python
OPENAI_API_KEY = "your-api-key-here"
```

**Testing LLM Connection:**
```sh
# For Ollama
curl http://localhost:11434/api/generate -d '{
  "model": "deepseek-r1:32b",
  "prompt":"Why is the sky blue?",
  "stream": false
}'

# For OpenAI-compatible endpoints
curl -X GET "https://api.openai.com/v1/models" \
  -H "Authorization: Bearer your-api-key"
```

The system automatically uses the configured LLM provider and removes thinking tags (`<think>.*</think>`) for reasoning models.

#### Summarizing & Pushing Workflow

```
SummarizeAndPush(topic):
    Use arxiv api to retrieve the latest papers of that topic, at most 10 papers
    Check if Ollama service is running, if not, raise exception
    for each paper:
        Check on disk, if already summarized before: 
            if this SummarizeAndPush is invoked by /subscribe now:
                add the paper's result to overall results
            else:
                continue
        Get the paper's pdf file
        Use markitdown to get the markdown version of this pdf
        Use Ollama api to summarize the paper in an easy-to-understand tone
        Add result to overall results, including the authors, pdf link, summary and categories&topics of the paper
    Construct a pretty discord flavor json message based on the overall results
    Send the json message to the user via Message Pusher
    Store the pdfs and the summarization results on disk
```

#### Subscription Workflow

```
SummarizeFromSubscription():
    for each topic in subscribed topics:
        SummarizeAndPush(topic)        # Send to Discord users
        SendEmailNotification(topic)   # Send to email recipients

Every 07:00 a.m. in the morning:
    SummarizeFromSubscription()
```

### Discord Interactions Webhook

Handles Discord slash command interactions via webhook with proper signature verification.

**Public Endpoint:** Available via Nginx at `/bot/interactions`

## Deployment

1. **Setup Credentials:**
   ```bash
   mv bot/auths-sample.py bot/auths.py
   # Fill in your Discord bot credentials including PUBLIC_KEY
   # Fill in your email SMTP settings for automated notifications
   ```

2. **Setup Email Recipients (Optional):**
   ```bash
   # Create email targets file
   mkdir -p data/essay_summarizer
   echo '["your-email@example.com"]' > data/essay_summarizer/email_targets.json
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Test Email Configuration (Optional):**
   ```bash
   python test.py
   ```

5. **Configure Nginx:**
   Add the following to your Nginx configuration:
   ```nginx
   # Discord interactions endpoint - UPDATED CONFIGURATION
   location /bot/ {
       # Strip the /bot prefix when proxying
       rewrite ^/bot/(.*)$ /$1 break;
       proxy_pass http://127.0.0.1:8010;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_set_header X-Signature-Ed25519 $http_x_signature_ed25519;
       proxy_set_header X-Signature-Timestamp $http_x_signature_timestamp;
       
       # Important: Don't buffer the request body for signature verification
       proxy_buffering off;
       proxy_request_buffering off;
   }
   ```

6. **Run the Bot:**
   ```bash
   ./deploy.sh
   ```

7. **Configure Discord Application:**
   - Set interactions endpoint URL to your own interaction endpoint on discord dev website
   - Enable necessary bot permissions and scopes
   - Ensure PUBLIC_KEY is correctly set in auths.py
