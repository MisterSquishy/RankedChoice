from datetime import datetime
from typing import Any, Dict, List, TypedDict


class VotingOption(TypedDict):
    id: str
    text: str

def create_ranked_choice_prompt(options: List[VotingOption], title: str = "Ranked Choice Voting", description: str = "") -> List[Dict[str, Any]]:
    """
    Creates a Slack blocks message for ranked choice voting with interactive buttons.
    
    Args:
        options: List of voting options with id and text
        title: Title of the poll
        
    Returns:
        List of Slack blocks
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🗳️ {title}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": description
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Request a ballot",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "request_ballot"
                }
            ]
        }
    ]

def create_submitted_message(user_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}> voted! Thank you for doing your civic duty 🫡"
            }
        }
    ]


def update_rankings_message(blocks: List[Dict[str, Any]], rankings: List[str], options: List[VotingOption]) -> List[Dict[str, Any]]:
    """
    Updates the rankings section of the message with current rankings.
    
    Args:
        blocks: Original message blocks
        rankings: Current list of ranked option IDs
        options: List of all options with id and text
        
    Returns:
        Updated message blocks
    """
    # Create a mapping of option IDs to their text
    option_map = {option["id"]: option["text"] for option in options}
    
    # Find the rankings section and update it
    for block in blocks:
        if block.get("type") == "section" and "Your rankings:" in block["text"]["text"]:
            rankings_text = "*Your rankings:*\n"
            if rankings:
                rankings_text += "\n".join(f"{idx + 1}. {option_map.get(option_id, option_id)}" for idx, option_id in enumerate(rankings))
            else:
                rankings_text += "No rankings yet"
            block["text"]["text"] = rankings_text
            break
    
    return blocks


def create_home_view(active_votes: List[Dict[str, str]], all_ballots: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """
    Create the home tab view.
    
    Args:
        active_votes: List of active voting sessions
        all_ballots: Dictionary of all submitted ballots by message timestamp
    
    Returns:
        The home tab view blocks
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "RankedChoice admin console",
                "emoji": True
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Active elections*"
            }
        }
    ]
    
    if not active_votes:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No active elections."
            }
        })
    else:
        for vote in active_votes:
            channel_id = vote["channel_id"]
            channel_name = vote["channel_name"]
            message_ts = vote["message_ts"]
            title = vote["title"]
            
            # Count submitted ballots for this session
            session_ballots = all_ballots.get(message_ts, {})
            submitted_count = sum(1 for ballot in session_ballots.values() if ballot)
            
            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*#{channel_name}*: {title}\n{submitted_count} {'ballot' if submitted_count == 1 else 'ballots'} submitted"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Close the poll",
                                "emoji": True
                            },
                            "value": channel_id,
                            "action_id": "stop_voting",
                            "style": "danger"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Post current results",
                                "emoji": True
                            },
                            "value": channel_id,
                            "action_id": "show_results"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Bump",
                                "emoji": True
                            },
                            "value": channel_id,
                            "action_id": "bump"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Cancel",
                                "emoji": True
                            },
                            "value": channel_id,
                            "action_id": "cancel"
                        }
                    ]
                }
            ])
    
    blocks.extend([
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Start a new election*"
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "poll_title",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter poll title"
                }
            },
            "label": {
                "type": "plain_text",
                "text": "Poll title",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "poll_description",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter description"
                }
            },
            "label": {
                "type": "plain_text",
                "text": "Poll description",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "poll_options",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter options (one per line)"
                }
            },
            "label": {
                "type": "plain_text",
                "text": "Poll options",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "channels_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a channel",
                    "emoji": True
                },
                "action_id": "channel_select"
            },
            "label": {
                "type": "plain_text",
                "text": "Channel",
                "emoji": True
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Start Voting",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "start_voting"
                }
            ]
        }
    ])
    
    return {
        "type": "home",
        "blocks": blocks
    }

def create_ranked_choice_ballot(title: str, options: List[VotingOption], message_ts: str, current_rankings: List[str] = None) -> Dict[str, Any]:
    """Create a modal view for the ranked choice ballot."""
    current_rankings = current_rankings or []
    rankings_text = "*Your rankings:*\n"
    if len(current_rankings) > 0:
        options_map = {option["id"]: option["text"] for option in options}
        rankings_text += "\n".join(f"{idx + 1}. {options_map.get(option_id, option_id)}" for idx, option_id in enumerate(current_rankings))
    else:
        rankings_text += "No rankings yet"
    
    # Create the modal view
    return {
        "type": "modal",
        "callback_id": "ballot_modal",
        "private_metadata": message_ts,  # Store the message_ts in private_metadata
        "title": {
            "type": "plain_text",
            "text": f"Ballot: {title[:15]}…" if len(title) > 16 else f"Ballot: {title}",
            "emoji": True
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit ballot",
            "emoji": True
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel",
            "emoji": True
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Rank your choices by clicking the buttons below. Your ballot will be private."
                }
            },
            {
                "type": "divider"
            },
            {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": rankings_text
            }
            },
            {
                "type": "divider"
            },
            *[
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": option["text"],
                                "emoji": True
                            },
                            "value": option["id"],
                            "action_id": "select_option"
                        }
                    ]
                }
                for option in options
            ],
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Clear ballot",
                            "emoji": True
                        },
                        "style": "danger",
                        "action_id": "clear_ballot" 
                    }
                ]
            }
        ]
    }

def create_ranked_choice_announcement(title: str, options: List[VotingOption], user_id: str, message_ts: str = None) -> List[Dict[str, Any]]:
    """Create a public announcement message for a new vote."""
    options_text = "\n".join([f"• {option['text']}" for option in options])
    
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "A ranked choice vote has started! Click the button below to receive your ballot."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Options:*\n{options_text}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Request ballot",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "request_ballot",
                    "value": message_ts or ""
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Started by <@{user_id}> • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        }
    ] 