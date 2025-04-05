import os
from collections import defaultdict
from typing import Callable, Dict, List, Optional, TypedDict, Union

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse

from blocks import (create_home_view, create_ranked_choice_prompt,
                    update_rankings_message)

# Load environment variables
load_dotenv()

# Define type hints for Slack payloads
class SlackUser(TypedDict):
    id: str

class SlackAction(TypedDict):
    action_id: str
    value: str

class SlackView(TypedDict):
    id: str
    state: Dict[str, Dict[str, Dict[str, str]]]

class SlackBody(TypedDict):
    user: SlackUser
    actions: List[SlackAction]
    view: Optional[SlackView]
    container: Optional[Dict[str, str]]

class SlackEvent(TypedDict):
    user: str

class SlackAck(TypedDict):
    __call__: Callable[[], None]

# Initialize the Slack app
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))

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

# Store active voting sessions
# Format: {channel_id: {is_active: bool, message_ts: str}}
active_sessions: Dict[str, Dict[str, Union[bool, str]]] = defaultdict(lambda: {"is_active": False, "message_ts": None})

# Message listener that responds to "hello"
@app.message("hello")
def message_hello(message: Dict[str, str], say: Callable[[str], None]) -> None:
    say(f"Hey there <@{message['user']}>! 👋")

# Handle home tab opened event
@app.event("app_home_opened")
def handle_app_home_opened(event: SlackEvent, client: WebClient) -> None:
    # Get the user's active voting sessions
    user_id = event["user"]
    active_votes = []
    
    for channel_id, session in active_sessions.items():
        if session["is_active"]:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            active_votes.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_ts": session["message_ts"]
            })
    
    # Update the home tab
    client.views_publish(
        user_id=user_id,
        view=create_home_view(active_votes)
    )

# Handle start voting button click
@app.action("start_voting")
def handle_start_voting(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Get the selected channel from the view state
    if not body.get("view") or not body["view"].get("state"):
        return
    
    # Get the first block ID and its channel_select value
    block_id = next(iter(body["view"]["state"]["values"]))
    channel_id = body["view"]["state"]["values"][block_id]["channel_select"]["selected_channel"]
    
    # Check if there's already an active session in this channel
    if active_sessions[channel_id]["is_active"]:
        client.chat_postMessage(
            channel=channel_id,
            text="There is already an active voting session in this channel."
        )
        return
    
    # Send the ranked choice voting prompt
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=create_ranked_choice_prompt(VOTING_OPTIONS)
    )
    
    # Store the message timestamp and mark session as active
    message_ts = response["ts"]
    active_sessions[channel_id] = {
        "is_active": True,
        "message_ts": message_ts
    }
    
    # Initialize empty rankings for this message
    user_rankings[message_ts] = defaultdict(list)
    
    # Update the home tab for all users
    update_all_home_tabs(client)

# Handle stop voting button click
@app.action("stop_voting")
def handle_stop_voting(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    if not active_sessions[channel_id]["is_active"]:
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Mark session as inactive
    active_sessions[channel_id]["is_active"] = False
    
    # Update the home tab for all users
    update_all_home_tabs(client)

# Handle show results button click
@app.action("show_results")
def handle_show_results(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    if not active_sessions[channel_id]["is_active"]:
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp
    message_ts = active_sessions[channel_id]["message_ts"]
    
    # Get all rankings for this session
    session_rankings = user_rankings[message_ts]
    
    # Calculate and display results
    # (This is a simple implementation - in a real app, you'd want more sophisticated ranking algorithms)
    results = calculate_results(session_rankings)
    
    client.chat_postMessage(
        channel=channel_id,
        text=f"*Voting Results:*\n" + "\n".join(f"{idx + 1}. {option} - {count} votes" for idx, (option, count) in enumerate(results))
    )

# Handle option selection
@app.action("select_option_")
def handle_option_selection(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
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
def handle_submit_rankings(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
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
def handle_clear_rankings(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
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

def calculate_results(rankings: Dict[str, List[str]]) -> List[tuple]:
    """
    Calculate the results of a voting session.
    
    Args:
        rankings: Dictionary of user rankings
        
    Returns:
        List of tuples (option, count) sorted by count
    """
    # Count first-choice votes
    first_choice_counts = defaultdict(int)
    for user_rankings in rankings.values():
        if user_rankings:
            first_choice_counts[user_rankings[0]] += 1
    
    # Sort by count
    return sorted(first_choice_counts.items(), key=lambda x: x[1], reverse=True)

def update_all_home_tabs(client: WebClient) -> None:
    """
    Update the home tab for all users in the workspace.
    
    Args:
        client: Slack client
    """
    # Get all users in the workspace
    users = client.users_list()
    
    # Get active voting sessions
    active_votes = []
    for channel_id, session in active_sessions.items():
        if session["is_active"]:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            active_votes.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_ts": session["message_ts"]
            })
    
    # Update each user's home tab
    for user in users["members"]:
        if not user["is_bot"] and not user["deleted"]:
            client.views_publish(
                user_id=user["id"],
                view=create_home_view(active_votes)
            )

# Start the app
if __name__ == "__main__":
    app.start(port=3000) 