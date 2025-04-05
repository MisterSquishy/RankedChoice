# Slack Ranked Choice Voting App

A Slack app that enables ranked choice voting in your workspace. The app provides a home tab interface for managing voting sessions and displaying results.

## Features

- Start and stop voting sessions in any channel
- Rank options by clicking them in order
- Submit and clear rankings
- View voting results
- Home tab interface for managing voting sessions

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
   - `users:read`
   - `channels:read`
   - `channels:join`
4. Enable the Home Tab feature in your app settings
5. Install the app to your workspace
6. Copy the Bot User OAuth Token and App-Level Token
7. Copy `.env.example` to `.env` and fill in your tokens:
   ```
   cp .env.example .env
   ```
8. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the App

Run the app with:

```
python app.py
```

The app will start in Socket Mode and you can access the home tab by clicking on the app in your Slack workspace.

## Usage

1. Click on the app in your Slack workspace to open the home tab
2. Select a channel and click "Start Voting" to begin a voting session
3. In the channel, users can click options to rank them
4. Users can submit their rankings or clear them to start over
5. Use the home tab to stop voting or view results
