import imaplib
import ssl
from typing import Generator, Optional, Dict, Any
from email import message_from_bytes
from email.policy import default
from .parsed_email import ParsedEmail, parse_envelope


class RealImapClient:
    """Real IMAP client that connects to actual email servers"""
    
    def __init__(self, credentials: Dict[str, str], allow_delete: bool = False):
        """
        Initialize with credentials
        
        Args:
            credentials: Dict with keys:
                - 'host': IMAP server hostname (e.g., 'imap.gmail.com')
                - 'port': IMAP port (usually 993 for SSL)
                - 'username': Email username
                - 'password': Email password or app password
                - 'use_ssl': Boolean, default True
            allow_delete: Whether to allow actual deletion of emails (default False for safety)
        """
        self.credentials = credentials
        self.allow_delete = allow_delete
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.connected = False
        
    def connect(self) -> None:
        """Establish connection to IMAP server"""
        try:
            host = self.credentials['host']
            port = self.credentials.get('port', 993)
            username = self.credentials['username']
            password = self.credentials['password']
            use_ssl = self.credentials.get('use_ssl', True)
            
            if use_ssl:
                # Create SSL context for secure connection
                context = ssl.create_default_context()
                self.connection = imaplib.IMAP4_SSL(host, port, ssl_context=context)
            else:
                self.connection = imaplib.IMAP4(host, port)
            
            # Login
            self.connection.login(username, password)
            self.connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to IMAP server: {e}")
    
    def disconnect(self) -> None:
        """Close the IMAP connection"""
        if self.connection and self.connected:
            try:
                self.connection.logout()
            except:
                pass  # Ignore errors during logout
            finally:
                self.connection = None
                self.connected = False
    
    def select_mailbox(self, mailbox: str = "INBOX") -> None:
        """Select a mailbox to work with"""
        if not self.connected:
            self.connect()
        
        status, messages = self.connection.select(mailbox)
        if status != 'OK':
            raise RuntimeError(f"Failed to select mailbox '{mailbox}': {status}")
    
    def list_messages(self, mailbox: str = "INBOX", limit: int = None, filters: list = None) -> Generator[ParsedEmail, None, None]:
        """
        List all messages in the mailbox, yielding ParsedEmail objects
        
        This fetches headers only initially. Body is fetched lazily when needed.
        """
        if not self.connected:
            self.connect()
        
        self.select_mailbox(mailbox)
        
        # Get UIDs for all messages
        status, uid_data = self.connection.uid('search', None, 'ALL')
        if status != 'OK':
            raise RuntimeError(f"Failed to get UIDs: {status}")
        
        if not uid_data[0]:
            return  # No messages
        
        uids = uid_data[0].split()
        
        # Apply limit if specified
        if limit:
            uids = uids[:limit]
            print(f"Limited to {len(uids)} messages")
        
        # Fetch headers for all messages in batches
        batch_size = 50  # Fetch 50 messages at a time to avoid timeouts
        
        for i in range(0, len(uids), batch_size):
            batch_uids = uids[i:i + batch_size]
            uid_list = b','.join(batch_uids)
            
            # Fetch full messages (headers + body) but we'll only parse headers for now
            status, message_data = self.connection.uid('fetch', uid_list, '(RFC822)')
            
            if status != 'OK':
                continue  # Skip this batch if there's an error
            

            
            # Process each message in the batch
            for j in range(0, len(message_data), 2):
                if j + 1 >= len(message_data):
                    break
                    
                uid_info = message_data[j]
                message_bytes = message_data[j + 1]
                
                if not uid_info or not message_bytes:
                    continue
                
                # Extract UID from response - uid_info is a tuple (uid_string, message_bytes)
                if isinstance(uid_info, tuple) and len(uid_info) == 2:
                    uid_str = uid_info[0].decode() if isinstance(uid_info[0], bytes) else str(uid_info[0])
                    uid = uid_str.split()[2].rstrip(')')
                    actual_message_bytes = uid_info[1]
                else:
                    # Fallback for different format
                    uid_info_str = uid_info.decode() if isinstance(uid_info, bytes) else str(uid_info)
                    uid = uid_info_str.split()[2].rstrip(')')
                    actual_message_bytes = message_bytes
                
                # Parse headers from full message
                envelope = self._parse_headers(actual_message_bytes)
                
                # Create lazy body fetcher (reuse the already fetched message)
                def make_body_fetcher(message_copy=actual_message_bytes):
                    def fetch_body():
                        return message_copy
                    return fetch_body
                
                yield ParsedEmail(uid, envelope, make_body_fetcher())
    
    def _parse_headers(self, header_bytes: bytes) -> Dict[str, str]:
        """Parse email headers from raw bytes"""
        try:
            if not isinstance(header_bytes, bytes):
                return {"sender": "", "subject": "", "date": "", "message_id": ""}
            
            # Parse the email message
            msg = message_from_bytes(header_bytes, policy=default)
            
            # Extract headers with fallbacks
            sender = msg.get("From", "")
            subject = msg.get("Subject", "")
            date = msg.get("Date", "")
            message_id = msg.get("Message-ID", "")
            reply_to = msg.get("Reply-To", "")
            to = msg.get("To", "")
            
            # Clean up the headers
            if sender:
                sender = sender.strip()
            if subject:
                subject = subject.strip()
            if date:
                date = date.strip()
            if message_id:
                message_id = message_id.strip()
            if reply_to:
                reply_to = reply_to.strip()
            if to:
                to = to.strip()
            
            return {
                "sender": sender,
                "subject": subject,
                "date": date,
                "message_id": message_id,
                "reply_to": reply_to,
                "to": to,
            }
            
        except Exception as e:
            # If parsing fails, try manual parsing of the raw bytes
            try:
                header_str = header_bytes.decode('utf-8', errors='ignore')
                lines = header_str.split('\n')
                
                sender = ""
                subject = ""
                date = ""
                message_id = ""
                reply_to = ""
                to = ""
                
                for line in lines:
                    line = line.strip()
                    if line.lower().startswith('from:'):
                        sender = line[5:].strip()
                    elif line.lower().startswith('subject:'):
                        subject = line[8:].strip()
                    elif line.lower().startswith('date:'):
                        date = line[5:].strip()
                    elif line.lower().startswith('message-id:'):
                        message_id = line[11:].strip()
                    elif line.lower().startswith('reply-to:'):
                        reply_to = line[9:].strip()
                    elif line.lower().startswith('to:'):
                        to = line[3:].strip()
                    elif line.startswith('\n') or line == '':
                        break  # End of headers
                
                return {
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "message_id": message_id,
                    "reply_to": reply_to,
                    "to": to,
                }
                
            except Exception:
                # Final fallback
                return {
                    "sender": "",
                    "subject": "",
                    "date": "",
                    "message_id": "",
                    "reply_to": "",
                    "to": "",
                }
    
    def _fetch_full_message(self, uid: str) -> bytes:
        """Fetch the full message body for a given UID"""
        if not self.connected:
            self.connect()
        
        status, data = self.connection.uid('fetch', uid, '(RFC822)')
        if status != 'OK' or not data or not data[0]:
            raise RuntimeError(f"Failed to fetch message {uid}")
        
        return data[0][1]  # Return the raw message bytes
    
    def delete_message(self, uid: str) -> bool:
        """Delete a message by UID"""
        if not self.connected:
            self.connect()
        
        if not self.allow_delete:
            print(f"Skipping deletion of message {uid} due to allow_delete=False")
            return False
        
        try:
            # Mark message for deletion
            status, _ = self.connection.uid('store', uid, '+FLAGS', '(\\Deleted)')
            if status != 'OK':
                return False
            
            # Expunge deleted messages
            status, _ = self.connection.expunge()
            return status == 'OK'
            
        except Exception as e:
            print(f"Error deleting message {uid}: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

 