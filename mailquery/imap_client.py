from .parsed_email import ParsedEmail, parse_envelope
from typing import Dict, Union


class DummyClient:
    """Dummy IMAP client for testing"""
    
    def __init__(self, credentials, allow_delete: bool = False):
        self.credentials = credentials
        self.allow_delete = allow_delete
        # Stub data for testing
        self._stub_data = {
            # Old emails from 2023
            "1": b"From: john@example.com\nSubject: Hello\nDate: 2023-06-25\nMessage-ID: <1@test>\n\nThis is the first message",
            "2": b"From: john@example.com\nSubject: Update\nDate: 2023-06-26\nMessage-ID: <2@test>\n\nThis one mentions foobar",
            "3": b"From: jane@example.com\nSubject: Spam\nDate: 2023-06-27\nMessage-ID: <3@test>\n\nTotally irrelevant",
            "4": b"From: alice@example.com\nSubject: Newsletter\nDate: 2023-06-28\nMessage-ID: <4@test>\n\nImportant newsletter with unsubscribe link",
            "5": b"From: bob@example.com\nSubject: Meeting\nDate: 2023-06-29\nMessage-ID: <5@test>\n\nMeeting tomorrow at 2pm",
            
            # Recent emails for testing time filters
            "6": b"From: recent@example.com\nSubject: Recent Email\nDate: Sun, 15 Dec 2024 12:00:00\nMessage-ID: <6@test>\n\nThis is a recent email",
            "7": b"From: today@example.com\nSubject: Today's Email\nDate: Fri, 20 Dec 2024 12:00:00\nMessage-ID: <7@test>\n\nThis is from today",
            "8": b"From: yesterday@example.com\nSubject: Yesterday's Email\nDate: Thu, 19 Dec 2024 12:00:00\nMessage-ID: <8@test>\n\nThis is from yesterday",
            "9": b"From: week_ago@example.com\nSubject: Week Ago Email\nDate: Fri, 13 Dec 2024 12:00:00\nMessage-ID: <9@test>\n\nThis is from a week ago",
            "10": b"From: month_ago@example.com\nSubject: Month Ago Email\nDate: Wed, 20 Nov 2024 12:00:00\nMessage-ID: <10@test>\n\nThis is from a month ago"
        }

    def list_messages(self, mailbox: str = "INBOX", limit: int = None, filters: list = None, verbose: bool = True):
        """Returns a generator of ParsedEmail objects with lazy body fetching"""
        for uid, raw in self._stub_data.items():
            envelope = parse_envelope(raw)
            
            # Create a closure to capture the raw data for lazy fetching
            def make_fetcher(raw_copy=raw):
                return lambda: raw_copy
            
            yield ParsedEmail(uid, envelope, make_fetcher())

    def delete_message(self, uid: str):
        """Delete a message by UID"""
        if not self.allow_delete:
            print(f"DummyClient: Skipping deletion of message {uid} due to allow_delete=False")
            return False
        
        if uid in self._stub_data:
            del self._stub_data[uid]
            return True
        return False


# Common IMAP server configurations
IMAP_SERVERS = {
    "gmail": {
        "host": "imap.gmail.com",
        "port": 993,
        "use_ssl": True
    },
    "outlook": {
        "host": "outlook.office365.com", 
        "port": 993,
        "use_ssl": True
    },
    "yahoo": {
        "host": "imap.mail.yahoo.com",
        "port": 993,
        "use_ssl": True
    },
    "icloud": {
        "host": "imap.mail.me.com",
        "port": 993,
        "use_ssl": True
    }
}
