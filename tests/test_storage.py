#!/usr/bin/env python3
"""
Test the pluggable storage system
"""

import unittest
import tempfile
import os
from unittest.mock import Mock
from mailquery import SQLiteStorage, MaildirStorage, MboxStorage, ParsedEmail, parse_envelope, Mailbox


class TestStorageBackends(unittest.TestCase):
    def setUp(self):
        # Create test email
        raw = b"From: test@example.com\nSubject: Test Email\nDate: 2023-06-25\nMessage-ID: <test@example>\n\nThis is a test email body"
        envelope = parse_envelope(raw)
        
        def fetch_body():
            return raw
        
        self.test_email = ParsedEmail("test-uid-123", envelope, fetch_body)
        
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.sqlite_path = os.path.join(self.temp_dir, "test.db")
        self.maildir_path = os.path.join(self.temp_dir, "maildir")
        self.mbox_path = os.path.join(self.temp_dir, "test.mbox")
    
    def tearDown(self):
        # Clean up temporary files
        # import shutil
        # shutil.rmtree(self.temp_dir)
        print(f"\n📁 Test files preserved in: {self.temp_dir}")
        print(f"   SQLite: {self.sqlite_path}")
        print(f"   Maildir: {self.maildir_path}")
        print(f"   Mbox: {self.mbox_path}")
        pass
    
    def test_sqlite_storage(self):
        """Test SQLite storage backend"""
        storage = SQLiteStorage(self.sqlite_path)
        
        # Store email
        result = storage.store_email(self.test_email)
        self.assertTrue(result)
        
        # Verify it was stored
        import sqlite3
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.execute("SELECT uid, folder, sender, subject FROM emails WHERE uid = ?", (self.test_email.uid,))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "test-uid-123")
        self.assertEqual(row[1], "example.com")  # Auto-determined from sender domain
        self.assertEqual(row[2], "test@example.com")
        self.assertEqual(row[3], "Test Email")
        
        conn.close()
        storage.close()
    
    def test_maildir_storage(self):
        """Test Maildir storage backend"""
        storage = MaildirStorage(self.maildir_path)
        
        # Store email
        result = storage.store_email(self.test_email)
        self.assertTrue(result)
        
        # Verify file was created
        folder_path = os.path.join(self.maildir_path, "example.com", "new")
        files = os.listdir(folder_path)
        self.assertEqual(len(files), 1)
        
        # Verify file content
        filepath = os.path.join(folder_path, files[0])
        with open(filepath, 'rb') as f:
            content = f.read().decode('utf-8')
        
        self.assertIn("From: test@example.com", content)
        self.assertIn("Subject: Test Email", content)
        self.assertIn("This is a test email body", content)
        
        storage.close()
    
    def test_mbox_storage(self):
        """Test Mbox storage backend"""
        storage = MboxStorage(self.mbox_path)
        
        # Store email
        result = storage.store_email(self.test_email)
        self.assertTrue(result)
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.mbox_path))
        
        # Verify file content
        with open(self.mbox_path, 'r') as f:
            content = f.read()
        
        self.assertIn("From test@example.com", content)
        self.assertIn("From: test@example.com", content)
        self.assertIn("Subject: Test Email", content)
        self.assertIn("This is a test email body", content)
        
        storage.close()
    
    def test_duplicate_prevention_sqlite(self):
        """Test that SQLite prevents duplicate emails"""
        storage = SQLiteStorage(self.sqlite_path)
        
        # Store email twice
        result1 = storage.store_email(self.test_email)
        result2 = storage.store_email(self.test_email)
        
        self.assertTrue(result1)
        self.assertTrue(result2)  # Should succeed but not create duplicate
        
        # Verify only one record exists
        import sqlite3
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.execute("SELECT COUNT(*) FROM emails WHERE uid = ?", (self.test_email.uid,))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)
        
        conn.close()
        storage.close()


class TestMailboxIntegration(unittest.TestCase):
    def setUp(self):
        # Create mock client with test emails
        self.mock_client = Mock()
        
        # Create test emails
        emails = []
        for i in range(3):
            raw = f"From: sender{i}@example.com\nSubject: Test {i}\nDate: 2023-06-25\nMessage-ID: <test{i}@example>\n\nBody {i}".encode()
            envelope = parse_envelope(raw)
            email = ParsedEmail(f"uid-{i}", envelope, lambda raw=raw: raw)
            emails.append(email)
        
        self.mock_client.list_messages.return_value = emails
    
    def test_mailbox_with_sqlite_storage(self):
        """Test Mailbox integration with SQLite storage"""
        import tempfile
        import os
        
        temp_dir = tempfile.mkdtemp()
        sqlite_path = os.path.join(temp_dir, "test.db")
        
        try:
            storage = SQLiteStorage(sqlite_path)
            mails = Mailbox(self.mock_client)
            
            # Store all emails
            mails.store_local(storage)
            
            # Verify storage
            import sqlite3
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.execute("SELECT COUNT(*) FROM emails")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 3)
            
            conn.close()
            
        finally:
            # import shutil
            # shutil.rmtree(temp_dir)
            print(f"📁 Integration test files preserved in: {temp_dir}")
            pass


if __name__ == "__main__":
    unittest.main() 