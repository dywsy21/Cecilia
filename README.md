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
Handles Discord slash command interactions via webhook with proper signature verification.

**Public Endpoint:** Available via Nginx at `/bot/interactions`

## Deployment

1. **Setup Credentials:**
   ```bash
   cp bot/auths-sample.py bot/auths.py
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
   python main.py
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

## Security Notes

- Port 8011 is localhost-only for internal communication
- Discord interactions are verified via Ed25519 signature verification
- PUBLIC_KEY must be correctly configured for webhook verification
- Only essential ports are exposed through Nginx

## Troubleshooting

If Discord interactions endpoint verification fails:

1. **Check PUBLIC_KEY:** Ensure it matches your Discord app's public key exactly
   ```bash
   # Test the health endpoint to verify public key is loaded
   curl https://dywsy21.cn:18080/bot/health
   ```

2. **Verify Dependencies:**
   ```bash
   pip install pynacl>=1.5.0
   ```

3. **Test Routing:**
   ```bash
   # Test that the routing works correctly
   curl -X GET https://dywsy21.cn:18080/bot/health
   # Should return bot health status
   ```

4. **Manual PING Test:**
   ```bash
   # Test PING directly to the bot server (from server)
   curl -X POST http://127.0.0.1:8010/interactions \
     -H "Content-Type: application/json" \
     -d '{"type": 1}'
   # Should return {"type": 1}
   ```

5. **Check Nginx Configuration:**
   - Ensure the `rewrite` rule is properly stripping `/bot` prefix
   - Verify signature headers are being forwarded
   - Restart Nginx after configuration changes: `sudo systemctl reload nginx`

6. **Check Logs:**
   ```bash
   # Look for routing and signature verification errors
   tail -f /var/log/nginx/dywsy21_ssl_error.log
   # Check bot logs for verification details
   ```

7. **Discord Developer Portal:**
   - Verify the interactions endpoint URL is exactly: `https://dywsy21.cn:18080/bot/interactions`
   - Check that the bot has the `applications.commands` scope
   - Ensure the PUBLIC_KEY matches what's shown in the portal

Common Issues:
- **404 Not Found:** Usually a routing problem - check Nginx rewrite rule
- **401 Unauthorized:** Usually a signature verification problem - check PUBLIC_KEY
- **Content-Type missing:** Ensure all responses include `Content-Type: application/json`
- **Nginx buffering:** Can interfere with signature verification - disable buffering
- **Case sensitivity:** PUBLIC_KEY and signature headers are case-sensitive

## Updated Nginx Configuration

The key change is the `rewrite` rule that strips the `/bot` prefix:

```nginx
location /bot/ {
    rewrite ^/bot/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:8010;
    # ... other proxy settings
}
```

This ensures that:
- `https://dywsy21.cn:18080/bot/interactions` → `http://127.0.0.1:8010/interactions`
- `https://dywsy21.cn:18080/bot/health` → `http://127.0.0.1:8010/health`
