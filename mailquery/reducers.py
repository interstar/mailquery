"""
Reducer classes for the reduce_all() functionality.

Reducers encapsulate the logic for processing a collection of emails
and producing a single result.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Set
from .parsed_email import ParsedEmail


class Reducer(ABC):
    """Base class for email reducers"""
    
    @abstractmethod
    def init_value(self):
        """Initialize the reducer's internal state"""
        pass
    
    def fold(self, email: ParsedEmail):
        """Fold the next email into the accumulator with error handling"""
        try:
            self._fold(email)
        except Exception as e:
            print(f"Warning: Could not process email {email.uid} in reducer {self.__class__.__name__}: {e}")
            # Subclasses can override _handle_error if they want custom error handling
            self._handle_error(email, e)
    
    @abstractmethod
    def _fold(self, email: ParsedEmail):
        """Internal fold method - subclasses implement this"""
        pass
    
    def _handle_error(self, email: ParsedEmail, error: Exception):
        """Handle errors during folding - subclasses can override for custom error handling"""
        # Default implementation does nothing - just skip the problematic email
        pass
    
    @abstractmethod
    def final(self) -> Any:
        """Return the final result"""
        pass


class CountReducer(Reducer):
    """Count the total number of emails"""
    
    def init_value(self):
        self.count = 0
    
    def _fold(self, email: ParsedEmail):
        self.count += 1
    
    def final(self) -> int:
        return self.count


class SubjectConcatenator(Reducer):
    """Concatenate all email subjects into a single string"""
    
    def init_value(self):
        self.subjects = []
    
    def _fold(self, email: ParsedEmail):
        self.subjects.append(email['subject'])
    
    def final(self) -> str:
        return " | ".join(self.subjects)


class SenderCollector(Reducer):
    """Collect all unique sender email addresses"""
    
    def init_value(self):
        self.senders: Set[str] = set()
    
    def _fold(self, email: ParsedEmail):
        self.senders.add(email.envelope['from'])
    
    def final(self) -> List[str]:
        return list(self.senders)


class WordCountReducer(Reducer):
    """Count total words across all email bodies"""
    
    def init_value(self):
        self.word_count = 0
    
    def _fold(self, email: ParsedEmail):
        body = email.get_plain_text_body()
        if body:
            self.word_count += len(body.split())
    
    def final(self) -> int:
        return self.word_count


class LongestSubjectFinder(Reducer):
    """Find the email with the longest subject line"""
    
    def init_value(self):
        self.longest_email = None
        self.max_length = 0
    
    def _fold(self, email: ParsedEmail):
        subject_length = len(email['subject'])
        if subject_length > self.max_length:
            self.max_length = subject_length
            self.longest_email = email
    
    def final(self) -> ParsedEmail:
        return self.longest_email


class EmailStatistics(Reducer):
    """Build comprehensive statistics about the email collection"""
    
    def init_value(self):
        self.stats = {
            'total_emails': 0,
            'senders': set(),
            'subjects': [],
            'has_html': 0,
            'total_subject_length': 0,
            'longest_subject': '',
            'sender_counts': {}
        }
    
    def _fold(self, email: ParsedEmail):
        self.stats['total_emails'] += 1
        self.stats['senders'].add(email.envelope['from'])
        self.stats['subjects'].append(email['subject'])
        self.stats['total_subject_length'] += len(email['subject'])
        
        if len(email['subject']) > len(self.stats['longest_subject']):
            self.stats['longest_subject'] = email['subject']
        
        if email.get_html():
            self.stats['has_html'] += 1
        
        sender = email.envelope['from']
        self.stats['sender_counts'][sender] = self.stats['sender_counts'].get(sender, 0) + 1
    
    def final(self) -> Dict[str, Any]:
        # Convert set to list for JSON serialization
        result = self.stats.copy()
        result['senders'] = list(result['senders'])
        return result


class HTMLPageBuilder(Reducer):
    """Build an HTML page from all emails"""
    
    def init_value(self):
        self.html_parts = []
        self.html_parts.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Email Collection</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .email { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
                .header { background-color: #f5f5f5; padding: 10px; margin-bottom: 10px; }
                .subject { font-weight: bold; color: #333; }
                .sender { color: #666; }
                .date { color: #999; font-size: 0.9em; }
                .body { margin-top: 10px; line-height: 1.5; }
            </style>
        </head>
        <body>
            <h1>Email Collection</h1>
        """)
    
    def _fold(self, email: ParsedEmail):
        sender = email.cleaned_sender()
        subject = email['subject'] or 'No Subject'
        date = email['date'] or 'No Date'
        
        # Get formatted body (HTML if available, otherwise plain text)
        body = email.get_formatted_body() or ''
        
        # Check for attachments
        has_attachments = email.has_attachments()
        attachments = email.get_attachments() if has_attachments else []
        
        # If no body but has attachments, create attachment info
        if not body and has_attachments:
            body = self._format_attachments_info(attachments)
        elif not body:
            body = self._generate_detailed_diagnostics(email)
        
        # Determine if body is HTML or plain text
        html_content = email.get_html()
        is_html_body = html_content and body == html_content
        
        # Escape HTML in text content (but not if body is already HTML)
        import html
        subject = html.escape(subject)
        sender = html.escape(sender)
        date = html.escape(date)
        
        if is_html_body:
            # Body is HTML, don't escape it
            body_class = "body html-content"
        else:
            # Body is plain text, escape it
            body = html.escape(body)
            body_class = "body text-content"
        
        email_html = f"""
            <div class="email">
                <div class="header">
                    <div class="subject">{subject}</div>
                    <div class="sender">From: {sender}</div>
                    <div class="date">Date: {date}</div>
                </div>
                <div class="{body_class}">{body}</div>
            </div>
        """
        self.html_parts.append(email_html)
    
    def _format_attachments_info(self, attachments: List[dict]) -> str:
        """Format attachment information for display"""
        if not attachments:
            # Enhanced diagnostics when no body and no attachments
            return self._generate_detailed_diagnostics()
        
        lines = ["No Body. But attachments were found:"]
        for i, attachment in enumerate(attachments, 1):
            filename = attachment.get('filename', 'Unnamed attachment')
            content_type = attachment.get('content_type', 'unknown')
            size = attachment.get('size', 0)
            
            # Format size nicely
            if size < 1024:
                size_str = f"{size} bytes"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            
            lines.append(f"{i}. {filename} ({content_type}, {size_str})")
        
        return '\n'.join(lines)
    
    def _generate_detailed_diagnostics(self, email: ParsedEmail) -> str:
        """Generate detailed diagnostics about the email structure when no body/attachments found"""
        try:
            diagnostics = ["=== EMAIL DIAGNOSTICS ==="]
            diagnostics.append(f"Email UID: {email.uid}")
            diagnostics.append(f"Subject: {email['subject'] if 'subject' in email.envelope else 'No Subject'}")
            diagnostics.append(f"From: {email['from'] if 'from' in email.envelope else 'No From'}")
            diagnostics.append(f"Date: {email['date'] if 'date' in email.envelope else 'No Date'}")
            diagnostics.append("")
            
            # Try to analyze the raw email structure and extract content
            try:
                raw_bytes = email._fetch_raw()
                if isinstance(raw_bytes, bytes):
                    diagnostics.append(f"Raw Email Size: {len(raw_bytes)} bytes")
                    
                    # Try to parse the raw email
                    import email as email_lib
                    from email.policy import default
                    
                    msg = email_lib.message_from_bytes(raw_bytes, policy=default)
                    diagnostics.append(f"Parsed Message Type: {type(msg).__name__}")
                    diagnostics.append(f"Is Multipart: {msg.is_multipart()}")
                    diagnostics.append("")
                    
                    # Extract and display all available content
                    diagnostics.append("=== CONTENT ANALYSIS ===")
                    
                    if msg.is_multipart():
                        diagnostics.append("Multipart email structure:")
                        part_num = 0
                        for part in msg.walk():
                            part_num += 1
                            content_type = part.get_content_type()
                            content_disposition = part.get('Content-Disposition', '')
                            filename = part.get_filename()
                            
                            diagnostics.append(f"\nPart {part_num}:")
                            diagnostics.append(f"  Content-Type: {content_type}")
                            diagnostics.append(f"  Content-Disposition: {content_disposition}")
                            if filename:
                                diagnostics.append(f"  Filename: {filename}")
                            
                            # Try to extract content based on type
                            try:
                                if content_type == "text/plain":
                                    content = part.get_content()
                                    if content:
                                        # Truncate long content for display
                                        display_content = content[:500] + "..." if len(content) > 500 else content
                                        diagnostics.append(f"  Text Content ({len(content)} chars):")
                                        diagnostics.append(f"    {repr(display_content)}")
                                    else:
                                        diagnostics.append("  Text Content: [Empty]")
                                        
                                elif content_type == "text/html":
                                    content = part.get_content()
                                    if content:
                                        # Truncate long HTML content
                                        display_content = content[:300] + "..." if len(content) > 300 else content
                                        diagnostics.append(f"  HTML Content ({len(content)} chars):")
                                        diagnostics.append(f"    {repr(display_content)}")
                                    else:
                                        diagnostics.append("  HTML Content: [Empty]")
                                        
                                elif content_type.startswith('image/'):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        diagnostics.append(f"  Image Content: {len(payload)} bytes")
                                    else:
                                        diagnostics.append("  Image Content: [Empty]")
                                        
                                elif content_type.startswith('application/'):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        diagnostics.append(f"  Application Content: {len(payload)} bytes")
                                        # Try to show first few bytes as hex
                                        hex_preview = payload[:20].hex()
                                        diagnostics.append(f"  Hex Preview: {hex_preview}")
                                    else:
                                        diagnostics.append("  Application Content: [Empty]")
                                        
                                else:
                                    # Try to get any content
                                    try:
                                        content = part.get_content()
                                        if content:
                                            diagnostics.append(f"  Other Content ({len(content)} chars): {repr(str(content)[:100])}")
                                        else:
                                            diagnostics.append("  Other Content: [Empty]")
                                    except:
                                        # Try raw payload
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            diagnostics.append(f"  Raw Payload: {len(payload)} bytes")
                                        else:
                                            diagnostics.append("  Raw Payload: [Empty]")
                                            
                            except Exception as e:
                                diagnostics.append(f"  Error extracting content: {str(e)}")
                                
                    else:
                        # Single part email
                        content_type = msg.get_content_type()
                        diagnostics.append(f"Single part email:")
                        diagnostics.append(f"Content-Type: {content_type}")
                        
                        try:
                            if content_type == "text/plain":
                                content = msg.get_content()
                                if content:
                                    display_content = content[:500] + "..." if len(content) > 500 else content
                                    diagnostics.append(f"Text Content ({len(content)} chars):")
                                    diagnostics.append(f"  {repr(display_content)}")
                                else:
                                    diagnostics.append("Text Content: [Empty]")
                                    
                            elif content_type == "text/html":
                                content = msg.get_content()
                                if content:
                                    display_content = content[:300] + "..." if len(content) > 300 else content
                                    diagnostics.append(f"HTML Content ({len(content)} chars):")
                                    diagnostics.append(f"  {repr(display_content)}")
                                else:
                                    diagnostics.append("HTML Content: [Empty]")
                                    
                            else:
                                # Try to get any content
                                try:
                                    content = msg.get_content()
                                    if content:
                                        diagnostics.append(f"Other Content ({len(content)} chars): {repr(str(content)[:100])}")
                                    else:
                                        diagnostics.append("Other Content: [Empty]")
                                except:
                                    # Try raw payload
                                    payload = msg.get_payload(decode=True)
                                    if payload:
                                        diagnostics.append(f"Raw Payload: {len(payload)} bytes")
                                    else:
                                        diagnostics.append("Raw Payload: [Empty]")
                                        
                        except Exception as e:
                            diagnostics.append(f"Error extracting content: {str(e)}")
                    
                    # Show all headers
                    diagnostics.append("\n=== ALL HEADERS ===")
                    for header, value in msg.items():
                        diagnostics.append(f"{header}: {value}")
                    
                else:
                    diagnostics.append(f"Raw content is not bytes: {type(raw_bytes)}")
                    if hasattr(raw_bytes, '__len__'):
                        diagnostics.append(f"Raw content length: {len(raw_bytes)}")
                    
            except Exception as e:
                diagnostics.append(f"Error analyzing raw email: {str(e)}")
            
            return '\n'.join(diagnostics)
        except Exception as e:
            return f"Diagnostic generation failed: {str(e)}"
    
    def _handle_error(self, email: ParsedEmail, error: Exception):
        """Try to recover from common errors, fall back to error placeholder"""
        try:
            # Try to get basic email info even if body fails
            sender = email.cleaned_sender()
            subject = email['subject'] or 'No Subject'
            date = email['date'] or 'No Date'
            
            # Try to get body with fallback strategies
            body = self._try_get_body_with_recovery(email, error)
            
            # Escape HTML in text content
            import html
            subject = html.escape(subject)
            sender = html.escape(sender)
            date = html.escape(date)
            body = html.escape(body)
            
            email_html = f"""
                <div class="email">
                    <div class="header">
                        <div class="subject">{subject}</div>
                        <div class="sender">From: {sender}</div>
                        <div class="date">Date: {date}</div>
                    </div>
                    <div class="body">{body}</div>
                </div>
            """
            self.html_parts.append(email_html)
            
        except Exception as recovery_error:
            # If recovery also fails, fall back to error placeholder
            error_html = f"""
                <div class="email">
                    <div class="header">
                        <div class="subject">[Error processing email]</div>
                        <div class="sender">From: [Unknown]</div>
                        <div class="date">Date: [Unknown]</div>
                    </div>
                    <div class="body">Error processing email {email.uid}: {str(error)}<br>Recovery also failed: {str(recovery_error)}</div>
                </div>
            """
            self.html_parts.append(error_html)
    
    def _try_get_body_with_recovery(self, email: ParsedEmail, original_error: Exception) -> str:
        """Try various strategies to get email body content"""
        # Strategy 1: Try normal get_plain_text_body()
        try:
            body = email.get_plain_text_body()
            if body:
                return body
        except Exception as e:
            pass
        
        # Strategy 2: Try to handle list payload specifically
        if "'list' object has no attribute 'encode'" in str(original_error):
            try:
                # Try to access the raw message and extract text content
                import email as email_lib
                from email.policy import default
                
                # Get the raw message bytes
                raw_bytes = email._fetch_raw()
                if isinstance(raw_bytes, bytes):
                    # Parse the email
                    msg = email_lib.message_from_bytes(raw_bytes, policy=default)
                    
                    # Try to extract text content
                    text_parts = []
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                content = part.get_content()
                                if content:
                                    text_parts.append(content)
                    else:
                        if msg.get_content_type() == "text/plain":
                            content = msg.get_content()
                            if content:
                                text_parts.append(content)
                    
                    if text_parts:
                        return ' '.join(text_parts)
                    else:
                        return '[Email has no text content]'
                else:
                    return f'[Unexpected raw content type: {type(raw_bytes)}]'
                    
            except Exception as e:
                return f'[List payload recovery failed: {str(e)}]'
        
        # Strategy 3: Fallback
        return f'[Body unavailable: {str(original_error)}]'
    
    def final(self) -> str:
        self.html_parts.append("</body></html>")
        return "\n".join(self.html_parts)


class TextDocumentBuilder(Reducer):
    """Build a plain text document from all emails"""
    
    def init_value(self):
        self.text_parts = []
        self.text_parts.append("EMAIL COLLECTION\n")
        self.text_parts.append("=" * 50 + "\n\n")
    
    def _fold(self, email: ParsedEmail):
        sender = email.cleaned_sender()
        subject = email['subject'] or 'No Subject'
        date = email['date'] or 'No Date'
        body = email.get_plain_text_body() or 'No Body'
        
        email_text = f"""
From: {sender}
Subject: {subject}
Date: {date}
{'-' * 40}
{body}

"""
        self.text_parts.append(email_text)
    
    def _handle_error(self, email: ParsedEmail, error: Exception):
        """Add a placeholder for problematic emails"""
        error_text = f"""
From: [Error processing email]
Subject: [Error processing email]
Date: [Unknown]
{'-' * 40}
Error processing email {email.uid}: {str(error)}

"""
        self.text_parts.append(error_text)
    
    def final(self) -> str:
        return "".join(self.text_parts)


class AISummaryReducer(Reducer):
    """Prepare emails for AI summarization (returns structured data)"""
    
    def init_value(self):
        self.emails_for_ai = []
    
    def _fold(self, email: ParsedEmail):
        body = email.get_plain_text_body() or 'No Body'
        
        # Add attachment information
        attachments = email.get_attachments()
        attachment_info = []
        for attachment in attachments:
            attachment_info.append({
                'filename': attachment.get('filename', 'Unnamed'),
                'content_type': attachment.get('content_type', 'unknown'),
                'size': attachment.get('size', 0)
            })
        
        email_data = {
            'sender': email.envelope.get('from', 'Unknown'),
            'subject': email['subject'] or 'No Subject',
            'date': email['date'] or 'No Date',
            'body': body,
            'attachments': attachment_info,
            'uid': email.uid
        }
        self.emails_for_ai.append(email_data)
    
    def _handle_error(self, email: ParsedEmail, error: Exception):
        """Add error data for problematic emails"""
        error_data = {
            'sender': 'Error processing email',
            'subject': 'Error processing email',
            'date': 'Unknown',
            'body': f'Error processing email {email.uid}: {str(error)}',
            'attachments': [],
            'uid': email.uid
        }
        self.emails_for_ai.append(error_data)
    
    def final(self) -> List[Dict[str, Any]]:
        return self.emails_for_ai


class AttachmentAnalyzer(Reducer):
    """Analyze attachments across all emails"""
    
    def init_value(self):
        self.attachment_stats = {
            'total_emails_with_attachments': 0,
            'total_attachments': 0,
            'attachment_types': {},
            'largest_attachment': None,
            'attachment_sizes': []
        }
    
    def _fold(self, email: ParsedEmail):
        if email.has_attachments():
            self.attachment_stats['total_emails_with_attachments'] += 1
            attachments = email.get_attachments()
            
            for attachment in attachments:
                self.attachment_stats['total_attachments'] += 1
                
                # Track content types
                content_type = attachment.get('content_type', 'unknown')
                self.attachment_stats['attachment_types'][content_type] = \
                    self.attachment_stats['attachment_types'].get(content_type, 0) + 1
                
                # Track sizes
                size = attachment.get('size', 0)
                self.attachment_stats['attachment_sizes'].append(size)
                
                # Track largest attachment
                if (self.attachment_stats['largest_attachment'] is None or 
                    size > self.attachment_stats['largest_attachment']['size']):
                    self.attachment_stats['largest_attachment'] = {
                        'filename': attachment.get('filename', 'Unnamed'),
                        'content_type': content_type,
                        'size': size,
                        'email_uid': email.uid
                    }
    
    def final(self) -> Dict[str, Any]:
        # Calculate average size
        sizes = self.attachment_stats['attachment_sizes']
        if sizes:
            self.attachment_stats['average_size'] = sum(sizes) / len(sizes)
            self.attachment_stats['total_size'] = sum(sizes)
        else:
            self.attachment_stats['average_size'] = 0
            self.attachment_stats['total_size'] = 0
        
        return self.attachment_stats 