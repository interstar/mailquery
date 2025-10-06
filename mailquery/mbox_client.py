#!/usr/bin/env python3
"""
Mbox Client - Parse and process mbox format email files

This module provides an MboxClient that can read mbox format files (used by
Pine, Thunderbird, and other email clients) and integrate with the MailQuery
library's fluent interface.
"""

import os
import re
import email
import email.policy
from typing import Generator, Optional, Dict, Any
from datetime import datetime
from .parsed_email import ParsedEmail, parse_envelope


class MboxClient:
    """
    Client for reading mbox format email files.
    
    Mbox files contain multiple emails concatenated together, separated by
    lines starting with "From " (note the space). This client parses these
    files and provides emails in the same format as other MailQuery clients.
    """
    
    def __init__(self, mbox_file_path: str, verbose: bool = True, allow_delete: bool = False):
        """
        Initialize the mbox client.
        
        Args:
            mbox_file_path: Path to the mbox file to read
            verbose: Whether to print progress information
            allow_delete: Whether to allow actual deletion of emails (default False for safety)
        """
        self.mbox_path = mbox_file_path
        self.verbose = verbose
        self.allow_delete = allow_delete
        self.connected = False
        self.fetch_limit = None  # Will be set by factory function
        
        # Verify file exists
        if not os.path.exists(mbox_file_path):
            raise FileNotFoundError(f"Mbox file not found: {mbox_file_path}")
    
    def connect(self) -> None:
        """Establish connection to the mbox file (just verify it's readable)"""
        try:
            with open(self.mbox_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Just read first few bytes to verify file is readable
                f.read(1024)
            self.connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to read mbox file: {e}")
    
    def disconnect(self) -> None:
        """Close the mbox file connection"""
        self.connected = False
    
    def select_mailbox(self, mailbox: str = "INBOX") -> None:
        """Select a mailbox (mbox files don't need this, but keeping interface consistent)"""
        if not self.connected:
            self.connect()
        
        # Mbox files don't need explicit mailbox selection
        # All operations are on the single mbox file
        pass
    
    def _parse_mbox_separator(self, line: str) -> Optional[Dict[str, str]]:
        """
        Parse an mbox separator line.
        
        Args:
            line: Line starting with "From "
            
        Returns:
            Dictionary with sender and timestamp, or None if not a valid separator
        """
        # Mbox separator format: "From sender@domain.com timestamp"
        # Example: "From sa386@soi.city.ac.uk Sun Jun  1 10:42:18 2008 +0100"
        
        if not line.startswith("From "):
            return None
        
        # Remove "From " prefix
        content = line[5:].strip()
        
        # Find the last space-separated timestamp
        parts = content.split()
        if len(parts) < 2:
            return None
        
        # The timestamp is typically the last 5-6 parts
        # Try to find where the timestamp starts
        timestamp_start = -1
        for i in range(len(parts) - 1, 0, -1):
            # Look for patterns like "Sun Jun 1 10:42:18 2008 +0100"
            if len(parts[i]) == 5 and parts[i].startswith('+') or parts[i].startswith('-'):
                # Timezone offset found
                timestamp_start = max(0, i - 5)
                break
        
        if timestamp_start == -1:
            # Fallback: assume last 5 parts are timestamp
            timestamp_start = max(0, len(parts) - 5)
        
        sender = ' '.join(parts[:timestamp_start])
        timestamp = ' '.join(parts[timestamp_start:])
        
        return {
            'sender': sender,
            'timestamp': timestamp
        }
    
    def _parse_email_from_mbox(self, email_content: str, email_id: str) -> Optional[ParsedEmail]:
        """
        Parse a single email from mbox content.
        
        Args:
            email_content: Raw email content (headers + body)
            email_id: Unique identifier for this email
            
        Returns:
            ParsedEmail object or None if parsing failed
        """
        try:
            # Parse using Python's email module with more lenient encoding handling
            # First, try to clean up the email content to handle encoding issues
            try:
                email_message = email.message_from_string(email_content, policy=email.policy.default)
            except UnicodeDecodeError:
                # If the email content has encoding issues, try to fix it
                try:
                    # Try to decode and re-encode with replacement characters
                    if isinstance(email_content, str):
                        # If it's already a string, try to encode it properly
                        email_content = email_content.encode('utf-8', errors='replace').decode('utf-8')
                    else:
                        # If it's bytes, decode with replacement
                        email_content = email_content.decode('utf-8', errors='replace')
                    
                    email_message = email.message_from_string(email_content, policy=email.policy.default)
                except Exception as inner_e:
                    if self.verbose:
                        print(f"MboxClient: Could not parse email {email_id} due to encoding issues: {inner_e}")
                    return None
            
            # Extract headers
            envelope = {
                "sender": email_message.get('From', ''),
                "from": email_message.get('From', ''),  # Alias for consistency
                "sender_header": email_message.get('Sender', ''),  # Separate Sender header
                "subject": email_message.get('Subject', ''),
                "date": email_message.get('Date', ''),
                "message_id": email_message.get('Message-ID', ''),
                "reply_to": email_message.get('Reply-To', ''),
                "to": email_message.get('To', ''),
                "cc": email_message.get('Cc', ''),
                "bcc": email_message.get('Bcc', ''),
            }
            
            # Create lazy body fetcher with encoding error handling
            def make_body_fetcher(email_content=email_content):
                def fetch_body():
                    try:
                        return email_content.encode('utf-8')
                    except UnicodeEncodeError:
                        # If the content can't be encoded as UTF-8, try with replacement characters
                        return email_content.encode('utf-8', errors='replace')
                return fetch_body
            
            return ParsedEmail(email_id, envelope, make_body_fetcher())
            
        except Exception as e:
            if self.verbose:
                error_msg = str(e)
                if "unknown encoding" in error_msg.lower():
                    print(f"MboxClient: Skipping email {email_id} due to encoding issues")
                else:
                    print(f"MboxClient: Failed to parse email {email_id}: {e}")
            return None
    
    def list_messages(self, mailbox: str = "INBOX", filters: list = None, verbose: bool = None) -> Generator[ParsedEmail, None, None]:
        """
        List all messages in the mbox file, yielding ParsedEmail objects
        
        This parses the entire mbox file and yields emails one by one.
        """
        if not self.connected:
            self.connect()
        
        verbose_mode = verbose if verbose is not None else self.verbose
        
        if verbose_mode:
            print(f"MboxClient: Reading messages from {self.mbox_path}")
        
        try:
            # Try to read the file with better encoding handling
            try:
                with open(self.mbox_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                # Fallback to latin-1 if UTF-8 fails
                with open(self.mbox_path, 'r', encoding='latin-1', errors='replace') as f:
                    lines = f.readlines()
            
            current_email_content = []
            current_email_id = None
            email_count = 0
            
            for line_num, line in enumerate(lines, 1):
                # Check if this is an mbox separator
                separator_info = self._parse_mbox_separator(line)
                
                if separator_info and current_email_content:
                    # We found a new email, process the previous one
                    if current_email_id:
                        try:
                            email_content = ''.join(current_email_content)
                        except UnicodeDecodeError:
                            # Handle encoding issues in the joined content
                            if verbose_mode:
                                print(f"MboxClient: Skipping email {current_email_id} due to encoding issues in content")
                            current_email_content = [line]
                            current_email_id = f"mbox_{line_num}"
                            continue
                        
                        email = self._parse_email_from_mbox(
                            email_content, 
                            current_email_id
                        )
                        if email:
                            email_count += 1
                            if verbose_mode:
                                print(f"MboxClient: Parsed email {email_count}: {email.envelope.get('subject', 'No Subject')}")
                            yield email
                        
                        # Check fetch limit
                        if self.fetch_limit and email_count >= self.fetch_limit:
                            if verbose_mode:
                                print(f"MboxClient: Reached fetch limit of {self.fetch_limit}")
                            break
                    
                    # Start new email
                    current_email_content = [line]
                    current_email_id = f"mbox_{line_num}"
                
                elif separator_info:
                    # First email in file
                    current_email_content = [line]
                    current_email_id = f"mbox_{line_num}"
                
                else:
                    # Regular line, add to current email
                    current_email_content.append(line)
                
                # Process the last email
                if current_email_content and current_email_id:
                    try:
                        email_content = ''.join(current_email_content)
                    except UnicodeDecodeError:
                        if verbose_mode:
                            print(f"MboxClient: Skipping final email {current_email_id} due to encoding issues")
                        email = None
                    else:
                        email = self._parse_email_from_mbox(
                            email_content, 
                            current_email_id
                        )
                    if email:
                        email_count += 1
                        if verbose_mode:
                            print(f"MboxClient: Parsed email {email_count}: {email.envelope.get('subject', 'No Subject')}")
                        yield email
                
                if verbose_mode:
                    print(f"MboxClient: Total emails parsed: {email_count}")
        
        except Exception as e:
            raise RuntimeError(f"Failed to read mbox file: {e}")
    
    def delete_message(self, uid: str) -> bool:
        """
        Delete a message from the mbox file.
        
        Note: This is a destructive operation that modifies the original file.
        Consider backing up the file before using this feature.
        
        Args:
            uid: The email UID to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.allow_delete:
            print(f"MboxClient: Skipping deletion of message {uid} due to allow_delete=False")
            return False
        
        # TODO: Implement mbox file modification
        # This would require rewriting the file without the specified email
        if self.verbose:
            print(f"MboxClient: Delete not implemented yet for email {uid}")
        return False





# Convenience alias
Mbox = MboxClient
