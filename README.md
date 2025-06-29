# Cecilia

![#c](pics/bot.jpg)

A discord bot deployable on server!

Invitation Link: https://discord.com/oauth2/authorize?client_id=1388147931659501658

## Structure

The bot listens on port 8010. The message pusher listens on port 8011. The file with the same name as the dir it's in is this dir's "main" module. (e.g. the "main" module of bot/ dir is bot.py)

- `bot`: the frontend for handling discord bot integration
- `apps`: the backend for the bot's functionalities
  - `msg_pusher`: listen to port 8011 for any msgs and push them to the discord user
  - `essay_summarizer`: summarize the essays on ArXiv about a specific topic using AI, and push the results to you regularly

## Message Pusher API

The message pusher accepts HTTP POST requests to `http://localhost:8011/push` with JSON payloads.

### JSON Schema

```json
{
  "user_id": "123456789012345678",
  "message": {
    "content": "Your message content here",
    "embed": {
      "title": "Optional Embed Title",
      "description": "Optional embed description", 
      "color": "#FF5733",
      "fields": [
        {
          "name": "Field Name",
          "value": "Field Value",
          "inline": true
        }
      ],
      "footer": {
        "text": "Footer text"
      }
    },
    "components": [
      {
        "type": "button",
        "label": "Click Me",
        "url": "https://example.com"
      }
    ]
  },
  "channel_id": "987654321098765432",
  "priority": "normal",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### API Endpoints

- `GET /health` - Health check
- `GET /schema` - Get the JSON schema
- `POST /push` - Send a message to Discord

### Example Usage

```bash
curl -X POST http://localhost:8011/push \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1131817164060495914",
    "channel_id": "1190649951693316169",
    "message": {
      "content": "Hello from external service!"
    }
  }'
```

## Deploy

1. Fill `bot/auths-sample.py` with your discord bot credentials and rename it to `auths.py`.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python main.py`
