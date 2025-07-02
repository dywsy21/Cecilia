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
  - `essay_summarizer`: ArXiv paper summarization

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

**JSON Format:**: See `apps/msg_pusher/schema.py`

### Essay Summarizer Services

#### Overview

This service lets the user subscribe to a specific field of academic researches and informs them of the latest progress (summarize the latest arxiv papers regarding that field using AI) on a regular basis.

#### Subscription & Registered Commands

The subscribed topics' Summarizing work will begin every 07:00 am in the morning, and once done, results will be pushed to the user **via Message Pusher**.

1. `/subscribe list`: list all subscribed topics
2. `/subscribe add [TOPIC]`: add a specific topic to subscription. The topics added will be stored on the disk.
3. `/subscribe remove [TOPIC]`: remove this subscription.
4. `/instantlyshow [TOPIC]`: instantly start an Essay Summarizer job on the given topic, reply to the user with "Processing..." and push the results to the user via the Message Pusher once done.

#### Arxiv api

Refer to [Arxiv api User Manual](https://info.arxiv.org/help/api/user-manual.html) for more info.

Use the `http://export.arxiv.org/api/{method_name}?{parameters}` api port to get essays regarding the topic.

We'll just use this: `https://export.arxiv.org/api/query?search_query=all:[TOPIC]&sortBy=lastUpdatedDate&sortOrder=descending`, where [TOPIC] is the user provided param in their command.

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

We use Ollama to run models locally. To launch Ollama service:

```sh
ollama serve
```

To generate a response using AI:

```sh
curl http://localhost:11434/api/generate -d '{
  "model": "deepseek-r1:32b",
  "prompt":"Why is the sky blue?",
  "stream": false
}'
```

We use the equivalent python code to interact with Ollama.

We use deepseek:32b to summarize the results, and will remove the `<think>.*</think>` thinking part.

#### Summarizing & Pushing Workflow

```
SummarizeAndPush(topic):
    Use arxiv api to retrieve the latest papers of that topic, at most 10 papers
    for each paper:
        Check on disk, if already summarized before: 
            continue (don't add to overall results)
        Get the paper's pdf file
        Use markitdown to get the markdown version of this pdf
        Use Ollama api to summarize the paper (needs to be easy to understand)
        Add result to overall results (including the pdf link)
    Construct a pretty discord flavor json message based on the overall results
    Send the json message to the user via Message Pusher
    Store the pdfs and the summarization results on disk
```

#### Subscription Workflow

```
SummarizeFromSubscription():
    for each topic in subscribed topics:
        SummarizeAndPush(topic)

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
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Nginx:**
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

4. **Run the Bot:**
   ```bash
   ./deploy.sh
   ```

5. **Configure Discord Application:**
   - Set interactions endpoint URL to: `https://dywsy21.cn:18080/bot/interactions`
   - Enable necessary bot permissions and scopes
   - Ensure PUBLIC_KEY is correctly set in auths.py

## Internal Message Pushing

Other services on your server can send messages via:

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


