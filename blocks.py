from typing import Any, Dict, List, TypedDict


class VotingOption(TypedDict):
    id: str
    text: str

def create_ranked_choice_prompt(options: List[VotingOption]) -> List[Dict[str, Any]]:
    """
    Creates a Slack blocks message for ranked choice voting with interactive buttons.
    
    Args:
        options: List of voting options with id and text
        
    Returns:
        List of Slack blocks
    """
    return [
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
                "text": "Click the options below in order from most to least preferred:"
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
                        "text": "Submit Rankings",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "submit_rankings"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Clear Rankings",
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
    Creates the home tab view for the Slack app.
    
    Args:
        active_votes: List of active voting sessions
        
    Returns:
        Home tab view
    """
    # Create the home tab view
    view = {
        "type": "home",
        "blocks": [
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
    }
    
    # Add active voting sessions
    if active_votes:
        for vote in active_votes:
            view["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Channel:* #{vote['channel_name']}"
                }
            })
            view["blocks"].append({
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
        view["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No active voting sessions."
            }
        })
    
    # Add start voting section
    view["blocks"].extend([
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
                    "action_id": "start_voting",
                    "disabled": True
                }
            ]
        }
    ])
    
    return view 