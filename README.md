# Cecilia

![#c](pics/bot.jpg)

A discord bot deployable on server!

Invitation Link: https://discord.com/oauth2/authorize?client_id=1388147931659501658

## Structure

The bot listens on port 8010. The file with the same name as the dir it's in is this dir's "main" module. (e.g. the "main" module of bot/ dir is bot.py)

- `bot`: the frontend for handling discord bot integration
- `apps`: theobackend for the bot's functionalities
  - `msg_pusher`: listen to port 8011 for any msgs and push them to the discord user
  - `essay_summarizer`: summarize the essays on ArXiv about a specific topic using AI, and push the results to you regularly

## Deploy

1. Fill `bot/auths-sample.py` with your discord bot credentials and rename it to `auths.py`.
