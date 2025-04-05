import os
import uuid
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, TypedDict, Union

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse

from blocks import (create_home_view, create_ranked_choice_prompt,
                    create_submitted_message, update_rankings_message)

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

class VotingOption(TypedDict):
    id: str
    text: str

class PollSession(TypedDict):
    is_active: bool
    message_ts: Optional[str]
    title: str
    options: List[VotingOption]

# Initialize the Slack app
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))

# Store user rankings (in a real app, this would be in a database)
# Format: {message_ts: {user_id: [rankings]}}
user_rankings: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

# Store active voting sessions
# Format: {channel_id: {is_active: bool, message_ts: str, title: str, options: List[VotingOption]}}
active_sessions: Dict[str, PollSession] = defaultdict(lambda: {"is_active": False, "message_ts": None, "title": "", "options": []})

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
        view=create_home_view(active_votes, user_rankings)
    )

# Handle channel selection
@app.action("channel_select")
def handle_channel_select(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["selected_channel"]
    
    # Update the home view
    client.views_update(
        view_id=body["view"]["id"],
        view=create_home_view(active_sessions, user_rankings)
    )

# Handle start voting button click
@app.action("start_voting")
def handle_start_voting(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    # Get the selected channel from the view state
    if not body.get("view") or not body["view"].get("state"):
        ack({
            "response_type": "ephemeral",
            "text": "Please select a channel first."
        })
        return
    
    # Get the channel ID
    channel_block_id = next(iter(body["view"]["state"]["values"]))
    channel_id = body["view"]["state"]["values"][channel_block_id]["channel_select"]["selected_channel"]
    
    if not channel_id:
        ack({
            "response_type": "ephemeral",
            "text": "Please select a channel first."
        })
        return
    
    # Get the poll title and options from the view state
    view_state = body["view"]["state"]["values"]
    
    # Find the poll title field
    poll_title = None
    for block_id, block_data in view_state.items():
        if "poll_title" in block_data:
            poll_title = block_data["poll_title"]["value"]
            break
    
    if not poll_title:
        ack({
            "response_type": "ephemeral",
            "text": "Please enter a poll title."
        })
        return
    
    # Find the poll options field
    poll_options_text = None
    for block_id, block_data in view_state.items():
        if "poll_options" in block_data:
            poll_options_text = block_data["poll_options"]["value"]
            break
    
    if not poll_options_text:
        ack({
            "response_type": "ephemeral",
            "text": "Please enter poll options."
        })
        return
    
    # Parse the options (one per line)
    options_text = [opt.strip() for opt in poll_options_text.split("\n") if opt.strip()]
    
    if len(options_text) < 2:
        ack({
            "response_type": "ephemeral",
            "text": "Please enter at least 2 options."
        })
        return
    
    # Create option objects with unique IDs
    options = []
    for text in options_text:
        option_id = str(uuid.uuid4())[:8]  # Generate a short unique ID
        options.append({"id": option_id, "text": text})
    
    # Check if there's already an active session in this channel
    if active_sessions[channel_id]["is_active"]:
        ack({
            "response_type": "ephemeral",
            "text": "There is already an active voting session in this channel."
        })
        return
    
    # Acknowledge the action
    ack()
    
    # Send the ranked choice voting prompt
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=create_ranked_choice_prompt(options, poll_title)
    )
    
    # Store the message timestamp and mark session as active
    message_ts = response["ts"]
    active_sessions[channel_id] = {
        "is_active": True,
        "message_ts": message_ts,
        "title": poll_title,
        "options": options
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
    
    # Get the message timestamp and session info
    message_ts = active_sessions[channel_id]["message_ts"]
    title = active_sessions[channel_id]["title"]
    options = active_sessions[channel_id]["options"]
    
    # Get all rankings for this session
    session_rankings = user_rankings[message_ts]
    
    # Calculate and display results
    result = calculate_irv_winner(session_rankings)
    
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in options}
    
    # Post final results
    resp = client.chat_postMessage(
        channel=channel_id,
        text=f"*{title} - Final result:*\n🏆 {option_map[result]} 🏆"
    )

    # Raw results
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=resp.data.get("ts", None),
        text="Raw results:\n"+"\n".join([", ".join([option_map.get(option_id, option_id) for option_id in rankings]) for rankings in session_rankings.values()])
    )
    
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
    result = calculate_irv_winner(session_rankings)
    
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in active_sessions[channel_id]["options"]}
    
    client.chat_postMessage(
        channel=channel_id,
        text=f"Current leader: *{active_sessions[channel_id]['title']} - Results:*\n{option_map[result]}"
    )

# Handle show results button click
@app.action("bump")
def handle_bump(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
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
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        reply_broadcast=True,
        text="Don't forget to vote!"
    )

# Handle option selection
@app.action("select_option")
def handle_option_selection(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    selected_option_id = body["actions"][0]["value"]
    
    # Get current rankings for this user
    current_rankings = user_rankings[message_ts][user_id]
    
    # Check if option is already ranked
    if selected_option_id in current_rankings:
        return
    
    # Add the option to rankings
    current_rankings.append(selected_option_id)
    
    # Get the options for this session
    options = active_sessions[channel_id]["options"]
    title = active_sessions[channel_id]["title"]
    
    # Update the message
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=update_rankings_message(
            create_ranked_choice_prompt(options, title),
            current_rankings,
            options
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
    
    title = active_sessions[channel_id]["title"]
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=create_submitted_message(title)
    )
    
    # In a real app, you would save these rankings to a database
    client.chat_postMessage(
        channel=channel_id,
        text=f"<@{user_id}> has submitted their rankings!"
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
    
    # Get the options for this session
    options = active_sessions[channel_id]["options"]
    title = active_sessions[channel_id]["title"]
    
    # Update the message
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=update_rankings_message(
            create_ranked_choice_prompt(options, title),
            [],
            options
        )
    )

# Handle clearing rankings
@app.action("delete_lowest_rank")
def handle_delete_lowest_rank(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Clear rankings for this user
    cur_rankings =  user_rankings[message_ts][user_id]
    user_rankings[message_ts][user_id] = cur_rankings[0:-1]
    
    # Get the options for this session
    options = active_sessions[channel_id]["options"]
    title = active_sessions[channel_id]["title"]
    
    # Update the message
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=update_rankings_message(
            create_ranked_choice_prompt(options, title),
            user_rankings[message_ts][user_id],
            options
        )
    )

def calculate_irv_winner(rankings: Dict[str, List[str]]) -> Optional[str]:
    """
    Calculates the winner using Instant Runoff Voting (IRV).
    
    Args:
        rankings: Dictionary of user rankings (option IDs in preference order)
    
    Returns:
        The winning option_id or None if no winner
    """
    ballots = list(rankings.values())

    while True:
        # Count first-choice votes
        counts = Counter()
        for ballot in ballots:
            if ballot:
                counts[ballot[0]] += 1

        total_votes = sum(counts.values())
        if not total_votes:
            return None  # No votes left

        # Check for majority
        for candidate, count in counts.items():
            if count > total_votes / 2:
                return candidate

        # Find the candidate(s) with the fewest votes
        min_count = min(counts.values())
        to_eliminate = {c for c, count in counts.items() if count == min_count}

        # Eliminate candidate(s) from all ballots
        for ballot in ballots:
            ballot[:] = [c for c in ballot if c not in to_eliminate]

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
                view=create_home_view(active_votes, user_rankings)
            )

# Start the app
if __name__ == "__main__":
    app.start(port=3000) 