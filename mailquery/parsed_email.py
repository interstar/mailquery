import email
from email.policy import default
from typing import Callable, Optional, List


class ParsedEmail:
    def __init__(self, uid: str, envelope: dict, fetch_raw_func: Callable[[], bytes]):
        self.uid = uid
        self.envelope = envelope  # header-only info
        self._fetch_raw = fetch_raw_func
        self._body = None
        self._html = None
        self._attachments = None  # Cache for attachments
        self.deleted_on_server = False  # Track if this email has been deleted on the server
        self.extra_attributes = {}  # Store computed attributes from add_attribute filters
        
        # Parse sender components
        self._sender_name = None
        self._sender_email = None
        self._parse_sender_components()
    
    def _parse_sender_components(self):
        """Parse sender into name and email components"""
        sender = self.envelope.get('sender', '')
        if not sender:
            self._sender_name = ""
            self._sender_email = ""
            return
            
        if '<' in sender and '>' in sender:
            # Format: "Name <email@domain.com>"
            parts = sender.split('<')
            self._sender_name = parts[0].strip()
            self._sender_email = parts[1].rstrip('>').strip()
        else:
            # Format: "email@domain.com" or just "Name"
            if '@' in sender:
                self._sender_name = ""
                self._sender_email = sender.strip()
            else:
                self._sender_name = sender.strip()
                self._sender_email = ""
    
    @property
    def sender_name(self) -> str:
        """Get the sender name part"""
        return self._sender_name
    
    @property
    def sender_email(self) -> str:
        """Get the sender email part"""
        return self._sender_email

    def get_plain_text_body(self) -> str:
        """Get plain text body, extracting from HTML if needed"""
        if self._body is None:
            raw = self._fetch_raw()
            parsed = parse_full_email(raw)
            self._body = parsed["body"]
            self._html = parsed.get("html")
        return self._body

    def get_formatted_body(self) -> str:
        """Get formatted body (HTML if available, otherwise plain text)"""
        html = self.get_html()
        if html:
            return html
        return self.get_plain_text_body()

    def get_html(self) -> Optional[str]:
        """Get raw HTML content if available"""
        if self._body is None:
            raw = self._fetch_raw()
            parsed = parse_full_email(raw)
            self._body = parsed["body"]
            self._html = parsed.get("html")
        return self._html

    def has_attachments(self) -> bool:
        """Check if the email has any attachments"""
        attachments = self.get_attachments()
        return len(attachments) > 0

    def get_attachments(self) -> List[dict]:
        """
        Get list of attachments in the email.
        
        Returns:
            List of attachment dictionaries with keys:
            - filename: str (or None if no filename)
            - content_type: str (e.g., 'image/jpeg', 'application/pdf')
            - size: int (size in bytes)
            - content: bytes (the actual attachment data)
        """
        if self._attachments is None:
            self._attachments = self._extract_attachments()
        return self._attachments

    def _extract_attachments(self) -> List[dict]:
        """Extract attachments from the email"""
        try:
            import email
            from email.policy import default
            
            raw = self._fetch_raw()
            msg = email.message_from_bytes(raw, policy=default)
            
            attachments = []
            
            for part in msg.walk():
                # Skip the main message parts
                if part.get_content_maintype() == 'multipart':
                    continue
                
                # Check if this part is an attachment
                filename = part.get_filename()
                content_type = part.get_content_type()
                
                # Consider it an attachment if:
                # 1. It has a filename, OR
                # 2. It's not text/plain or text/html, OR
                # 3. It has Content-Disposition: attachment
                is_attachment = (
                    filename is not None or
                    not content_type.startswith('text/') or
                    part.get('Content-Disposition', '').startswith('attachment')
                )
                
                if is_attachment:
                    try:
                        content = part.get_payload(decode=True)
                        if content:
                            attachments.append({
                                'filename': filename,
                                'content_type': content_type,
                                'size': len(content),
                                'content': content
                            })
                    except Exception as e:
                        # Skip attachments that can't be decoded
                        continue
            
            return attachments
            
        except Exception as e:
            # If extraction fails, return empty list
            return []

    def __getitem__(self, key):
        if key in self.envelope:
            return self.envelope[key]
        if key == "body":
            return self.get_plain_text_body()
        if key == "html":
            return self.get_html()
        raise KeyError(key)

    def cleaned_sender(self) -> str:
        """Return a cleaned, human-readable sender name"""
        sender = self.envelope.get('sender', '')
        if not sender:
            return ''
            
        if '<' in sender:
            # Extract name from "Name <email@example.com>"
            name_part = sender.split('<')[0].strip()
            if name_part:
                return name_part
            else:
                # Just show email if no name
                return sender.split('<')[1].split('>')[0]
        
        return sender

    def __repr__(self):
        return f"<ParsedEmail uid={self.uid} from={self.envelope.get('sender', '')!r} subject={self.envelope.get('subject', '')!r}>"


def parse_envelope(raw: bytes) -> dict:
    """Parse email headers only - fast operation"""
    msg = email.message_from_bytes(raw, policy=default)
    return {
        "sender": msg.get("From"),
        "from": msg.get("From"),  # Alias for consistency
        "sender_header": msg.get("Sender"),  # Separate Sender header
        "subject": msg.get("Subject"),
        "date": msg.get("Date"),
        "message_id": msg.get("Message-ID"),
        "reply_to": msg.get("Reply-To"),
        "to": msg.get("To"),
        "cc": msg.get("Cc"),
        "bcc": msg.get("Bcc"),
    }


def parse_full_email(raw: bytes) -> dict:
    """Parse full email including body - slower operation"""
    msg = email.message_from_bytes(raw, policy=default)
    body_parts = []
    html = None
    
    def safe_get_content(part):
        """Safely get content with encoding error handling"""
        try:
            return part.get_content()
        except UnicodeDecodeError:
            # Try to decode with different encodings
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode('utf-8', errors='replace')
            except:
                pass
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode('latin-1', errors='replace')
            except:
                pass
            return "[Encoding error - content not readable]"
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                content = safe_get_content(part)
                if content and content.strip():
                    body_parts.append(content)
            elif content_type == "text/html":
                html = safe_get_content(part)
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            content = safe_get_content(msg)
            if content and content.strip():
                body_parts.append(content)
        elif content_type == "text/html":
            html = safe_get_content(msg)
    
    # Join all body parts
    body = "\n\n".join(body_parts) if body_parts else ""

    # If no plain text body but we have HTML, extract text from HTML using regex
    if not body and html:
        import re
        # Remove script and style tags and their content
        body = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
        # Remove other HTML tags but preserve some structure
        body = re.sub(r'<br\s*/?>', '\n', body, flags=re.IGNORECASE)
        body = re.sub(r'</p>', '\n\n', body, flags=re.IGNORECASE)
        body = re.sub(r'</div>', '\n', body, flags=re.IGNORECASE)
        body = re.sub(r'</h[1-6]>', '\n\n', body, flags=re.IGNORECASE)
        body = re.sub(r'<[^>]+>', '', body)
        # Clean up whitespace and normalize
        body = re.sub(r'\n\s*\n\s*\n', '\n\n', body)  # Remove excessive blank lines
        body = re.sub(r'[ \t]+', ' ', body)  # Normalize spaces
        body = re.sub(r'\n +', '\n', body)  # Remove leading spaces on lines
        body = body.strip()

    return {
        "body": body,
        "html": html,
        "message_id": msg.get("Message-ID"),
    }
