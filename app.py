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
from database import Database

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
    response_type: str
    text: str

class VotingOption(TypedDict):
    id: str
    text: str

class PollSession(TypedDict):
    is_active: bool
    message_ts: Optional[str]
    title: str
    options: List[VotingOption]

# Initialize the Slack app and database
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))
db = Database()

# Message listener that responds to "hello"
@app.message("hello")
def message_hello(message: Dict[str, str], say: Callable[[str], None]) -> None:
    print(f"[DEBUG] message_hello: User {message['user']} said hello")
    say(f"Hey there <@{message['user']}>! 👋")

# Handle home tab opened event
@app.event("app_home_opened")
def handle_app_home_opened(event: SlackEvent, client: WebClient) -> None:
    print(f"[DEBUG] handle_app_home_opened: User {event['user']} opened home tab")
    # Get the user's active voting sessions
    user_id = event["user"]
    active_votes = []
    
    # Get all active sessions from the database
    all_sessions = db.get_all_active_sessions()
    print(f"[DEBUG] all_sessions: {all_sessions}")
    
    for channel_id, session in all_sessions.items():
        if session["is_active"]:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            active_votes.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_ts": session["message_ts"]
            })
    
    # Get all user rankings from the database
    all_rankings = db.get_all_user_rankings()
    
    # Update the home tab
    client.views_publish(
        user_id=user_id,
        view=create_home_view(active_votes, all_rankings)
    )

# Handle channel selection
@app.action("channel_select")
def handle_channel_select(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_channel_select: User {body['user']['id']} selected channel")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["selected_channel"]
    
    # Get all active sessions from the database
    all_sessions = db.get_all_active_sessions()
    
    # Get all user rankings from the database
    all_rankings = db.get_all_user_rankings()
    
    # Update the home view
    client.views_update(
        view_id=body["view"]["id"],
        view=create_home_view(all_sessions, all_rankings)
    )

# Handle start voting button click
@app.action("start_voting")
def handle_start_voting(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_start_voting: User {body['user']['id']} clicked start voting")
    # Get the selected channel from the view state
    if not body.get("view") or not body["view"].get("state"):
        print(f"[DEBUG] handle_start_voting: No view state found")
        ack({
            "response_type": "ephemeral",
            "text": "Please select a channel first."
        })
        return
    
    # Get the channel ID
    channel_block_id = next(iter(body["view"]["state"]["values"]))
    channel_id = body["view"]["state"]["values"][channel_block_id]["channel_select"]["selected_channel"]
    
    if not channel_id:
        print(f"[DEBUG] handle_start_voting: No channel selected")
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
        print(f"[DEBUG] handle_start_voting: No poll title provided")
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
        print(f"[DEBUG] handle_start_voting: No poll options provided")
        ack({
            "response_type": "ephemeral",
            "text": "Please enter poll options."
        })
        return
    
    # Parse the options (one per line)
    options_text = [opt.strip() for opt in poll_options_text.split("\n") if opt.strip()]
    
    if len(options_text) < 2:
        print(f"[DEBUG] handle_start_voting: Less than 2 options provided")
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
    active_session = db.get_active_session(channel_id)
    if active_session and active_session["is_active"]:
        print(f"[DEBUG] handle_start_voting: Active session already exists in channel {channel_id}")
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
    session = {
        "is_active": True,
        "message_ts": message_ts,
        "title": poll_title,
        "options": options
    }
    db.set_active_session(channel_id, session)
    print(f"[DEBUG] handle_start_voting: Created new session in channel {channel_id} with message_ts {message_ts}")
    
    # Update the home tab for all users
    update_all_home_tabs(client)

# Handle stop voting button click
@app.action("stop_voting")
def handle_stop_voting(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_stop_voting: User {body['user']['id']} clicked stop voting")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    active_session = db.get_active_session(channel_id)
    if not active_session or not active_session["is_active"]:
        print(f"[DEBUG] handle_stop_voting: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp and session info
    message_ts = active_session["message_ts"]
    title = active_session["title"]
    options = active_session["options"]
    
    # Get all rankings for this session
    session_rankings = db.get_user_rankings(message_ts)
    print(f"[DEBUG] handle_stop_voting: Found {len(session_rankings)} user rankings for session {message_ts}")
    
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
    active_session["is_active"] = False
    db.set_active_session(channel_id, active_session)
    print(f"[DEBUG] handle_stop_voting: Marked session in channel {channel_id} as inactive")
    
    # Update the home tab for all users
    update_all_home_tabs(client)

# Handle show results button click
@app.action("show_results")
def handle_show_results(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_show_results: User {body['user']['id']} clicked show results")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    active_session = db.get_active_session(channel_id)
    if not active_session or not active_session["is_active"]:
        print(f"[DEBUG] handle_show_results: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp
    message_ts = active_session["message_ts"]
    
    # Get all rankings for this session
    session_rankings = db.get_user_rankings(message_ts)
    print(f"[DEBUG] handle_show_results: Found {len(session_rankings)} user rankings for session {message_ts}")
    
    # Calculate and display results
    result = calculate_irv_winner(session_rankings)
    
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in active_session["options"]}
    
    client.chat_postMessage(
        channel=channel_id,
        text=f"Current leader: *{active_session['title']} - Results:*\n{option_map[result]}"
    )

# Handle show results button click
@app.action("bump")
def handle_bump(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_bump: User {body['user']['id']} clicked bump")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    active_session = db.get_active_session(channel_id)
    if not active_session or not active_session["is_active"]:
        print(f"[DEBUG] handle_bump: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp
    message_ts = active_session["message_ts"]
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        reply_broadcast=True,
        text="Don't forget to vote!"
    )
    print(f"[DEBUG] handle_bump: Sent bump message for session {message_ts} in channel {channel_id}")

# Handle option selection
@app.action("select_option")
def handle_option_selection(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_option_selection: User {body['user']['id']} selected option")
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    selected_option_id = body["actions"][0]["value"]
    
    # Get current rankings for this user
    session_rankings = db.get_user_rankings(message_ts)
    current_rankings = session_rankings.get(user_id, [])
    
    # Check if option is already ranked
    if selected_option_id in current_rankings:
        print(f"[DEBUG] handle_option_selection: Option {selected_option_id} already ranked by user {user_id}")
        return
    
    # Add the option to rankings
    current_rankings.append(selected_option_id)
    db.set_user_rankings(message_ts, user_id, current_rankings)
    print(f"[DEBUG] handle_option_selection: Added option {selected_option_id} to rankings for user {user_id}")
    
    # Get the options for this session
    active_session = db.get_active_session(channel_id)
    options = active_session["options"]
    title = active_session["title"]
    
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
    print(f"[DEBUG] handle_submit_rankings: User {body['user']['id']} submitted rankings")
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Get current rankings for this user
    session_rankings = db.get_user_rankings(message_ts)
    current_rankings = session_rankings.get(user_id, [])
    
    # Get the options for this session
    active_session = db.get_active_session(channel_id)
    options = active_session["options"]
    
    # Send confirmation message
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        blocks=create_submitted_message(user_id)
    )
    print(f"[DEBUG] handle_submit_rankings: User {user_id} successfully submitted rankings")

# Handle clear rankings button click
@app.action("clear_rankings")
def handle_clear_rankings(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_clear_rankings: User {body['user']['id']} cleared rankings")
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Clear rankings for this user
    db.clear_user_rankings(message_ts, user_id)
    print(f"[DEBUG] handle_clear_rankings: Cleared rankings for user {user_id} in session {message_ts}")
    
    # Get the options for this session
    active_session = db.get_active_session(channel_id)
    options = active_session["options"]
    title = active_session["title"]
    
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

def calculate_irv_winner(rankings: Dict[str, List[str]]) -> Optional[str]:
    """
    Calculates the winner using Instant Runoff Voting (IRV).
    
    Args:
        rankings: Dictionary of user rankings (option IDs in preference order)
    
    Returns:
        The winning option_id or None if no winner
    """
    print(f"[DEBUG] calculate_irv_winner: Calculating winner from {len(rankings)} ballots")
    ballots = list(rankings.values())

    while True:
        # Count first-choice votes
        counts = Counter()
        for ballot in ballots:
            if ballot:
                counts[ballot[0]] += 1

        total_votes = sum(counts.values())
        if not total_votes:
            print(f"[DEBUG] calculate_irv_winner: No votes left, returning None")
            return None  # No votes left

        # Check for majority
        for candidate, count in counts.items():
            if count > total_votes / 2:
                print(f"[DEBUG] calculate_irv_winner: Found majority winner: {candidate}")
                return candidate

        # Find the candidate(s) with the fewest votes
        min_count = min(counts.values())
        to_eliminate = {c for c, count in counts.items() if count == min_count}
        print(f"[DEBUG] calculate_irv_winner: Eliminating candidates: {to_eliminate}")

        # Eliminate candidate(s) from all ballots
        for ballot in ballots:
            ballot[:] = [c for c in ballot if c not in to_eliminate]

def update_all_home_tabs(client: WebClient) -> None:
    """
    Update the home tab for all users in the workspace.
    
    Args:
        client: Slack client
    """
    print(f"[DEBUG] update_all_home_tabs: Updating home tabs for all users")
    # Get all users in the workspace
    users = client.users_list()
    
    # Get active voting sessions from the database
    all_sessions = db.get_all_active_sessions()
    
    # Get all user rankings from the database
    all_rankings = db.get_all_user_rankings()
    
    # Get active voting sessions
    active_votes = []
    for channel_id, session in all_sessions.items():
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
                view=create_home_view(active_votes, all_rankings)
            )
    print(f"[DEBUG] update_all_home_tabs: Updated home tabs for {len(users['members'])} users")

# Start the app
if __name__ == "__main__":
    app.start(port=3000) 