# Cecilia

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
Handles slash commands and Discord API interactions.

**Available Commands:**
- `/hello` - Greet the bot
- `/summarize <topic>` - Summarize ArXiv papers on a topic
- `/status` - Check bot status
- `/get_my_id` - Get your Discord IDs for testing
- `/test_message` - Test internal message pusher

### Message Pusher (Internal)
Accepts HTTP POST requests from other server processes to send Discord messages.

**Internal API Endpoint:** `http://localhost:8011/push`

**JSON Format:**
```json
{
  "user_id": "123456789012345678",
  "message": {
    "content": "Your message content",
    "embed": {
      "title": "Optional Title",
      "description": "Optional description",
      "color": "#FF5733"
    }
  },
  "channel_id": "987654321098765432"
}
```

### Discord Interactions Webhook
Handles Discord slash command interactions via webhook.

**Public Endpoint:** Available via Nginx at `/bot/interactions`

## Deployment

1. **Setup Credentials:**
   ```bash
   cp bot/auths-sample.py bot/auths.py
   # Fill in your Discord bot credentials
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Nginx:**
   Add the following to your Nginx configuration:
   ```nginx
   # Discord interactions endpoint
   location /bot/ {
       proxy_pass http://127.0.0.1:8010/;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

4. **Run the Bot:**
   ```bash
   python main.py
   ```

5. **Configure Discord Application:**
   - Set interactions endpoint URL to: `https://yourdomain.com:18080/bot/interactions`
   - Enable necessary bot permissions and scopes

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

## Security Notes

- Port 8011 is localhost-only for internal communication
- Discord interactions are verified via webhook signatures
- Only essential ports are exposed through Nginx
