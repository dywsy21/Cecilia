# Cecilia

![Cecilia](pics/bot.jpg)

A Discord bot with Vue frontend for ArXiv paper subscriptions, deployable on server with message pushing capabilities!

## Structure

The bot runs multiple services:

- **Port 8010**: Discord interactions webhook endpoint (accessible via `/bot`)
- **Port 8011**: Internal message pusher (localhost only)
- **Port 8012**: Email subscription service API (localhost only)
- **Port 8075**: Vue frontend development server (development only)

File structure:

- `bot`: Discord bot integration and interactions handling
- `apps`: Backend functionalities
  - `msg_pusher`: Internal message pushing service
  - `email_service`: SMTP email service for automated notifications
  - `essay_summarizer`: ArXiv paper summarization subscription service
  - `subscription_service`: Email subscription management with 6-digit verification
- `ui`: Vue 3 frontend for email subscriptions
  - `src`: Vue application source code
  - `dist`: Production build output

## Services

### Vue Frontend (NEW)

Modern Vue 3 frontend for email subscription management.

**Features:**

- Professional subscription form with ArXiv category selection
- Email verification with 6-digit codes
- Real-time validation and user feedback
- Responsive design for desktop and mobile
- Rate limiting and spam protection
- Search and filter functionality for research topics

**Development:**

```bash
cd ui
npm run dev
```

**Production:**

```bash
cd ui
npm run build
# Serve ui/dist/ via nginx at https://subscription.dywsy21.cn:18080
```

### Email Subscription Service (NEW)

Handles email subscription creation and verification with secure 6-digit codes.

**API Endpoints:**

- `POST /api/subscription/create` - Create new subscription with email verification
- `POST /api/subscription/verify` - Verify email with 6-digit code
- `POST /api/subscription/resend` - Resend verification code

**Features:**

- Secure 6-digit email verification
- Rate limiting per IP and endpoint
- Automatic session cleanup
- Support for multiple ArXiv categories
- Integration with existing email notification system

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

This service lets users subscribe to specific fields of academic research and informs them of the latest progress by summarizing the latest arxiv papers using AI on a regular basis.

#### Subscription & Registered Commands

The subscribed topics' summarizing work begins every 07:00 AM, and results are pushed via **Message Pusher** and **via Email** (if configured).

1. `/subscribe list`: list all subscribed topics
2. `/subscribe add [CATEGORY] [TOPIC]`: add a specific topic to subscription
3. `/subscribe remove [CATEGORY] [TOPIC]`: remove this subscription
4. `/subscribe now [CATEGORY] [TOPIC]`: instantly start summarization and push results

#### Email Notification System

**Setup:**

1. **Configure Email Settings:** Fill in email credentials in `bot/auths.py`
2. **Configure Email Recipients:** Use the Vue frontend at `https://subscription.dywsy21.cn:18080` or manually edit `data/essay_summarizer/email_targets.json`:

   ```json
   {
     "researcher@university.edu": ["cs.ai", "cs.cv"],
     "student@school.edu": ["cs.lg", "stat.ml"]
   }
   ```

**New Subscription Process:**

1. User visits the Vue frontend
2. Selects research interests (minimum 5 topics)
3. Enters email address
4. Receives 6-digit verification code
5. Confirms subscription
6. Added to daily email delivery system

**Email Features:**

- **Rich HTML Emails:** Beautiful, responsive email templates with paper summaries
- **Daily Automated Delivery:** Emails sent at 7:00 AM along with Discord notifications
- **Per-User Topic Subscriptions:** Each email can subscribe to specific ArXiv categories
- **Comprehensive Content:** Paper titles, authors, AI summaries, PDF links, and statistics
- **PDF Attachments:** Full papers attached with organized filenames

## Deployment

### Quick Start

1. **Run Installation Script:**

   ```bash
   chmod +x install.sh
   ./install.sh
   ```

2. **Configure Credentials:**

   ```bash
   # Edit Discord bot credentials and email settings
   nano bot/auths.py
   
   # Edit bot configuration
   nano bot/config.py
   ```

3. **Configure Nginx for Frontend:**

   ```nginx
   # Subscription frontend
   location /subscription/ {
       rewrite ^/subscription/(.*)$ /$1 break;
       proxy_pass http://127.0.0.1:8075;  # Development
       # For production: serve ui/dist/ directly
   }
   
   # Discord interactions endpoint
   location /bot/ {
       rewrite ^/bot/(.*)$ /$1 break;
       proxy_pass http://127.0.0.1:8010;
       proxy_set_header X-Signature-Ed25519 $http_x_signature_ed25519;
       proxy_set_header X-Signature-Timestamp $http_x_signature_timestamp;
       proxy_buffering off;
       proxy_request_buffering off;
   }
   ```

4. **Deploy All Services:**

   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

5. **Start Frontend (Development):**

   ```bash
   cd ui
   chmod +x serve.sh
   ./serve.sh
   ```

### Production Deployment

For production, build and serve the frontend statically:

```bash
cd ui
npm run build
# Serve ui/dist/ via nginx at https://subscription.dywsy21.cn:18080
```

### Testing

**Test Email System:**

```bash
python test_email_sending.py
```

**Test Vue Frontend:**

1. Visit `http://localhost:8080` (development) or `https://subscription.dywsy21.cn:18080` (production)
2. Fill out subscription form
3. Check email for verification code
4. Complete verification process

## Architecture

![Architecture Diagram](docs/architecture.png)

## Troubleshooting

**Common Issues:**

- If the bot doesn't respond to commands, check if the Discord bot is running and commands are registered.
- For email issues, ensure SMTP settings are correct and the email service is running.
- If the Vue frontend doesn't load, check the development server logs and ensure the correct port is being used.

**Logs:**

- Bot logs: `logs/bot.log`
- Email service logs: `logs/email_service.log`
- Vue frontend logs: Check browser console and network tab

**Tips:**

- Always ensure your server's firewall allows traffic on the required ports (8010, 8011, 8012, 8075).
- For production, consider using a process manager like `pm2` to keep the bot and services running.
- Regularly check for updates in the ArXiv API and adjust the integration if necessary.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to the contributors and supporters of the Cecilia project.
- Special thanks to the developers of the libraries and frameworks used in this project.
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
