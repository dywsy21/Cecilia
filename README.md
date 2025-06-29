# Cecilia

A Discord bot deployable on server with HTTP interaction support!

## Architecture

- **Port 8010**: Discord interactions endpoint (`/bot`) - 对外开放
- **Port 8011**: Message pusher API (`localhost` only) - 仅内部通信

## Structure

- `bot`: Discord bot integration and interaction handling
- `apps`: Backend functionalities
  - `msg_pusher`: HTTP API for internal services to send Discord messages
  - `essay_summarizer`: ArXiv paper summarization service

## Discord Setup

1. Create a Discord application at https://discord.com/developers/applications
2. Set the **Interactions Endpoint URL** to: `https://yourdomain.com:18080/bot/interactions`
3. Add slash commands in the Discord Developer Portal:
   - `/hello` - Basic greeting
   - `/summarize` - Summarize research papers (with topic parameter)
   - `/status` - Check bot status

## Message Pusher API (Internal Use Only)

**注意**: 此 API 仅供服务器内部其他进程使用，不对外开放。

Internal services can send messages to Discord via HTTP POST to `http://localhost:8011/push`.

### JSON Schema

```json
{
  "user_id": "123456789012345678",
  "message": {
    "content": "Your message content",
    "embed": {
      "title": "Title",
      "description": "Description", 
      "color": "#FF5733"
    }
  },
  "channel_id": "987654321098765432"
}
```

### Example Usage (Server Internal Only)

```bash
# 仅在服务器内部使用
curl -X POST http://localhost:8011/push \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "channel_id": "CHANNEL_ID",
    "message": {
      "content": "Hello from internal service!"
    }
  }'
```

## Deploy

1. Create `bot/auths.py` with your Discord credentials:
   ```python
   APP_ID = 'your_app_id'
   DISCORD_TOKEN = 'your_bot_token'
   PUBLIC_KEY = 'your_public_key'
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Nginx to proxy **only** `/bot` to port 8010 (不要暴露端口 8011)

4. Run the application:
   ```bash
   python main.py
   ```

## API Endpoints

### Public (via Nginx proxy)
- `GET /bot/health` - Health check for interaction service
- `POST /bot/interactions` - Discord interactions webhook

### Internal Only (localhost)
- `GET http://localhost:8011/health` - Message pusher health check
- `POST http://localhost:8011/push` - Send message to Discord (内部使用)
- `GET http://localhost:8011/schema` - Get message schema

## Security Notes

- 端口 8011 的 Message Pusher API 仅监听 localhost，不对外开放
- 只有服务器内部的其他进程可以访问消息推送功能
- Discord 交互通过端口 8010 的 `/bot` 路径处理，需要签名验证
