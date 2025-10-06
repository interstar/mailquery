from abc import ABC, abstractmethod
import sqlite3
import os
import base64
from typing import Optional
from .parsed_email import ParsedEmail


class StorageBackend(ABC):
    """Abstract base class for email storage backends"""
    
    def __init__(self, attachment_storage_path: str = None):
        """
        Initialize storage backend
        
        Args:
            attachment_storage_path: Optional path for storing attachments separately.
                                   If None, attachments are embedded in the email format.
        """
        self.attachment_storage_path = attachment_storage_path
        if attachment_storage_path:
            os.makedirs(attachment_storage_path, exist_ok=True)
    
    def setup(self, mailbox):
        """
        Setup the storage backend with information from the mailbox.
        Called by Mailbox.store_local() before storing emails.
        
        Args:
            mailbox: The mailbox object that will be storing emails
        """
        # Default implementation does nothing
        # Subclasses can override to use mailbox._extra_attributes
        pass
    
    def _store_attachments(self, email: ParsedEmail) -> dict:
        """
        Store attachments and return metadata about where they were stored.
        
        Returns:
            dict with attachment metadata for embedding in email storage
        """
        attachments = email.get_attachments()
        if not attachments:
            return {}
        
        attachment_metadata = {}
        
        for i, attachment in enumerate(attachments):
            filename = attachment.get('filename', f'attachment_{i}')
            content_type = attachment.get('content_type', 'application/octet-stream')
            content = attachment.get('content', b'')
            
            if not content:
                continue
            
            # Clean filename for filesystem
            import re
            safe_filename = re.sub(r'[^\w\-_.]', '_', filename)
            
            if self.attachment_storage_path:
                # Store attachment as separate file
                import hashlib
                content_hash = hashlib.md5(content).hexdigest()
                file_extension = self._get_extension_from_content_type(content_type)
                attachment_filename = f"{content_hash}{file_extension}"
                attachment_path = os.path.join(self.attachment_storage_path, attachment_filename)
                
                # Only write if file doesn't exist (deduplication)
                if not os.path.exists(attachment_path):
                    with open(attachment_path, 'wb') as f:
                        f.write(content)
                
                attachment_metadata[f'attachment_{i}'] = {
                    'original_filename': filename,
                    'stored_filename': attachment_filename,
                    'content_type': content_type,
                    'size': len(content),
                    'path': attachment_path
                }
            else:
                # Store attachment metadata for embedding
                attachment_metadata[f'attachment_{i}'] = {
                    'filename': filename,
                    'content_type': content_type,
                    'size': len(content),
                    'content_base64': base64.b64encode(content).decode('utf-8')
                }
        
        return attachment_metadata
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from MIME content type"""
        extension_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/vnd.ms-powerpoint': '.ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            'text/plain': '.txt',
            'text/html': '.html',
            'text/csv': '.csv',
            'application/zip': '.zip',
            'application/x-zip-compressed': '.zip',
            'application/rar': '.rar',
            'application/x-rar-compressed': '.rar',
            'audio/mpeg': '.mp3',
            'audio/wav': '.wav',
            'video/mp4': '.mp4',
            'video/avi': '.avi',
            'video/quicktime': '.mov'
        }
        return extension_map.get(content_type, '.bin')
    
    @abstractmethod
    def store_email(self, email: ParsedEmail) -> bool:
        """Store a single email. Returns True if successful."""
        pass
    
    @abstractmethod
    def describe(self) -> str:
        """Return a description of this storage backend"""
        pass
    
    @abstractmethod
    def close(self):
        """Clean up resources"""
        pass


class SQLiteStorage(StorageBackend):
    """SQLite storage backend for emails"""
    
    def __init__(self, db_path: str = "emails.db", attachment_storage_path: str = None):
        super().__init__(attachment_storage_path)
        self.db_path = db_path
        self.conn = None
        self.extra_attributes = []  # Will be populated by setup()
    
    def setup(self, mailbox):
        """Setup the storage backend with information from the mailbox"""
        # Get extra attributes from the mailbox
        self.extra_attributes = mailbox._extra_attributes.copy()
        
        # Initialize the database with the extra attributes
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        self.conn = sqlite3.connect(self.db_path)
        
        # Build the CREATE TABLE statement with extra attribute columns
        base_columns = [
            "id INTEGER PRIMARY KEY",
            "uid TEXT UNIQUE",
            "folder TEXT",
            "sender TEXT",
            "sender_name TEXT",
            "sender_email TEXT",
            "subject TEXT",
            "date TEXT",
            "message_id TEXT",
            "reply_to TEXT",
            "recipient TEXT",
            "body TEXT",
            "html TEXT",
            "attachments_metadata TEXT",  # JSON string with attachment info
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ]
        
        # Add extra attribute columns
        for column_name in self.extra_attributes:
            base_columns.append(f"{column_name} TEXT")
        
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS emails (
                {', '.join(base_columns)}
            )
        """
        
        self.conn.execute(create_table_sql)
        
        # Create indexes for fast queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sender ON emails(sender)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON emails(date)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_folder ON emails(folder)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_uid ON emails(uid)")
        
        # Create full-text search table
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts 
            USING fts5(sender, subject, body, content='emails', content_rowid='id')
        """)
        
        self.conn.commit()
    
    def store_email(self, email: ParsedEmail) -> bool:
        """Store a single email in SQLite"""
        try:
            # Check if email already exists
            cursor = self.conn.execute(
                "SELECT id FROM emails WHERE uid = ?", 
                (email.uid,)
            )
            if cursor.fetchone():
                print(f"Email {email.uid} already exists in database")
                return True
            
            # Determine folder based on sender domain
            folder = self._determine_folder(email)
            
            # Get extra attribute values from email.extra_attributes
            extra_attribute_values = []
            for attr_name in self.extra_attributes:
                try:
                    value = email.extra_attributes.get(attr_name, '')
                    extra_attribute_values.append(str(value) if value is not None else '')
                except Exception as e:
                    print(f"Warning: Extra attribute '{attr_name}' failed for email {email.uid}: {e}")
                    extra_attribute_values.append('')
            
            # Store attachments and get metadata
            import json
            attachment_metadata = self._store_attachments(email)
            attachments_json = json.dumps(attachment_metadata) if attachment_metadata else ""
            
            # Build INSERT statement with extra attribute columns
            base_columns = [
                "uid", "folder", "sender", "sender_name", "sender_email",
                "subject", "date", "message_id", "reply_to", "recipient", "body", "html", "attachments_metadata"
            ]
            all_columns = base_columns + self.extra_attributes
            
            # Build placeholders
            placeholders = ', '.join(['?' for _ in all_columns])
            
            # Build values tuple
            base_values = (
                email.uid,
                folder,
                email.envelope.get('sender', ''),
                email.sender_name,
                email.sender_email,
                email.envelope.get('subject', ''),
                email.envelope.get('date', ''),
                email.envelope.get('message_id', ''),
                email.envelope.get('reply_to', ''),
                email.envelope.get('to', ''),
                email.get_plain_text_body(),
                email.get_html(),
                attachments_json
            )
            all_values = base_values + tuple(extra_attribute_values)
            
            # Insert email data
            insert_sql = f"""
                INSERT INTO emails (
                    {', '.join(all_columns)}
                ) VALUES ({placeholders})
            """
            cursor = self.conn.execute(insert_sql, all_values)
            
            email_id = cursor.lastrowid
            
            # Insert into full-text search index
            self.conn.execute("""
                INSERT INTO emails_fts (rowid, sender, subject, body)
                VALUES (?, ?, ?, ?)
            """, (
                email_id,
                email.envelope.get('sender', ''),
                email.envelope.get('subject', ''),
                email.get_plain_text_body()
            ))
            
            self.conn.commit()
            print(f"Stored email {email.uid} in folder '{folder}'")
            return True
            
        except Exception as e:
            print(f"Error storing email {email.uid}: {e}")
            self.conn.rollback()
            return False
    
    def _determine_folder(self, email: ParsedEmail) -> str:
        """Determine folder based on sender domain"""
        if email.sender_email:
            domain = email.sender_email.split('@')[-1] if '@' in email.sender_email else 'unknown'
            return domain
        elif email.envelope.get('sender', ''):
            # Fallback to parsing from full sender string
            sender = email.envelope['sender']
            if '<' in sender and '>' in sender:
                email_part = sender.split('<')[1].split('>')[0]
                domain = email_part.split('@')[-1] if '@' in email_part else 'unknown'
                return domain
            elif '@' in sender:
                domain = sender.split('@')[-1]
                return domain
        
        return 'unknown'
    
    def describe(self) -> str:
        """Return a description of this SQLite storage backend"""
        return f"SQLite database at {os.path.abspath(self.db_path)}"
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()


class MaildirStorage(StorageBackend):
    """Maildir storage backend for emails"""
    
    def __init__(self, maildir_path: str, attachment_storage_path: str = None):
        super().__init__(attachment_storage_path)
        self.maildir_path = os.path.expanduser(maildir_path)
        self._ensure_maildir_structure()
    
    def _ensure_maildir_structure(self):
        """Create Maildir structure if it doesn't exist"""
        for subdir in ['cur', 'new', 'tmp']:
            os.makedirs(os.path.join(self.maildir_path, subdir), exist_ok=True)
    
    def store_email(self, email: ParsedEmail) -> bool:
        """Store a single email in Maildir format"""
        try:
            # Store attachments and get metadata
            import json
            attachment_metadata = self._store_attachments(email)
            
            # Generate unique filename
            import time
            import hashlib
            timestamp = str(int(time.time()))
            unique_id = hashlib.md5(f"{email.uid}{timestamp}".encode()).hexdigest()
            filename = f"{timestamp}.{unique_id}.mail"
            
            # Store in 'new' directory (unread)
            filepath = os.path.join(self.maildir_path, 'new', filename)
            
            # Get raw email data with attachment metadata embedded
            raw_email = self._reconstruct_raw_email(email, attachment_metadata)
            
            with open(filepath, 'wb') as f:
                f.write(raw_email)
            
            print(f"Stored email {email.uid} in Maildir")
            return True
            
        except Exception as e:
            print(f"Error storing email {email.uid} in Maildir: {e}")
            return False
    
    def _determine_folder(self, email: ParsedEmail) -> str:
        """Determine folder based on sender domain"""
        if email.sender_email:
            domain = email.sender_email.split('@')[-1] if '@' in email.sender_email else 'unknown'
            return domain
        elif email.envelope.get('sender', ''):
            # Fallback to parsing from full sender string
            sender = email.envelope['sender']
            if '<' in sender and '>' in sender:
                email_part = sender.split('<')[1].split('>')[0]
                domain = email_part.split('@')[-1] if '@' in email_part else 'unknown'
                return domain
            elif '@' in sender:
                domain = sender.split('@')[-1]
                return domain
        
        return 'unknown'
    
    def _reconstruct_raw_email(self, email: ParsedEmail, attachment_metadata: dict = None) -> bytes:
        """Reconstruct raw email from parsed components"""
        lines = []
        
        # Headers
        if email.envelope.get('sender'):
            lines.append(f"From: {email.envelope['sender']}")
        if email.envelope.get('subject'):
            lines.append(f"Subject: {email.envelope['subject']}")
        if email.envelope.get('date'):
            lines.append(f"Date: {email.envelope['date']}")
        if email.envelope.get('message_id'):
            lines.append(f"Message-ID: {email.envelope['message_id']}")
        if email.envelope.get('reply_to'):
            lines.append(f"Reply-To: {email.envelope['reply_to']}")
        if email.envelope.get('to'):
            lines.append(f"To: {email.envelope['to']}")
        
        # Add attachment metadata header if present
        if attachment_metadata:
            import json
            lines.append(f"X-Attachment-Metadata: {json.dumps(attachment_metadata)}")
        
        # Empty line separates headers from body
        lines.append("")
        
        # Body
        body = email.get_plain_text_body()
        if body:
            lines.append(body)
        
        return '\n'.join(lines).encode('utf-8')
    
    def describe(self) -> str:
        """Return a description of this Maildir storage backend"""
        return f"Maildir at {os.path.abspath(self.maildir_path)}"
    
    def close(self):
        """No cleanup needed for Maildir"""
        pass


class MboxStorage(StorageBackend):
    """Mbox storage backend for emails"""
    
    def __init__(self, mbox_path: str, attachment_storage_path: str = None):
        super().__init__(attachment_storage_path)
        self.mbox_path = os.path.expanduser(mbox_path)
        self.file = None
    
    def store_email(self, email: ParsedEmail) -> bool:
        """Store a single email in Mbox format"""
        try:
            # Store attachments and get metadata
            import json
            attachment_metadata = self._store_attachments(email)
            
            if not self.file:
                self.file = open(self.mbox_path, 'a', encoding='utf-8')
            
            # Mbox format: From line + email content + empty line
            # Use proper Mbox From line format
            from_line = f"From {email.envelope.get('sender', 'unknown')} {email.envelope.get('date', '')}\n"
            self.file.write(from_line)
            
            # Reconstruct email content with attachment metadata
            raw_email = self._reconstruct_raw_email(email, attachment_metadata)
            self.file.write(raw_email.decode('utf-8'))
            self.file.write("\n")  # Single newline after message
            self.file.flush()
            
            print(f"Stored email {email.uid} in Mbox file")
            return True
            
        except Exception as e:
            print(f"Error storing email {email.uid} in Mbox: {e}")
            return False
    
    def _reconstruct_raw_email(self, email: ParsedEmail, attachment_metadata: dict = None) -> bytes:
        """Reconstruct raw email from parsed components"""
        lines = []
        
        # Headers
        if email.envelope.get('sender'):
            lines.append(f"From: {email.envelope['sender']}")
        if email.envelope.get('subject'):
            lines.append(f"Subject: {email.envelope['subject']}")
        if email.envelope.get('date'):
            lines.append(f"Date: {email.envelope['date']}")
        if email.envelope.get('message_id'):
            lines.append(f"Message-ID: {email.envelope['message_id']}")
        if email.envelope.get('reply_to'):
            lines.append(f"Reply-To: {email.envelope['reply_to']}")
        if email.envelope.get('to'):
            lines.append(f"To: {email.envelope['to']}")
        
        # Add attachment metadata header if present
        if attachment_metadata:
            import json
            lines.append(f"X-Attachment-Metadata: {json.dumps(attachment_metadata)}")
        
        # Empty line separates headers from body
        lines.append("")
        
        # Body
        body = email.get_plain_text_body()
        if body:
            lines.append(body)
        
        return '\n'.join(lines).encode('utf-8')
    
    def describe(self) -> str:
        """Return a description of this Mbox storage backend"""
        return f"Mbox file at {os.path.abspath(self.mbox_path)}"
    
    def close(self):
        """Close the Mbox file"""
        if self.file:
            self.file.close()
            self.file = None 