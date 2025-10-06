import pytest
from unittest.mock import patch, MagicMock
from mailquery import Mailbox, ImapClient, SQLiteStorage
from mailquery.parsed_email import ParsedEmail


class TestAddAttribute:
    """Test the add_attribute functionality"""
    
    def test_add_attribute_basic(self):
        """Test basic add_attribute functionality"""
        # Create a mock client
        client = ImapClient('test')
        mailbox = Mailbox(client)
        
        # Add an attribute that computes subject length
        mailbox.add_attribute("subject_len", lambda e: len(e.envelope.get("subject", "")))
        
        # Get the first email
        emails = list(mailbox)
        assert len(emails) > 0
        
        # Check that the extra_attributes dict exists and contains our computed value
        email = emails[0]
        assert hasattr(email, 'extra_attributes')
        assert 'subject_len' in email.extra_attributes
        assert isinstance(email.extra_attributes['subject_len'], int)
        
        # Verify the value is correct
        expected_length = len(email.envelope.get("subject", ""))
        assert email.extra_attributes['subject_len'] == expected_length
    
    def test_add_attribute_multiple(self):
        """Test adding multiple attributes"""
        client = ImapClient('test')
        mailbox = Mailbox(client)
        
        # Add multiple attributes
        mailbox.add_attribute("subject_len", lambda e: len(e.envelope.get("subject", "")))
        mailbox.add_attribute("has_html", lambda e: e.get_html() is not None)
        mailbox.add_attribute("sender_domain", lambda e: e.sender_email.split('@')[-1] if '@' in e.sender_email else '')
        
        emails = list(mailbox)
        assert len(emails) > 0
        
        email = emails[0]
        assert 'subject_len' in email.extra_attributes
        assert 'has_html' in email.extra_attributes
        assert 'sender_domain' in email.extra_attributes
        
        # Verify values are computed correctly
        assert email.extra_attributes['subject_len'] == len(email.envelope.get("subject", ""))
        assert email.extra_attributes['has_html'] == (email.get_html() is not None)
        if '@' in email.sender_email:
            assert email.extra_attributes['sender_domain'] == email.sender_email.split('@')[-1]
    
    def test_add_attribute_with_storage(self):
        """Test that add_attribute works with SQLiteStorage"""
        client = ImapClient('test')
        mailbox = Mailbox(client)
        
        # Add attributes
        mailbox.add_attribute("subject_len", lambda e: len(e.envelope.get("subject", "")))
        mailbox.add_attribute("word_count", lambda e: len(e.get_plain_text_body().split()))
        
        # Create storage (this should call setup() and create columns)
        storage = SQLiteStorage("test_add_attribute.db")
        
        # Store emails (this should use the extra attributes)
        mailbox.store_local(storage)
        
        # Verify the storage was set up with the extra attributes
        assert 'subject_len' in storage.extra_attributes
        assert 'word_count' in storage.extra_attributes
        
        # Clean up
        import os
        if os.path.exists("test_add_attribute.db"):
            os.remove("test_add_attribute.db")
    
    def test_add_attribute_persistence(self):
        """Test that extra_attributes persist across operations"""
        client = ImapClient('test')
        mailbox = Mailbox(client)
        
        # Add an attribute
        mailbox.add_attribute("subject_len", lambda e: len(e.envelope.get("subject", "")))
        
        # Get emails twice
        emails1 = list(mailbox)
        emails2 = list(mailbox)
        
        # Both should have the extra attribute
        assert len(emails1) > 0
        assert len(emails2) > 0
        
        email1 = emails1[0]
        email2 = emails2[0]
        
        assert 'subject_len' in email1.extra_attributes
        assert 'subject_len' in email2.extra_attributes
        assert email1.extra_attributes['subject_len'] == email2.extra_attributes['subject_len']
    
    def test_add_attribute_chaining(self):
        """Test that add_attribute supports method chaining"""
        client = ImapClient('test')
        mailbox = Mailbox(client)
        
        # Chain add_attribute calls
        result = (mailbox
                 .add_attribute("subject_len", lambda e: len(e.envelope.get("subject", "")))
                 .add_attribute("has_html", lambda e: e.get_html() is not None))
        
        # Should return self for chaining
        assert result is mailbox
        
        # Both attributes should be added
        assert 'subject_len' in mailbox._extra_attributes
        assert 'has_html' in mailbox._extra_attributes 