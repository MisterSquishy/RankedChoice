import json
import sqlite3
from typing import Any, Dict, List, Optional, TypedDict


class VotingOption(TypedDict):
    id: str
    text: str

class PollSession(TypedDict):
    is_active: bool
    message_ts: Optional[str]
    title: str
    options: List[VotingOption]

class Database:
    def __init__(self, db_path: str = "/data/ranked_choice.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create elections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS elections (
                    channel_id TEXT PRIMARY KEY,
                    is_active BOOLEAN,
                    message_ts TEXT,
                    title TEXT,
                    options TEXT
                )
            """)
            
            # Create ballots table (renamed from user_rankings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ballots (
                    message_ts TEXT,
                    user_id TEXT,
                    rankings TEXT,
                    is_submitted BOOLEAN,
                    PRIMARY KEY (message_ts, user_id)
                )
            """)
            
            conn.commit()

    def get_active_election(self, channel_id: str) -> Optional[PollSession]:
        """Get active session for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_active, message_ts, title, options FROM elections WHERE channel_id = ?",
                (channel_id,)
            )
            result = cursor.fetchone()
            
            if result:
                is_active, message_ts, title, options_json = result
                return {
                    "is_active": bool(is_active),
                    "message_ts": message_ts,
                    "title": title,
                    "options": json.loads(options_json)
                }
            return None

    def get_all_active_elections(self) -> Dict[str, PollSession]:
        """Get all active sessions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, is_active, message_ts, title, options FROM elections")
            results = cursor.fetchall()
            
            sessions = {}
            for channel_id, is_active, message_ts, title, options_json in results:
                sessions[channel_id] = {
                    "is_active": bool(is_active),
                    "message_ts": message_ts,
                    "title": title,
                    "options": json.loads(options_json)
                }
            return sessions

    def set_active_election(self, channel_id: str, session: PollSession) -> None:
        """Set active session for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO elections 
                (channel_id, is_active, message_ts, title, options)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    channel_id,
                    session["is_active"],
                    session["message_ts"],
                    session["title"],
                    json.dumps(session["options"])
                )
            )
            conn.commit()

    def get_ballots(self, message_ts: str) -> Dict[str, List[str]]:
        """Get all submitted ballots for a message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, rankings FROM ballots WHERE message_ts = ? AND is_submitted = 1",
                (message_ts,)
            )
            results = cursor.fetchall()
            
            ballots = {}
            for user_id, rankings_json in results:
                ballots[user_id] = json.loads(rankings_json)
            return ballots

    def get_all_ballots(self) -> Dict[str, Dict[str, List[str]]]:
        """Get all submitted ballots for all messages."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message_ts, user_id, rankings FROM ballots WHERE is_submitted = 1")
            results = cursor.fetchall()
            
            all_ballots = {}
            for message_ts, user_id, rankings_json in results:
                if message_ts not in all_ballots:
                    all_ballots[message_ts] = {}
                all_ballots[message_ts][user_id] = json.loads(rankings_json)
            return all_ballots

    def get_user_ballot(self, message_ts: str, user_id: str) -> Optional[List[str]]:
        """Get a user's ballot for a message, whether submitted or not."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT rankings, is_submitted FROM ballots WHERE message_ts = ? AND user_id = ?",
                (message_ts, user_id)
            )
            result = cursor.fetchone()
            
            if result:
                rankings_json, is_submitted = result
                return json.loads(rankings_json)
            return None

    def is_ballot_submitted(self, message_ts: str, user_id: str) -> bool:
        """Check if a user's ballot is submitted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_submitted FROM ballots WHERE message_ts = ? AND user_id = ?",
                (message_ts, user_id)
            )
            result = cursor.fetchone()
            
            if result:
                return bool(result[0])
            return False

    def set_ballot(self, message_ts: str, user_id: str, rankings: List[str], is_submitted: bool = False) -> None:
        """Set a user's ballot for a message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO ballots 
                (message_ts, user_id, rankings, is_submitted)
                VALUES (?, ?, ?, ?)
                """,
                (message_ts, user_id, json.dumps(rankings), is_submitted)
            )
            conn.commit()

    def submit_ballot(self, message_ts: str, user_id: str) -> None:
        """Mark a user's ballot as submitted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ballots SET is_submitted = 1 WHERE message_ts = ? AND user_id = ?",
                (message_ts, user_id)
            )
            conn.commit()

    def clear_ballot(self, message_ts: str, user_id: str) -> None:
        """Clear a user's ballot for a message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ballots WHERE message_ts = ? AND user_id = ?",
                (message_ts, user_id)
            )
            conn.commit()

    def get_ballot(self, message_ts: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a ballot for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT message_ts, user_id, rankings, is_submitted
                FROM ballots
                WHERE message_ts = ? AND user_id = ?
                """,
                (message_ts, user_id)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "message_ts": row[0],
                    "user_id": row[1],
                    "rankings": json.loads(row[2]) if row[2] else [],
                    "is_submitted": bool(row[3])
                }
            return None

    def get_vote(self, message_ts: str) -> Optional[Dict[str, Any]]:
        """Get vote details by message timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, options, channel_id
                FROM elections
                WHERE message_ts = ? AND is_active
                """,
                (message_ts,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "title": row[0],
                    "options": json.loads(row[1]),
                    "channel_id": row[2]
                }
            return None 