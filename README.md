# Slack Bolt App

A simple Slack bot built with the Bolt framework for Python.

## Setup

1. Create a new Slack app at https://api.slack.com/apps
2. Enable Socket Mode in your Slack app settings
3. Add the following bot token scopes:
   - `chat:write`
   - `app_mentions:read`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
4. Install the app to your workspace
5. Copy the Bot User OAuth Token and App-Level Token
6. Copy `.env.example` to `.env` and fill in your tokens:
   ```
   cp .env.example .env
   ```
7. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the App

Run the app with:

```
python app.py
```

The bot will respond to messages containing "hello" with a greeting.
