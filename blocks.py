from typing import Any, Dict, List, TypedDict


class VotingOption(TypedDict):
    id: str
    text: str

def create_ranked_choice_prompt(options: List[VotingOption], title: str = "Ranked Choice Voting") -> List[Dict[str, Any]]:
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
                "text": "Click the options below to rank your choices (1 being your top choice):"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Your Rankings:*\nNo rankings yet"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Available Options:*"
            }
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
                        "text": "Submit",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "submit_rankings"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete last choice",
                        "emoji": True
                    },
                    "action_id": "delete_lowest_rank"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Clear",
                        "emoji": True
                    },
                    "style": "danger",
                    "action_id": "clear_rankings"
                }
            ]
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
        if block.get("type") == "section" and "Your Rankings:" in block["text"]["text"]:
            rankings_text = "*Your Rankings:*\n"
            if rankings:
                rankings_text += "\n".join(f"{idx + 1}. {option_map.get(option_id, option_id)}" for idx, option_id in enumerate(rankings))
            else:
                rankings_text += "No rankings yet"
            block["text"]["text"] = rankings_text
            break
    
    return blocks


def create_home_view(active_votes: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Create the home tab view.
    
    Args:
        active_votes: List of active voting sessions
        
    Returns:
        Dict containing the view definition
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🗳️ Ranked Choice Voting",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Welcome to the Ranked Choice Voting app! Use this tab to manage voting sessions."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Active Voting Sessions:*"
            }
        }
    ]
    
    # Add active voting sessions
    if active_votes:
        for vote in active_votes:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Channel:* #{vote['channel_name']}"
                }
            })
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Stop Voting",
                            "emoji": True
                        },
                        "style": "danger",
                        "action_id": "stop_voting",
                        "value": vote["channel_id"]
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Show Results",
                            "emoji": True
                        },
                        "action_id": "show_results",
                        "value": vote["channel_id"]
                    }
                ]
            })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No active voting sessions."
            }
        })
    
    # Add start voting section
    blocks.extend([
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Start a New Voting Session:*"
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
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter poll title (e.g., 'Team Lunch Options')",
                    "emoji": True
                },
                "action_id": "poll_title"
            },
            "label": {
                "type": "plain_text",
                "text": "Poll Title",
                "emoji": True
            }
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter options (one per line)",
                    "emoji": True
                },
                "multiline": True,
                "action_id": "poll_options"
            },
            "label": {
                "type": "plain_text",
                "text": "Poll Options",
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