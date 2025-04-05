import os
from collections import defaultdict
from typing import Any, Dict, List

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.context import BoltContext
from slack_bolt.context.say import Say

from blocks import create_ranked_choice_prompt, update_rankings_message

# Load environment variables
load_dotenv()

# Initialize the Slack app
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Sample voting options (in a real app, these would come from a database or user input)
VOTING_OPTIONS: List[str] = [
    "Pizza Party 🍕",
    "Movie Night 🎬",
    "Game Night 🎮",
    "Team Building Workshop 🏢",
    "Outdoor Adventure 🌲"
]

# Store user rankings (in a real app, this would be in a database)
# Format: {message_ts: {user_id: [rankings]}}
user_rankings: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

# Message listener that responds to "hello"
@app.message("hello")
def message_hello(message: Dict[str, Any], context: BoltContext, say: Say) -> None:
    say(f"Hey there <@{message['user']}>! 👋")

# Command to start ranked choice voting
@app.command("/ranked-vote")
def handle_ranked_vote(ack: Any, body: Dict[str, Any], say: Say) -> None:
    # Acknowledge the command request
    ack()
    
    # Send the ranked choice voting prompt
    response = say(blocks=create_ranked_choice_prompt(VOTING_OPTIONS))
    # Store the message timestamp for later updates
    message_ts = response["ts"]
    # Initialize empty rankings for this message
    user_rankings[message_ts] = defaultdict(list)

# Handle option selection
@app.action("select_option_")
def handle_option_selection(ack: Any, body: Dict[str, Any], client: Any) -> None:
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    selected_option = body["actions"][0]["value"]
    
    # Get current rankings for this user
    current_rankings = user_rankings[message_ts][user_id]
    
    # Check if option is already ranked
    if selected_option in current_rankings:
        return
    
    # Add the option to rankings
    current_rankings.append(selected_option)
    
    # Update the message
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=update_rankings_message(
            create_ranked_choice_prompt(VOTING_OPTIONS),
            current_rankings
        )
    )

# Handle ranking submission
@app.action("submit_rankings")
def handle_submit_rankings(ack: Any, body: Dict[str, Any], client: Any) -> None:
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Get current rankings
    current_rankings = user_rankings[message_ts][user_id]
    
    if not current_rankings:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> Please rank at least one option before submitting."
        )
        return
    
    # In a real app, you would save these rankings to a database
    client.chat_postMessage(
        channel=channel_id,
        text=f"<@{user_id}> has submitted their rankings:\n" + 
             "\n".join(f"{idx + 1}. {option}" for idx, option in enumerate(current_rankings))
    )

# Handle clearing rankings
@app.action("clear_rankings")
def handle_clear_rankings(ack: Any, body: Dict[str, Any], client: Any) -> None:
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Clear rankings for this user
    user_rankings[message_ts][user_id] = []
    
    # Update the message
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=update_rankings_message(
            create_ranked_choice_prompt(VOTING_OPTIONS),
            []
        )
    )

# Start the app
if __name__ == "__main__":
    handler: SocketModeHandler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start() 