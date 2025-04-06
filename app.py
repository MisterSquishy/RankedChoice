import copy
import json
import os
import random
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Set, TypedDict

from dotenv import load_dotenv
from slack_bolt import App, Say
from slack_sdk import WebClient

from blocks import (create_home_view, create_ranked_choice_ballot,
                    create_ranked_choice_prompt, create_submitted_message)
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
def message_hello(message: Dict[str, str], say: Say) -> None:
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
    all_elections = db.get_all_active_elections()
    
    for channel_id, session in all_elections.items():
        if session["is_active"]:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            active_votes.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_ts": session["message_ts"],
                "title": session["title"]
            })
    
    # Get all submitted ballots from the database
    all_ballots = db.get_all_ballots()
    
    # Update the home tab
    client.views_publish(
        user_id=user_id,
        view=create_home_view(active_votes, all_ballots)
    )

# Handle channel selection
@app.action("channel_select")
def handle_channel_select(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_channel_select: User {body['user']['id']} selected channel")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["selected_channel"]
    
    # Get all active sessions from the database
    all_elections = db.get_all_active_elections()
    
    # Get all submitted ballots from the database
    all_ballots = db.get_all_ballots()
    
    # Update the home view
    client.views_update(
        view_id=body["view"]["id"],
        view=create_home_view(all_elections, all_ballots)
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
    channel_id = None
    for block_id, block_data in body["view"]["state"]["values"].items():
        if "channel_select" in block_data:
            channel_id = block_data["channel_select"]["selected_channel"]
            break
    
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
    
    # Find the poll description field
    poll_description = ""
    for block_id, block_data in view_state.items():
        if "poll_description" in block_data:
            poll_description = block_data["poll_description"]["value"]
            break
    
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
    active_election = db.get_active_election(channel_id)
    if active_election and active_election["is_active"]:
        print(f"[DEBUG] handle_start_voting: Active session already exists in channel {channel_id}")
        ack({
            "response_type": "ephemeral",
            "text": "There is already an active voting session in this channel."
        })
        return
    
    # Acknowledge the action
    ack()
    
    # Send the ranked choice voting prompt
    resp = client.users_info(user=body["user"]["id"])
    response = client.chat_postMessage(
        channel=channel_id,
        blocks=create_ranked_choice_prompt(resp["user"]["name"], poll_title, poll_description)
    )
    
    # Store the message timestamp and mark session as active
    message_ts = response["ts"]
    session = {
        "is_active": True,
        "message_ts": message_ts,
        "title": poll_title,
        "options": options
    }
    db.set_active_election(channel_id, session)
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
    active_election = db.get_active_election(channel_id)
    if not active_election or not active_election["is_active"]:
        print(f"[DEBUG] handle_stop_voting: No active session in channel {channel_id}")
        return
    
    # Get the message timestamp and session info
    message_ts = active_election["message_ts"]
    title = active_election["title"]
    options = active_election["options"]
    
    # Get all submitted ballots for this session
    session_ballots = db.get_ballots(message_ts)
    print(f"[DEBUG] handle_stop_voting: Found {len(session_ballots)} submitted ballots for session {message_ts}")

    if len(session_ballots) == 0:
        print(f"[DEBUG] handle_stop_voting: No ballots, returning")
        return
    
    # Calculate and display results
    [result, rounds] = calculate_irv_winner(session_ballots)
    
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in options}
    
    # Post final results
    resp = client.chat_postMessage(
        channel=channel_id,
        text=f"*{title} · final result:*\n🏆 {option_map[result]} 🏆"
    )

    # Raw results
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=resp.data.get("ts", None),
        text="Anonymized results:\n"+"\n".join([f"Voter {i+1}: " + ", ".join([option_map.get(option_id, option_id) for option_id in rankings]) for i, rankings in enumerate(sorted(session_ballots.values(), key=lambda x: random.random()))])
    )

    # Raw rounds
    print(f"[DEBUG] handle_stop_voting: Raw rounds: {rounds}")
    if len(rounds) > 0:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=resp.data.get("ts", None),
            text="\n".join([f"After round {i+1}: " + "\n".join([", ".join([option_map.get(option_id, option_id) for option_id in ballot]) for ballot in round_ballots]) for i, round_ballots in enumerate(rounds)])
        )
    
    # Mark session as inactive
    active_election["is_active"] = False
    db.set_active_election(channel_id, active_election)
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
    active_election = db.get_active_election(channel_id)
    if not active_election or not active_election["is_active"]:
        print(f"[DEBUG] handle_show_results: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp
    message_ts = active_election["message_ts"]
    
    # Get all submitted ballots for this session
    session_ballots = db.get_ballots(message_ts)
    print(f"[DEBUG] handle_show_results: Found {len(session_ballots)} submitted ballots for session {message_ts}")

    if len(session_ballots) == 0:
        print(f"[DEBUG] handle_show_results: No ballots, returning")
        return
    
    # Calculate and display results
    [result, rounds] = calculate_irv_winner(session_ballots)
    
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in active_election["options"]}
    
    resp = client.chat_postMessage(
        channel=channel_id,
        text=f"*{active_election['title']}* · current leader:\n{option_map[result]}"
    )

    # Raw results
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=resp.data.get("ts", None),
        text="Anonymized results:\n"+"\n".join([f"Voter {i+1}: " + ", ".join([option_map.get(option_id, option_id) for option_id in rankings]) for i, rankings in enumerate(sorted(session_ballots.values(), key=lambda x: random.random()))])
    )

    # Raw rounds
    if len(rounds) > 0:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=resp.data.get("ts", None),
            text="\n".join([f"After round {i+1}: " + "\n".join([", ".join([option_map.get(option_id, option_id) for option_id in ballot]) for ballot in round_ballots]) for i, round_ballots in enumerate(rounds)])
        )

# Handle show results button click
@app.action("bump")
def handle_bump(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_bump: User {body['user']['id']} clicked bump")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    active_election = db.get_active_election(channel_id)
    if not active_election or not active_election["is_active"]:
        print(f"[DEBUG] handle_bump: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Get the message timestamp
    message_ts = active_election["message_ts"]
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        reply_broadcast=True,
        text="Don't forget to vote!"
    )
    print(f"[DEBUG] handle_bump: Sent bump message for session {message_ts} in channel {channel_id}")

# Handle show results button click
@app.action("cancel")
def handle_cancel(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_cancel: User {body['user']['id']} clicked cancel")
    ack()
    
    # Get the selected channel
    channel_id = body["actions"][0]["value"]
    
    # Check if there's an active session in this channel
    active_election = db.get_active_election(channel_id)
    if not active_election or not active_election["is_active"]:
        print(f"[DEBUG] handle_cancel: No active session in channel {channel_id}")
        client.chat_postMessage(
            channel=channel_id,
            text="There is no active voting session in this channel."
        )
        return
    
    # Mark session as inactive
    active_election["is_active"] = False
    db.set_active_election(channel_id, active_election)
    
    # Get the message timestamp
    message_ts = active_election["message_ts"]
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        reply_broadcast=True,
        text=f"<@{body['user']['id']}> cancelled the election"
    )
    print(f"[DEBUG] handle_cancel: Sent bump message for session {message_ts} in channel {channel_id}")
    
    update_all_home_tabs(client)

# Handle option selection
@app.action("select_option")
def handle_option_selection(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_option_selection: User {body['user']['id']} selected option")
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["view"]["private_metadata"]
    vote = db.get_vote(message_ts)
    channel_id = vote["channel_id"]
    selected_option_id = body["actions"][0]["value"]
    
    # Check if the ballot is already submitted
    if db.is_ballot_submitted(message_ts, user_id):
        print(f"[DEBUG] handle_option_selection: User {user_id} tried to modify a submitted ballot")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            thread_ts=message_ts,
            text=f"<@{user_id}> Your ballot has already been submitted. You cannot modify it."
        )
        return
    
    # Get current ballot for this user
    current_rankings = db.get_user_ballot(message_ts, user_id) or []
    
    # Check if option is already ranked
    if selected_option_id in current_rankings:
        print(f"[DEBUG] handle_option_selection: Option {selected_option_id} already ranked by user {user_id}")
        return
    
    # Add the option to rankings
    current_rankings.append(selected_option_id)
    db.set_ballot(message_ts, user_id, current_rankings, is_submitted=False)
    print(f"[DEBUG] handle_option_selection: Added option {selected_option_id} to ballot for user {user_id}")
    
    # Get the options for this session
    active_election = db.get_active_election(channel_id)
    options = active_election["options"]
    title = active_election["title"]
    
    # Update the message
    client.views_update(
        view_id=body["view"]["id"],
        view=create_ranked_choice_ballot(
            title,
            options,
            message_ts,
            current_rankings
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
    
    # Check if the ballot is already submitted
    if db.is_ballot_submitted(message_ts, user_id):
        print(f"[DEBUG] handle_submit_rankings: User {user_id} tried to submit an already submitted ballot")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            thread_ts=message_ts,
            text=f"<@{user_id}> You have already submitted your ballot."
        )
        return
    
    # Get current ballot for this user
    current_rankings = db.get_user_ballot(message_ts, user_id) or []
    
    # Get the options for this session
    active_election = db.get_active_election(channel_id)
    options = active_election["options"]
    
    # Mark the ballot as submitted
    db.submit_ballot(message_ts, user_id)
    print(f"[DEBUG] handle_submit_rankings: User {user_id} successfully submitted ballot")
    
    # Send confirmation message
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        blocks=create_submitted_message(user_id)
    )

# Handle clear rankings button click
@app.action("clear_ballot")
def handle_clear_rankings(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    print(f"[DEBUG] handle_clear_rankings: User {body['user']['id']} cleared rankings")
    ack()
    
    # Extract information from the action
    user_id = body["user"]["id"]
    message_ts = body["view"]["private_metadata"]
    vote = db.get_vote(message_ts)
    channel_id = vote["channel_id"]
    
    # Check if the ballot is already submitted
    if db.is_ballot_submitted(message_ts, user_id):
        print(f"[DEBUG] handle_clear_rankings: User {user_id} tried to clear a submitted ballot")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=f"<@{user_id}> Your ballot has already been submitted. You cannot clear it."
        )
        return
    
    # Clear ballot for this user
    db.clear_ballot(message_ts, user_id)
    print(f"[DEBUG] handle_clear_rankings: Cleared ballot for user {user_id} in session {message_ts}")
    
    # Get the options for this session
    active_election = db.get_active_election(channel_id)
    options = active_election["options"]
    title = active_election["title"]
    
    # Update the message
    client.views_update(
        view_id=body["view"]["id"],
        view=create_ranked_choice_ballot(
            title,
            options,
            message_ts,
            []
        )
    )

def calculate_irv_winner(rankings: Dict[str, List[str]]) -> tuple[str, List[List[List[str]]]]:
    """
    Calculates the winner using Instant Runoff Voting (IRV).
    
    Args:
        rankings: Dictionary of user rankings (option IDs in preference order)
    
    Returns:
        tuple[str | None, List[List[List[str]]]]: A tuple containing:
            - The winning option_id or None if no winner
            - List of rounds showing ballot state after each elimination
    """
    print(f"[DEBUG] calculate_irv_winner: Calculating winner from {len(rankings)} ballots")
    ballots = copy.deepcopy(list(rankings.values()))
    rounds = []

    if len(ballots) == 0:
        print(f"[DEBUG] calculate_irv_winner: No ballots, returning None")
        return None, rounds

    while True:
        all_candidates: Set[str] = set()
        for row in ballots:
            for vote in row:
                all_candidates.add(vote)
                
        # Count first-choice votes
        counts = Counter({candidate: 0 for candidate in all_candidates})
        for ballot in ballots:
            if ballot:
                counts[ballot[0]] += 1

        total_votes = sum(counts.values())
        if not total_votes:
            print(f"[DEBUG] calculate_irv_winner: No votes left, returning random winnder")
            original_ballots = copy.deepcopy(list(rankings.values()))
            result = random.choice(list({ballot[0] for ballot in original_ballots}))
            print(f"[DEBUG] handle_stop_voting: Randomly selected {result} as winner")
            return result, rounds

        # Check for majority
        for candidate, count in counts.items():
            if count > total_votes / 2:
                print(f"[DEBUG] calculate_irv_winner: Found majority winner: {candidate}")
                return candidate, rounds

        # Find the candidate(s) with the fewest votes
        min_count = min(counts.values())
        to_eliminate = {c for c, count in counts.items() if count == min_count}
        print(f"[DEBUG] calculate_irv_winner: Eliminating candidates with {min_count} votes: {to_eliminate}")

        # Eliminate candidate(s) from all ballots
        for ballot in ballots:
            ballot[:] = [c for c in ballot if c not in to_eliminate]

        shuffled_ballots = copy.deepcopy(ballots)
        random.shuffle(shuffled_ballots)
        rounds.append(shuffled_ballots)
        if len(rounds) > 1000:
            raise Exception("IRV has entered an infinite loop")

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
    all_elections = db.get_all_active_elections()
    
    # Get all submitted ballots from the database
    all_ballots = db.get_all_ballots()
    
    # Get active voting sessions
    active_votes = []
    for channel_id, session in all_elections.items():
        if session["is_active"]:
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]
            active_votes.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_ts": session["message_ts"],
                "title": session["title"]
            })
    
    # Update each user's home tab
    for user in users["members"]:
        if not user["is_bot"] and not user["deleted"]:
            client.views_publish(
                user_id=user["id"],
                view=create_home_view(active_votes, all_ballots)
            )
    print(f"[DEBUG] update_all_home_tabs: Updated home tabs for {len(users['members'])} users")

@app.action("request_ballot")
def handle_request_ballot(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    """Handle requesting a ballot."""
    ack()
    
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["container"]["channel_id"]
    
    # Get the vote details
    vote = db.get_vote(message_ts)
    if not vote:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="This vote is no longer active."
        )
        return
    
    # Check if user already has a ballot
    ballot = db.get_ballot(message_ts, user_id)
    if ballot and ballot.get("is_submitted", False):
        # Create rankings text
        rankings_text = "No rankings"
        if ballot["rankings"]:
            rankings_lines = []
            for i, option_id in enumerate(ballot["rankings"]):
                option_text = next(opt["text"] for opt in vote["options"] if opt["id"] == option_id)
                rankings_lines.append(f"{i+1}. {option_text}")
            rankings_text = "\n".join(rankings_lines)
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"You have already submitted your ballot for this vote:\n{rankings_text}"
        )
        return
        
    # Open the ballot modal
    client.views_open(
        trigger_id=body["trigger_id"],
        view=create_ranked_choice_ballot(vote["title"], vote["options"], message_ts, ballot["rankings"] if ballot else None)
    )

@app.view("ballot_modal")
def handle_ballot_submission(ack: SlackAck, body: SlackBody, client: WebClient) -> None:
    """Handle the submission of a ballot from the modal."""
    ack()
    
    user_id = body["user"]["id"]
    message_ts = body["view"]["private_metadata"]
    vote = db.get_vote(message_ts)
    channel_id = vote["channel_id"]
    
    # Get the vote details
    vote = db.get_vote(message_ts)
    if not vote:
        return
    
    # Check if user already has a ballot
    ballot = db.get_ballot(message_ts, user_id)
    if ballot and ballot.get("is_submitted", False):
        # Create rankings text
        rankings_text = "No rankings"
        if ballot["rankings"]:
            rankings_lines = []
            for i, option_id in enumerate(ballot["rankings"]):
                option_text = next(opt["text"] for opt in vote["options"] if opt["id"] == option_id)
                rankings_lines.append(f"{i+1}. {option_text}")
            rankings_text = "\n".join(rankings_lines)
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"You have already submitted your ballot for this vote.\n{rankings_text}"
        )
        return
    
    # Mark the ballot as submitted
    db.submit_ballot(message_ts, user_id)
    
    # Send a confirmation message
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=f"<@{user_id}> voted! Thank you for doing your civic duty 🫡"
    )

# Start the app
if __name__ == "__main__":
    app.start(port=3000) 