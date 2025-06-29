# Cecilia

A discord bot deployable on server!

## Structure

The bot listens on port 8010.

- `bot`: the frontend for handling discord bot integration
- `apps`: the backend for the bot's functionalities
  - `essay_summarizer`: summarize the essays on ArXiv about a specific topic using AI, and push the results to you regularly

## Deploy

1. Fill `bot/auths-sample.py` with your discord bot credentials and rename it to `auths.py`.
