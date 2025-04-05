import json
import sqlite3
from typing import Dict, List, Optional, TypedDict


class VotingOption(TypedDict):
    id: str
    text: str

class PollSession(TypedDict):
    is_active: bool
    message_ts: Optional[str]
    title: str
    options: List[VotingOption]

class Database:
    def __init__(self, db_path: str = "ranked_choice.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create active_sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_sessions (
                    channel_id TEXT PRIMARY KEY,
                    is_active BOOLEAN,
                    message_ts TEXT,
                    title TEXT,
                    options TEXT
                )
            """)
            
            # Create user_rankings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_rankings (
                    message_ts TEXT,
                    user_id TEXT,
                    rankings TEXT,
                    PRIMARY KEY (message_ts, user_id)
                )
            """)
            
            conn.commit()

    def get_active_session(self, channel_id: str) -> Optional[PollSession]:
        """Get active session for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_active, message_ts, title, options FROM active_sessions WHERE channel_id = ?",
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

    def get_all_active_sessions(self) -> Dict[str, PollSession]:
        """Get all active sessions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, is_active, message_ts, title, options FROM active_sessions")
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

    def set_active_session(self, channel_id: str, session: PollSession) -> None:
        """Set active session for a channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO active_sessions 
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

    def get_user_rankings(self, message_ts: str) -> Dict[str, List[str]]:
        """Get all user rankings for a message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, rankings FROM user_rankings WHERE message_ts = ?",
                (message_ts,)
            )
            results = cursor.fetchall()
            
            rankings = {}
            for user_id, rankings_json in results:
                rankings[user_id] = json.loads(rankings_json)
            return rankings

    def get_all_user_rankings(self) -> Dict[str, Dict[str, List[str]]]:
        """Get all user rankings for all messages."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message_ts, user_id, rankings FROM user_rankings")
            results = cursor.fetchall()
            
            all_rankings = {}
            for message_ts, user_id, rankings_json in results:
                if message_ts not in all_rankings:
                    all_rankings[message_ts] = {}
                all_rankings[message_ts][user_id] = json.loads(rankings_json)
            return all_rankings

    def set_user_rankings(self, message_ts: str, user_id: str, rankings: List[str]) -> None:
        """Set rankings for a user and message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_rankings 
                (message_ts, user_id, rankings)
                VALUES (?, ?, ?)
                """,
                (message_ts, user_id, json.dumps(rankings))
            )
            conn.commit()

    def clear_user_rankings(self, message_ts: str, user_id: str) -> None:
        """Clear rankings for a user and message."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_rankings WHERE message_ts = ? AND user_id = ?",
                (message_ts, user_id)
            )
            conn.commit() 