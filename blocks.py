from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from slack_sdk.models.blocks import (ActionsBlock, Block, ButtonElement,
                                     ChannelSelectElement, ContextBlock,
                                     DividerBlock, HeaderBlock, InputBlock,
                                     PlainTextInputElement, PlainTextObject,
                                     SectionBlock)
from slack_sdk.models.views import View


class VotingOption(TypedDict):
    id: str
    text: str

def create_ranked_choice_prompt(user_display_name: str, title: str, description: str = "A ranked choice vote") -> List[Block]:
    """
    Creates a Slack blocks message for ranked choice voting with interactive buttons.
    
    Args:
        user_id: User ID of the person who started the vote
        title: Title of the poll
        description: Description of the poll
    Returns:
        List of Slack blocks
    """
    return [
        HeaderBlock(text=f"🗳️ {title}"),
        SectionBlock(text=description),
        ActionsBlock(elements=[
            ButtonElement(text="Request a ballot", style="primary", action_id="request_ballot")
        ]),
        ContextBlock(elements=[
            PlainTextObject(text=f"Created by @{user_display_name}")
        ])
    ]

def create_submitted_message(user_id: str) -> List[Block]:
    return [
        SectionBlock(text=f"<@{user_id}> voted! Thank you for doing your civic duty 🫡")
    ]

# todo this signature is emblematic of a deep evil
def create_home_view(active_votes: List[Dict[str, str]], all_ballots: Dict[str, Dict[str, List[str]]], active_vote_errors: Dict[str, str] = {}, new_vote_error: Optional[str] = None) -> View:
    """
    Create the home tab view.
    
    Args:
        active_votes: List of active voting sessions
        all_ballots: Dictionary of all submitted ballots by message timestamp
    
    Returns:
        The home tab view blocks
    """
    blocks = []

    # Active elections section
    blocks.extend([
        HeaderBlock(text="Active polls"),
    ])
    
    if not active_votes:
        blocks.append(SectionBlock(text="No active polls."))
    else:
        for vote in active_votes:
            channel_id = vote["channel_id"]
            channel_name = vote["channel_name"]
            message_ts = vote["message_ts"]
            title = vote["title"]
            
            # Count submitted ballots for this session
            session_ballots = all_ballots.get(message_ts, {})
            submitted_count = sum(1 for ballot in session_ballots.values() if ballot)
            noun = 'ballot' if submitted_count == 1 else 'ballots'
            
            blocks.extend([
                SectionBlock(text=f"*#{channel_name}*: {title}\n{submitted_count} {noun} submitted"),        
                ActionsBlock(elements=[
                    ButtonElement(text="Close", style="danger", action_id="stop_voting", value=channel_id),
                    ButtonElement(text="Post results", action_id="show_results", value=channel_id),
                    ButtonElement(text="Bump", action_id="bump", value=channel_id),
                    ButtonElement(text="Cancel", action_id="cancel", value=channel_id),
                ])
            ])

            if active_vote_errors.get(message_ts):
                blocks.append(SectionBlock(text=f"⚠️ {active_vote_errors[message_ts]}"))
    
    # Start a new poll section
    blocks.extend([
        DividerBlock(),
        HeaderBlock(text="Start a new poll"),
        InputBlock(
            label="Poll title",
            action_id="poll_title",
            element=PlainTextInputElement(
                placeholder="Enter poll title",
                action_id="poll_title"
            )
        ),
        InputBlock(
            label="Poll description",
            action_id="poll_description",
            element=PlainTextInputElement(
                placeholder="Enter poll description",
                multiline=True,
                action_id="poll_description"
            )
        ),
        InputBlock(
            label="Poll options",
            action_id="poll_options",
            element=PlainTextInputElement(
                placeholder="Enter poll options",
                multiline=True,
                action_id="poll_options"
            )
        ),
        InputBlock(
            label="Channel",
            action_id="channel_select",
            element=ChannelSelectElement(
                placeholder="Select a channel",
                action_id="channel_select"
            )
        ),
        ActionsBlock(elements=[
            ButtonElement(text="Start voting", style="primary", action_id="start_voting")
        ])
    ])

    if new_vote_error:
        blocks.append(SectionBlock(text=f"⚠️ {new_vote_error}"))
    
    return View(type="home", blocks=blocks)

# todo this signature is a bit haphazard -- should current_rankings be a List[VotingOption]?
def create_ranked_choice_ballot(title: str, options: List[VotingOption], message_ts: str, current_rankings: List[str] = None) -> View:
    """Create a modal view for the ranked choice ballot."""
    current_rankings = current_rankings or []
    rankings_text = "*Your rankings:*\n"
    if len(current_rankings) > 0:
        options_map = {option["id"]: option["text"] for option in options}
        rankings_text += "\n".join(f"{idx + 1}. {options_map.get(option_id, option_id)}" for idx, option_id in enumerate(current_rankings))
    else:
        rankings_text += "No rankings yet"

    blocks = [
        SectionBlock(text="Rank your choices by clicking the buttons below. Your ballot will be private."),
        DividerBlock(),
        SectionBlock(text=rankings_text),
        DividerBlock(),
        *[
            ActionsBlock(elements=[
                ButtonElement(text=option["text"], action_id="select_option", value=option["id"])
            ])
            for option in options
        ],
        ActionsBlock(elements=[
            ButtonElement(text="Clear ballot", style="danger", action_id="clear_ballot")
        ])
    ]
    
    # Create the modal view
    return View(
        type="modal",
        callback_id="ballot_modal",
        private_metadata=message_ts,  # Store the message_ts in private_metadata
        title=PlainTextObject(text=f"Ballot: {title[:15]}…" if len(title) > 16 else f"Ballot: {title}"),
        submit=PlainTextObject(text="Submit ballot"),
        close=PlainTextObject(text="Cancel"),
        blocks=blocks
    )
