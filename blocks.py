from typing import Any, Dict, List


def create_ranked_choice_prompt(options: List[str]) -> List[Dict[str, Any]]:
    """
    Creates a Slack blocks message for ranked choice voting with interactive buttons.
    
    Args:
        options: List of voting options
        
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
                            "text": option,
                            "emoji": True
                        },
                        "value": option,
                        "action_id": f"select_option_{idx}"
                    }
                ]
            }
            for idx, option in enumerate(options)
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

def update_rankings_message(blocks: List[Dict[str, Any]], rankings: List[str]) -> List[Dict[str, Any]]:
    """
    Updates the rankings section of the message with current rankings.
    
    Args:
        blocks: Original message blocks
        rankings: Current list of ranked options
        
    Returns:
        Updated message blocks
    """
    # Find the rankings section and update it
    for block in blocks:
        if block.get("type") == "section" and "Your Rankings:" in block["text"]["text"]:
            rankings_text = "*Your Rankings:*\n"
            if rankings:
                rankings_text += "\n".join(f"{idx + 1}. {option}" for idx, option in enumerate(rankings))
            else:
                rankings_text += "No rankings yet"
            block["text"]["text"] = rankings_text
            break
    
    return blocks 