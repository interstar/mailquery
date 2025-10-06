#!/usr/bin/env python3
"""
Example: Using mailquery with Gmail OAuth2
"""

from mailquery import GmailClient, Mailbox
from mailquery.storage import SQLiteStorage

def main():
    # Create Gmail OAuth2 client
    # You'll need to download credentials.json from Google Cloud Console
    client = GmailClient("credentials.json")
    
    # Create a new Mailbox object for each query to ensure a clean filter set.
    # The fluent interface chains filters, so reusing the same object would
    # cause filters to stack across independent queries.
    
    # --- Example 1: List recent emails ---
    print("📬 Recent emails:")
    Mailbox(client).list_all(limit=5)
    
    # --- Example 2: Store emails from a specific domain ---
    print("\n📥 Storing emails from a specific domain:")
    # This creates a new query, independent of the one above.
    Mailbox(client).from_("example.com").store_local(SQLiteStorage("gmail_emails.db"))
    
    # --- Example 3: Complex filtering ---
    print("\n🔍 Complex filtering:")
    # This query finds emails with "important" in the subject, but excludes
    # those that also contain "spam".
    Mailbox(client).subject_contains("important")\
        .exclude_when(lambda e: "spam" in e["subject"].lower())\
        .list_all(limit=3)

if __name__ == "__main__":
    main()