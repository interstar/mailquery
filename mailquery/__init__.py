#!/usr/bin/env python3
"""
MailQuery - Fluent interface for email filtering and processing

A Python library that provides a jQuery-like fluent interface for filtering,
processing, and managing emails from various sources (Gmail, IMAP, etc.).

Main Components:
- Mailbox: Core filtering and processing interface
- Predicates: Server-side optimized filters
- Reducers: Email analysis and document generation
- Storage: Local email storage and transformation
- MailReader: Interactive email triage system

Usage:
    from mailquery import Mailbox, GmailClient
    
    client = GmailClient("credentials.json", fetch_limit=1000, batch_size=500)
    mailbox = Mailbox(client)
    
    # Filter and process emails
    mailbox.from_("newsletters").older_than(30).delete()
    
    # Interactive triage
    mailbox.from_("notifications").human(10).delete()
    
    # Analysis and storage
    mailbox.from_("reports").reduce_all(HTMLPageBuilder()).save("reports.html")
"""

from .mailbox import Mailbox, SubqueryMailbox
from .predicates import OR
from .reducers import (
    HTMLPageBuilder, 
    WordCountReducer, 
    TextDocumentBuilder, 
    EmailStatistics,
    AISummaryReducer,
    SenderCollector
)
from .storage import SQLiteStorage, MaildirStorage
from .mailreader import TriagePredicate
from .gmail_client import GmailClient
from .real_imap_client import RealImapClient
from .imap_client import DummyClient, IMAP_SERVERS
from .mbox_client import MboxClient, Mbox

# Import the mailreader submodule for advanced usage
import mailquery.mailreader

def spit(fname, s):
    """Write string s to file fname"""
    with open(fname, "w") as text_file:
        text_file.write(s)

__all__ = [
    # Core classes
    'Mailbox',
    'SubqueryMailbox',
    
    # Predicates
    'OR',
    
    # Reducers
    'HTMLPageBuilder',
    'WordCountReducer', 
    'TextDocumentBuilder',
    'EmailStatistics',
    'AISummaryReducer',
    'SenderCollector',
    
    # Storage
    'SQLiteStorage',
    'MaildirStorage',
    
    # Interactive triage
    'TriagePredicate',
    
    # Email clients
    'GmailClient',
    'RealImapClient',
    'DummyClient',
    'IMAP_SERVERS',
    'MboxClient',
    'Mbox',
    
    # Utility functions
    'spit',
    
    # Submodules
    'mailreader'
] 