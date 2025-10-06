import os
import pickle
import base64
import email.message
import email.policy
from typing import Generator, Optional, Dict, Any
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .parsed_email import ParsedEmail, parse_envelope


class GmailClient:
    """Gmail API client that implements the same interface as RealImapClient"""
    
    # Gmail API scopes needed for reading and modifying emails
    SCOPES = [
        'https://mail.google.com/'  # Full Gmail access (matches OAuth consent screen)
    ]
    
    def __init__(self, credentials_json_path: str = "credentials.json", batch_size: int = 100, fetch_limit: int = None, allow_delete: bool = False):
        """
        Initialize Gmail OAuth2 client
        
        Args:
            credentials_json_path: Path to the credentials.json file from Google Cloud Console
            batch_size: Number of messages to fetch per API call (1-500, default 100)
            fetch_limit: Maximum number of emails to fetch from server (None for all emails)
            allow_delete: Whether to allow actual deletion of emails (default False for safety)
        """
        self.credentials_path = credentials_json_path
        self.batch_size = min(max(batch_size, 1), 500)  # Clamp between 1 and 500
        self.fetch_limit = fetch_limit
        self.allow_delete = allow_delete
        self.service = None
        self.connected = False
        self.verbose = True  # Default verbose setting
        
    def _get_credentials(self):
        """Get OAuth2 credentials for Gmail API"""
        creds = None
        
        # Load existing credentials from token.pickle
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    def connect(self) -> None:
        """Establish connection to Gmail API"""
        try:
            creds = self._get_credentials()
            self.service = build('gmail', 'v1', credentials=creds)
            self.connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Gmail API: {e}")
    
    def disconnect(self) -> None:
        """Close the Gmail API connection"""
        self.service = None
        self.connected = False
    
    def select_mailbox(self, mailbox: str = "INBOX") -> None:
        """Select a mailbox (Gmail API doesn't need this, but keeping interface consistent)"""
        if not self.connected:
            self.connect()
        
        # Gmail API doesn't need explicit mailbox selection
        # All operations are on the user's mailbox
        pass
    
    def _fetch_all_message_ids(self):
        """Fetch all message IDs from Gmail API with pagination"""
        messages = []
        page_token = None
        
        while True:
            # Calculate how many messages to request in this batch
            if self.fetch_limit:
                remaining = self.fetch_limit - len(messages)
                if remaining <= 0:
                    break
                batch_size = min(self.batch_size, remaining)
            else:
                batch_size = self.batch_size
            
            # Get batch of message IDs
            results = self.service.users().messages().list(
                userId='me', 
                pageToken=page_token,
                maxResults=batch_size
            ).execute()
            
            batch_messages = results.get('messages', [])
            messages.extend([msg['id'] for msg in batch_messages])
            
            # Check if we've reached the fetch limit
            if self.fetch_limit and len(messages) >= self.fetch_limit:
                messages = messages[:self.fetch_limit]  # Trim to exact limit
                break
            
            # Check if there are more pages
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        if self.fetch_limit:
            print(f"Fetched {len(messages)} messages (limited to {self.fetch_limit})")
        else:
            print(f"Found {len(messages)} total messages")
        
        return messages
    
    def _create_parsed_email(self, msg_id: str) -> ParsedEmail:
        """Create a ParsedEmail object for a given message ID"""
        try:
            # Fetch message details (headers only for now)
            msg = self.service.users().messages().get(
                userId='me', id=msg_id, format='metadata',
                metadataHeaders=['From', 'Sender', 'Subject', 'Date', 'Message-ID', 'Reply-To', 'To', 'Cc', 'Bcc']
            ).execute()
            
            # Extract headers
            headers = msg.get('payload', {}).get('headers', [])
            header_dict = {h['name']: h['value'] for h in headers}
            
            # Debug: Check if this is a problematic email (empty date but matches date filter)
            date_header = header_dict.get('Date', '')
            if not date_header and self.verbose:
                print(f"GmailClient: DEBUG - Message {msg_id} has empty Date header")
                print(f"GmailClient: DEBUG - Full Gmail API response keys: {list(msg.keys())}")
                if 'internalDate' in msg:
                    print(f"GmailClient: DEBUG - Internal date: {msg['internalDate']}")
                if 'snippet' in msg:
                    print(f"GmailClient: DEBUG - Snippet: {msg['snippet']}")
                print(f"GmailClient: DEBUG - Headers found: {list(header_dict.keys())}")
            
            # Create envelope dict similar to IMAP format
            envelope = {
                "sender": header_dict.get('From', ''),
                "from": header_dict.get('From', ''),  # Alias for consistency
                "sender_header": header_dict.get('Sender', ''),  # Separate Sender header
                "subject": header_dict.get('Subject', ''),
                "date": header_dict.get('Date', ''),
                "message_id": header_dict.get('Message-ID', ''),
                "reply_to": header_dict.get('Reply-To', ''),
                "to": header_dict.get('To', ''),
                "cc": header_dict.get('Cc', ''),
                "bcc": header_dict.get('Bcc', ''),
            }
            
            # Use Gmail's internal date as fallback if email header date is empty
            if not envelope["date"] and 'internalDate' in msg:
                try:
                    from datetime import datetime
                    # Convert milliseconds to datetime
                    internal_timestamp = int(msg['internalDate']) / 1000  # Convert to seconds
                    internal_date = datetime.fromtimestamp(internal_timestamp)
                    # Format as RFC 2822 string
                    envelope["date"] = internal_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
                    if self.verbose:
                        print(f"GmailClient: Using internal date for message {msg_id}: {envelope['date']}")
                except Exception as e:
                    if self.verbose:
                        print(f"GmailClient: Failed to convert internal date for message {msg_id}: {e}")
            
            # Create lazy body fetcher
            def make_body_fetcher(msg_id=msg_id):
                def fetch_body():
                    return self._fetch_full_message(msg_id)
                return fetch_body
            
            return ParsedEmail(msg_id, envelope, make_body_fetcher())
            
        except HttpError as error:
            if error.resp.status == 404:
                # Message not found - skip this message
                if self.verbose:
                    print(f"GmailClient: Skipping message {msg_id} - not found (may have been deleted)")
                return None
            else:
                # Re-raise other HTTP errors
                raise
    
    def list_messages(self, mailbox: str = "INBOX", filters: list = None, verbose: bool = None) -> Generator[ParsedEmail, None, None]:
        """
        List all messages in the mailbox, yielding ParsedEmail objects
        
        This fetches headers only initially. Body is fetched lazily when needed.
        The number of messages returned is limited by self.fetch_limit.
        
        Args:
            mailbox: Mailbox name (Gmail API doesn't use this, but keeping interface consistent)
            filters: Optional list of filter objects for server-side optimization
            verbose: Whether to print diagnostic messages (overrides self.verbose if provided)
        """
        if not self.connected:
            self.connect()
        
        # Use passed verbose parameter or fall back to instance setting
        verbose_mode = verbose if verbose is not None else self.verbose
        
        limit = self.fetch_limit
        
        # Build server-side query from filters if provided
        query = self._build_server_query(filters, verbose_mode) if filters else None
        if verbose_mode:
            print(f"GmailClient: Built query: {query}")
            print(f"GmailClient: Using fetch_limit: {limit}")
        
        try:
            count = 0
            page_token = None
            date_range = {'earliest': None, 'latest': None}
            
            while True:
                # Calculate batch size
                if self.fetch_limit:
                    remaining = self.fetch_limit - count
                    if remaining <= 0:
                        break
                    batch_size = min(self.batch_size, remaining)  # Use configured batch size
                else:
                    batch_size = self.batch_size
                
                # Get batch of message IDs
                #print(f"GmailClient: Making API call with query='{query}', maxResults={batch_size}")
                results = self.service.users().messages().list(
                    userId='me', 
                    pageToken=page_token,
                    maxResults=batch_size,
                    q=query
                ).execute()
                
                batch_messages = results.get('messages', [])
                result_size_estimate = results.get('resultSizeEstimate', 'unknown')
                if verbose_mode:
                    print(f"GmailClient: Got {len(batch_messages)} messages from API (total estimate: {result_size_estimate})")
                    
                    # Peek at the first message in this batch to show date range
                    if batch_messages:
                        try:
                            first_msg_id = batch_messages[0]['id']
                            # Get just the headers for the first message (fast operation)
                            first_msg = self.service.users().messages().get(
                                userId='me', id=first_msg_id, format='metadata', 
                                metadataHeaders=['Date']
                            ).execute()
                            
                            # Extract date from headers
                            headers = first_msg.get('payload', {}).get('headers', [])
                            date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
                            
                            if date_header:
                                print(f"GmailClient: First message in this batch dated: {date_header}")
                            else:
                                print("GmailClient: Could not determine date of first message in batch")
                        except Exception as e:
                            if verbose_mode:
                                print(f"GmailClient: Could not peek at first message date: {e}")
                
                if not batch_messages:
                    break
                
                # Create ParsedEmail objects for this batch
                for msg in batch_messages:
                    parsed_email = self._create_parsed_email(msg['id'])
                    if parsed_email is not None:
                        count += 1
                        
                        # Track date range for verbose output
                        if verbose_mode and 'date' in parsed_email.envelope and parsed_email['date']:
                            try:
                                from datetime import datetime
                                # Try to parse the date
                                date_str = parsed_email['date']
                                # Handle various date formats
                                email_date = None
                                
                                # Try multiple date formats
                                for fmt in [
                                    "%a, %d %b %Y %H:%M:%S %z",
                                    "%a, %d %b %Y %H:%M:%S",
                                    "%d %b %Y %H:%M:%S %z",
                                    "%d %b %Y %H:%M:%S"
                                ]:
                                    try:
                                        email_date = datetime.strptime(date_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                                
                                if email_date:
                                    if date_range['earliest'] is None or email_date < date_range['earliest']:
                                        date_range['earliest'] = email_date
                                    if date_range['latest'] is None or email_date > date_range['latest']:
                                        date_range['latest'] = email_date
                            except Exception:
                                # Skip date parsing errors
                                pass
                        
                        yield parsed_email
                        
                        if self.fetch_limit and count >= self.fetch_limit:
                            # Print date range summary when we hit the limit
                            if verbose_mode:
                                if date_range['earliest'] and date_range['latest']:
                                    print(f"GmailClient: Date range of fetched emails: {date_range['earliest'].strftime('%Y-%m-%d %H:%M')} to {date_range['latest'].strftime('%Y-%m-%d %H:%M')}")
                                elif date_range['earliest']:
                                    print(f"GmailClient: Earliest email date: {date_range['earliest'].strftime('%Y-%m-%d %H:%M')}")
                                elif date_range['latest']:
                                    print(f"GmailClient: Latest email date: {date_range['latest'].strftime('%Y-%m-%d %H:%M')}")
                                else:
                                    print("GmailClient: Could not determine date range of fetched emails")
                            break
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            # Print final summary with date range
            if verbose_mode:
                if date_range['earliest'] and date_range['latest']:
                    print(f"GmailClient: Date range of fetched emails: {date_range['earliest'].strftime('%Y-%m-%d %H:%M')} to {date_range['latest'].strftime('%Y-%m-%d %H:%M')}")
                elif date_range['earliest']:
                    print(f"GmailClient: Earliest email date: {date_range['earliest'].strftime('%Y-%m-%d %H:%M')}")
                elif date_range['latest']:
                    print(f"GmailClient: Latest email date: {date_range['latest'].strftime('%Y-%m-%d %H:%M')}")
                else:
                    print("GmailClient: Could not determine date range of fetched emails")
                
        except HttpError as error:
            raise RuntimeError(f"Gmail API error: {error}")
    
    def _build_server_query(self, filters: list, verbose: bool = None) -> str:
        """
        Build Gmail API query string from filter list
        
        Args:
            filters: List of filter objects (functions and Predicate instances)
            verbose: Whether to print diagnostic messages (overrides self.verbose if provided)
        
        Returns:
            Gmail API query string or None if no server-side filters found
        """
        if not filters:
            return None
        
        # Use passed verbose parameter or fall back to instance setting
        verbose_mode = verbose if verbose is not None else self.verbose
        
        if verbose_mode:
            print(f"GmailClient: Building query from {len(filters)} filters")
        
        # Group predicates by type for OR handling
        from_predicates = []
        to_predicates = []
        involves_predicates = []
        date_predicates = []
        
        for i, filter_obj in enumerate(filters):
            if verbose_mode:
                print(f"GmailClient: Filter {i}: {type(filter_obj).__name__} = {filter_obj}")
            
            # Group predicates by type
            if hasattr(filter_obj, '__class__'):
                class_name = filter_obj.__class__.__name__
                if class_name == 'FROM':
                    from_predicates.append(filter_obj)
                elif class_name == 'TO':
                    to_predicates.append(filter_obj)
                elif class_name == 'INVOLVES':
                    involves_predicates.append(filter_obj)
                elif class_name in ['BEFORE', 'AFTER']:
                    date_predicates.append(filter_obj)
        
        # Build query parts
        query_parts = []
        
        # Handle FROM predicates (support multiple senders with OR)
        if from_predicates:
            if len(from_predicates) == 1 and len(from_predicates[0].senders) == 1:
                # Single sender
                query_parts.append(f"from:{from_predicates[0].senders[0]}")
                if verbose_mode:
                    print(f"GmailClient: Added 'from:{from_predicates[0].senders[0]}' to query")
            else:
                # Multiple senders - combine with OR
                all_senders = []
                for pred in from_predicates:
                    all_senders.extend(pred.senders)
                from_conditions = [f"from:{sender}" for sender in all_senders]
                from_query = " OR ".join(from_conditions)
                query_parts.append(f"({from_query})")
                if verbose_mode:
                    print(f"GmailClient: Added OR from query: '({from_query})'")
        
        # Handle TO predicates (support multiple recipients with OR)
        if to_predicates:
            if len(to_predicates) == 1 and len(to_predicates[0].recipients) == 1:
                # Single recipient
                query_parts.append(f"to:{to_predicates[0].recipients[0]}")
                if verbose_mode:
                    print(f"GmailClient: Added 'to:{to_predicates[0].recipients[0]}' to query")
            else:
                # Multiple recipients - combine with OR
                all_recipients = []
                for pred in to_predicates:
                    all_recipients.extend(pred.recipients)
                to_conditions = [f"to:{recipient}" for recipient in all_recipients]
                to_query = " OR ".join(to_conditions)
                query_parts.append(f"({to_query})")
                if verbose_mode:
                    print(f"GmailClient: Added OR to query: '({to_query})'")
        
        # Handle INVOLVES predicates (convert to from: OR to: queries)
        if involves_predicates:
            all_persons = []
            for pred in involves_predicates:
                all_persons.extend(pred.persons)
            
            # Create conditions for each person: from:person OR to:person
            involves_conditions = []
            for person in all_persons:
                involves_conditions.append(f"from:{person} OR to:{person}")
            
            # Combine all conditions with OR
            involves_query = " OR ".join(involves_conditions)
            query_parts.append(f"({involves_query})")
            if verbose_mode:
                print(f"GmailClient: Added INVOLVES query: '({involves_query})'")
        
        # Handle date predicates (these are ANDed together)
        for pred in date_predicates:
            if pred.__class__.__name__ == 'BEFORE':
                date_str = pred.date_str.replace('-', '/')
                query_parts.append(f"before:{date_str}")
                if verbose_mode:
                    print(f"GmailClient: Added 'before:{date_str}' to query")
            elif pred.__class__.__name__ == 'AFTER':
                date_str = pred.date_str.replace('-', '/')
                query_parts.append(f"after:{date_str}")
                if verbose_mode:
                    print(f"GmailClient: Added 'after:{date_str}' to query")
        
        final_query = ' '.join(query_parts) if query_parts else None
        if verbose_mode:
            print(f"GmailClient: Final query: '{final_query}'")
        return final_query
    
    def _fetch_full_message(self, msg_id: str) -> bytes:
        """Fetch the full message body for a given message ID"""
        if not self.connected:
            self.connect()
        
        try:
            # Get full message
            msg = self.service.users().messages().get(
                userId='me', id=msg_id, format='full'
            ).execute()
            
            # Convert Gmail API format to raw email bytes
            return self._gmail_to_raw_email(msg)
            
        except HttpError as error:
            raise RuntimeError(f"Failed to fetch message {msg_id}: {error}")
    
    def _gmail_to_raw_email(self, msg: dict) -> bytes:
        """Convert Gmail API message format to raw email bytes"""
        try:
            # Add headers
            headers = msg.get('payload', {}).get('headers', [])
            
            # Add body content
            payload = msg.get('payload', {})
            mime_type = payload.get('mimeType', 'unknown')
            
            # Create email message and add headers
            email_msg = email.message.EmailMessage()
            for header in headers:
                email_msg[header['name']] = header['value']
            
            # Add body content based on type
            if mime_type.startswith('multipart/'):
                # For multipart messages, add parts
                self._add_multipart_parts(email_msg, payload)
            else:
                # For single part messages, add body content
                self._add_body_parts(email_msg, payload)
            
            # Convert to bytes
            return email_msg.as_bytes(policy=email.policy.default)
            
        except AttributeError as e:
            if "'list' object has no attribute 'encode'" in str(e):
                # Handle list payload error by creating a minimal email
                print(f"Warning: Gmail message has list payload, creating minimal email")
                print(f"Diagnostic: Payload structure: {self._diagnose_payload_structure(msg)}")
                print("Debug: Detailed part structure:")
                payload = msg.get('payload', {})
                if 'parts' in payload:
                    for i, part in enumerate(payload['parts']):
                        print(f"  Top-level part {i+1}:")
                        self._debug_part_structure(part, 2)
                return self._create_minimal_email_from_gmail(msg)
            else:
                raise
        except Exception as e:
            print(f"Warning: Error converting Gmail message to raw email: {e}")
            return self._create_minimal_email_from_gmail(msg)
    
    def _create_minimal_email_from_gmail(self, msg: dict) -> bytes:
        """Create a minimal email when the original conversion fails"""
        # Extract basic headers
        headers = msg.get('payload', {}).get('headers', [])
        payload = msg.get('payload', {})
        
        # Create email message
        email_msg = email.message.EmailMessage()
        
        # Add headers
        for header in headers:
            email_msg[header['name']] = header['value']
        
        # Check if this is a multipart message
        mime_type = payload.get('mimeType', 'text/plain')
        if mime_type.startswith('multipart/'):
            # Handle multipart by creating parts
            self._create_multipart_from_problematic_payload(email_msg, payload)
        else:
            # Single part - try to extract content
            body_content = self._extract_content_from_problematic_payload(msg)
            email_msg.set_content(body_content)
        
        return email_msg.as_bytes(policy=email.policy.default)
    
    def _create_multipart_from_problematic_payload(self, email_msg: email.message.EmailMessage, payload: dict):
        """Create a multipart email from problematic payload"""
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    part_mime_type = part.get('mimeType', 'text/plain')
                    
                    # Check if this part is itself multipart
                    if part_mime_type.startswith('multipart/') and 'parts' in part:
                        # Handle nested multipart - extract content from nested parts
                        nested_content = self._extract_nested_multipart_content(part)
                        if nested_content:
                            # Create a text part with the extracted content
                            part_msg = email.message.EmailMessage()
                            part_msg.set_content(nested_content)
                            email_msg.attach(part_msg)
                    else:
                        # Regular part
                        part_msg = email.message.EmailMessage()
                        part_content = self._extract_part_content(part)
                        if part_content:
                            part_msg.set_content(part_content)
                        else:
                            part_msg.set_content("[Part content could not be extracted]")
                        
                        # Add the part to the main message
                        email_msg.attach(part_msg)
            else:
                # No parts found, add a placeholder
                email_msg.set_content("[Multipart email with no extractable parts]")
                
        except Exception as e:
            print(f"Warning: Error creating multipart from problematic payload: {e}")
            # Fallback to simple text
            email_msg.set_content("[Multipart email could not be reconstructed]")
    
    def _extract_nested_multipart_content(self, multipart_part: dict) -> str:
        """Extract content from nested multipart parts, preferring text/plain"""
        try:
            if 'parts' not in multipart_part:
                return ""
            
            # First, try to find text/plain content
            for part in multipart_part['parts']:
                mime_type = part.get('mimeType', 'text/plain')
                if mime_type == 'text/plain':
                    content = self._extract_part_content(part)
                    if content:
                        return content
            
            # If no text/plain found, try text/html
            for part in multipart_part['parts']:
                mime_type = part.get('mimeType', 'text/html')
                if mime_type == 'text/html':
                    content = self._extract_part_content(part)
                    if content:
                        return content
            
            # If still nothing, try any text content
            for part in multipart_part['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type.startswith('text/'):
                    content = self._extract_part_content(part)
                    if content:
                        return content
            
            return ""
            
        except Exception as e:
            print(f"Warning: Error extracting nested multipart content: {e}")
            return ""
    
    def _extract_content_from_problematic_payload(self, msg: dict) -> str:
        """Try to extract useful content from a problematic Gmail payload"""
        try:
            payload = msg.get('payload', {})
            
            # Strategy 1: Try to get content from body.data if it exists
            if 'body' in payload and payload['body'].get('data'):
                try:
                    content = base64.urlsafe_b64decode(payload['body']['data'])
                    if isinstance(content, list):
                        # Try different ways to convert list to string
                        return self._convert_list_to_string(content)
                    elif isinstance(content, bytes):
                        return content.decode('utf-8', errors='replace')
                    else:
                        return str(content)
                except Exception as e:
                    pass
            
            # Strategy 2: Try to extract from parts if it's multipart
            if 'parts' in payload:
                parts_content = []
                for part in payload['parts']:
                    part_content = self._extract_part_content(part)
                    if part_content:
                        parts_content.append(part_content)
                
                if parts_content:
                    return '\n\n---\n\n'.join(parts_content)
            
            # Strategy 3: Try to get any text from the payload structure
            return self._extract_text_from_payload_structure(payload)
            
        except Exception as e:
            return f"[Content extraction failed: {str(e)}]"
    
    def _convert_list_to_string(self, content_list: list) -> str:
        """Convert a list to a string using various strategies"""
        try:
            # Strategy 1: Join with newlines
            if all(isinstance(item, str) for item in content_list):
                return '\n'.join(content_list)
            
            # Strategy 2: Join with spaces
            if all(isinstance(item, (str, int, float)) for item in content_list):
                return ' '.join(str(item) for item in content_list)
            
            # Strategy 3: Format each item with %s
            formatted_items = []
            for item in content_list:
                try:
                    formatted_items.append("%s" % item)
                except:
                    formatted_items.append(str(item))
            return '\n'.join(formatted_items)
            
        except Exception as e:
            return f"[List conversion failed: {str(e)}]"
    
    def _extract_part_content(self, part: dict) -> str:
        """Extract content from a single part"""
        try:
            if part.get('body', {}).get('data'):
                data = part['body']['data']
                
                # If data is already a string, use it directly
                if isinstance(data, str):
                    try:
                        content = base64.urlsafe_b64decode(data)
                        if isinstance(content, list):
                            return self._convert_list_to_string(content)
                        elif isinstance(content, bytes):
                            return content.decode('utf-8', errors='replace')
                        else:
                            return str(content)
                    except Exception as decode_error:
                        # If base64 decode fails, try using the string directly
                        return data
                else:
                    # Handle non-string data
                    if isinstance(data, list):
                        return self._convert_list_to_string(data)
                    else:
                        return str(data)
            
            # Try nested parts
            if 'parts' in part:
                nested_content = []
                for nested_part in part['parts']:
                    nested_text = self._extract_part_content(nested_part)
                    if nested_text:
                        nested_content.append(nested_text)
                return '\n'.join(nested_content)
            
            return ""
            
        except Exception as e:
            return f"[Part extraction failed: {str(e)}]"
    
    def _debug_part_structure(self, part: dict, depth: int = 0):
        """Debug helper to print part structure"""
        indent = "  " * depth
        mime_type = part.get('mimeType', 'unknown')
        has_data = 'body' in part and part['body'].get('data')
        has_parts = 'parts' in part
        
        print(f"{indent}Part: {mime_type} | has_data: {has_data} | has_parts: {has_parts}")
        
        if has_data:
            data = part['body']['data']
            print(f"{indent}  Data type: {type(data)}")
            if isinstance(data, str):
                print(f"{indent}  Data length: {len(data)}")
                print(f"{indent}  Data preview: {data[:100]}...")
        
        if has_parts:
            print(f"{indent}  Nested parts count: {len(part['parts'])}")
            for i, nested_part in enumerate(part['parts']):
                print(f"{indent}  Nested part {i+1}:")
                self._debug_part_structure(nested_part, depth + 2)
    
    def _extract_text_from_payload_structure(self, payload: dict) -> str:
        """Extract any text content from the payload structure"""
        try:
            # Look for any text-like fields in the payload
            text_parts = []
            
            # Check for body data
            if 'body' in payload and payload['body'].get('data'):
                text_parts.append("Body data present but could not decode")
            
            # Check for parts
            if 'parts' in payload:
                text_parts.append(f"Multipart message with {len(payload['parts'])} parts")
                
                # Try to describe each part
                for i, part in enumerate(payload['parts']):
                    mime_type = part.get('mimeType', 'unknown')
                    has_data = 'body' in part and part['body'].get('data')
                    text_parts.append(f"Part {i+1}: {mime_type} {'(has data)' if has_data else '(no data)'}")
            
            # Check for headers
            if 'headers' in payload:
                text_parts.append("Headers present")
            
            if text_parts:
                return '\n'.join(text_parts)
            else:
                return "[No extractable content found]"
                
        except Exception as e:
            return f"[Structure extraction failed: {str(e)}]"
    
    def _diagnose_payload_structure(self, msg: dict) -> str:
        """Create a diagnostic summary of the problematic payload structure"""
        try:
            payload = msg.get('payload', {})
            diagnosis = []
            
            # Basic structure
            diagnosis.append(f"Payload keys: {list(payload.keys())}")
            
            # Headers info
            headers = payload.get('headers', [])
            diagnosis.append(f"Headers count: {len(headers)}")
            if headers:
                header_names = [h.get('name', 'unknown') for h in headers[:5]]  # First 5 headers
                diagnosis.append(f"Header names: {header_names}")
            
            # Body info
            if 'body' in payload:
                body = payload['body']
                diagnosis.append(f"Body keys: {list(body.keys())}")
                if 'data' in body:
                    data = body['data']
                    diagnosis.append(f"Body data type: {type(data)}")
                    if isinstance(data, str):
                        diagnosis.append(f"Body data length: {len(data)}")
                        diagnosis.append(f"Body data preview: {data[:100]}...")
            
            # Parts info
            if 'parts' in payload:
                parts = payload['parts']
                diagnosis.append(f"Parts count: {len(parts)}")
                for i, part in enumerate(parts[:3]):  # First 3 parts
                    part_keys = list(part.keys())
                    mime_type = part.get('mimeType', 'unknown')
                    diagnosis.append(f"Part {i+1} keys: {part_keys}, mimeType: {mime_type}")
                    
                    if 'body' in part and part['body'].get('data'):
                        data = part['body']['data']
                        diagnosis.append(f"Part {i+1} data type: {type(data)}")
                        if isinstance(data, str):
                            diagnosis.append(f"Part {i+1} data length: {len(data)}")
            
            return ' | '.join(diagnosis)
            
        except Exception as e:
            return f"Diagnosis failed: {str(e)}"
    
    def _add_body_parts(self, email_msg: email.message.EmailMessage, payload: dict):
        """Add body parts to single-part email message"""
        if 'body' in payload and payload['body'].get('data'):
            # Single part message
            try:
                content = base64.urlsafe_b64decode(payload['body']['data'])
                # Ensure content is a string, not a list
                if isinstance(content, list):
                    content = ' '.join(str(item) for item in content)
                elif not isinstance(content, (str, bytes)):
                    content = str(content)
                
                content_type = payload.get('mimeType', 'text/plain')
                if '/' in content_type:
                    maintype, subtype = content_type.split('/', 1)
                    email_msg.set_content(content, maintype=maintype, subtype=subtype)
                else:
                    email_msg.set_content(content, maintype=content_type)
            except Exception as e:
                print(f"Warning: Error adding body part: {e}")
                email_msg.set_content("[Body content could not be parsed]")
    
    def _add_multipart_parts(self, email_msg: email.message.EmailMessage, payload: dict):
        """Add parts to multipart email message"""
        if 'parts' in payload:
            for part in payload['parts']:
                try:
                    part_msg = email.message.EmailMessage()
                    part_mime_type = part.get('mimeType', 'text/plain')
                    
                    if part.get('body', {}).get('data'):
                        # Part has content
                        content = base64.urlsafe_b64decode(part['body']['data'])
                        # Ensure content is a string, not a list
                        if isinstance(content, list):
                            content = ' '.join(str(item) for item in content)
                        elif not isinstance(content, (str, bytes)):
                            content = str(content)
                        
                        if '/' in part_mime_type:
                            maintype, subtype = part_mime_type.split('/', 1)
                            part_msg.set_content(content, maintype=maintype, subtype=subtype)
                        else:
                            part_msg.set_content(content, maintype=part_mime_type)
                    elif part.get('parts'):
                        # Part has nested parts - recurse
                        self._add_multipart_parts(part_msg, part)
                    
                    # Add the part to the main message
                    email_msg.attach(part_msg)
                except Exception as e:
                    print(f"Warning: Error adding multipart part: {e}")
                    # Create a placeholder part
                    placeholder_msg = email.message.EmailMessage()
                    placeholder_msg.set_content("[Part content could not be parsed]")
                    email_msg.attach(placeholder_msg)
    

    
    def delete_message(self, msg_id: str) -> bool:
        """Delete a message by ID"""
        if not self.connected:
            self.connect()
        
        if not self.allow_delete:
            print(f"Skipping deletion of message {msg_id} due to allow_delete=False")
            return False

        try:
            result = self.service.users().messages().delete(userId='me', id=msg_id).execute()
            return True
            
        except HttpError as error:
            print(f"Error deleting message {msg_id}: {error}")
            return False
    
    def check_scopes(self):
        """Check what scopes the current token has"""
        if not self.connected:
            self.connect()
        
        # Get credentials from the _get_credentials method
        creds = self._get_credentials()
        print(f"Current scopes: {creds.scopes}")
        print(f"Token valid: {creds.valid}")
        print(f"Token expired: {creds.expired}")
        return creds.scopes
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()





 