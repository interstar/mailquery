import unittest
from unittest.mock import Mock
from mailquery import Mailbox, ParsedEmail, parse_envelope, parse_full_email


class TestParsedEmail(unittest.TestCase):
    def setUp(self):
        self.body_fetch_count = 0
        
        def make_email(uid, sender, subject, body):
            raw = f"From: {sender}\nSubject: {subject}\nDate: 2023-06-25\nMessage-ID: <{uid}@test>\n\n{body}".encode()
            envelope = parse_envelope(raw)
            
            def fetch_body():
                self.body_fetch_count += 1
                return raw
            
            return ParsedEmail(uid, envelope, fetch_body)
        
        self.email1 = make_email("1", "alice@example.com", "Hello", "foobar here")
        self.email2 = make_email("2", "bob@example.com", "Spam", "nothing useful")
        self.email3 = make_email("3", "alice@example.com", "Update", "another foobar")

    def test_envelope_access(self):
        """Test accessing envelope data without fetching body"""
        self.assertEqual(self.email1["sender"], "alice@example.com")
        self.assertEqual(self.email1["subject"], "Hello")
        self.assertEqual(self.body_fetch_count, 0)  # No body fetch yet

    def test_lazy_body_fetching(self):
        """Test that body is only fetched when get_body() is called"""
        self.assertEqual(self.body_fetch_count, 0)
        
        body = self.email1.get_plain_text_body()
        self.assertEqual(body, "foobar here")
        self.assertEqual(self.body_fetch_count, 1)
        
        # Second call should use cached value
        body2 = self.email1.get_plain_text_body()
        self.assertEqual(body2, "foobar here")
        self.assertEqual(self.body_fetch_count, 1)  # Still 1, not 2

    def test_body_access_via_getitem(self):
        """Test accessing body via email["body"]"""
        self.assertEqual(self.body_fetch_count, 0)
        
        body = self.email1["body"]
        self.assertEqual(body, "foobar here")
        self.assertEqual(self.body_fetch_count, 1)

    def test_html_access(self):
        """Test HTML access triggers body fetch"""
        self.assertEqual(self.body_fetch_count, 0)
        
        html = self.email1.get_html()
        self.assertEqual(self.body_fetch_count, 1)  # get_html() calls get_body()

    def test_repr(self):
        """Test string representation"""
        self.assertIn("alice@example.com", repr(self.email1))
        self.assertIn("Hello", repr(self.email1))


class TestMailboxFiltering(unittest.TestCase):
    def setUp(self):
        self.body_fetch_count = 0
        
        def make_email(uid, sender, subject, body):
            raw = f"From: {sender}\nSubject: {subject}\nDate: 2023-06-25\nMessage-ID: <{uid}@test>\n\n{body}".encode()
            envelope = parse_envelope(raw)
            
            def fetch_body():
                self.body_fetch_count += 1
                return raw
            
            return ParsedEmail(uid, envelope, fetch_body)
        
        self.emails = [
            make_email("1", "alice@example.com", "Hello", "foobar here"),
            make_email("2", "bob@example.com", "Spam", "nothing useful"),
            make_email("3", "alice@example.com", "Update", "another foobar"),
            make_email("4", "charlie@example.com", "Newsletter", "important content"),
        ]
        
        self.mock_client = Mock()
        self.mock_client.list_messages.return_value = (e for e in self.emails)

    def test_include_when_sender_filter(self):
        """Test filtering by sender"""
        mbox = Mailbox(self.mock_client)
        mbox.include_when(lambda e: e["sender"] == "alice@example.com")
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 2)
        self.assertTrue(all("alice" in e["sender"] for e in results))

    def test_exclude_when_subject_filter(self):
        """Test excluding by subject"""
        mbox = Mailbox(self.mock_client)
        mbox.exclude_when(lambda e: "Spam" in e["subject"])
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 3)
        self.assertTrue(all("Spam" not in e["subject"] for e in results))

    def test_include_body_filter_lazy(self):
        """Test body filtering with lazy loading"""
        self.body_fetch_count = 0
        mbox = Mailbox(self.mock_client)
        mbox.include_when(lambda e: "foobar" in e.get_plain_text_body())
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 2)
        self.assertEqual(self.body_fetch_count, 4)  # All 4 emails checked

    def test_combined_filters(self):
        """Test combining include and exclude filters"""
        mbox = Mailbox(self.mock_client)
        mbox.include_when(lambda e: e["sender"] == "alice@example.com")
        mbox.include_when(lambda e: "foobar" in e.get_plain_text_body())
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 2)
        self.assertTrue(all("alice" in e["sender"] and "foobar" in e.get_plain_text_body() for e in results))

    def test_convenience_methods(self):
        """Test convenience filter methods"""
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com").body_contains("foobar")
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 2)

    def test_subject_contains(self):
        """Test subject filtering"""
        mbox = Mailbox(self.mock_client)
        mbox.subject_contains("Hello")
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject"], "Hello")

    def test_date_filtering(self):
        """Test date filtering"""
        # Create emails with different dates
        def make_dated_email(uid, sender, subject, date_str):
            raw = f"From: {sender}\nSubject: {subject}\nDate: {date_str}\nMessage-ID: <{uid}@test>\n\nbody".encode()
            envelope = parse_envelope(raw)
            return ParsedEmail(uid, envelope, lambda: raw)
        
        dated_emails = [
            make_dated_email("1", "a@test.com", "Old", "2023-06-20"),
            make_dated_email("2", "b@test.com", "New", "2023-06-25"),
        ]
        
        mock_client = Mock()
        mock_client.list_messages.return_value = (e for e in dated_emails)
        
        mbox = Mailbox(mock_client)
        mbox.after("2023-06-22")
        
        results = list(mbox.fetch())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject"], "New")

    def test_iteration(self):
        """Test that Mailbox is iterable"""
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com")
        
        count = 0
        for email in mbox:
            count += 1
            self.assertIn("alice", email["sender"])
        
        self.assertEqual(count, 2)

    def test_delete_action(self):
        """Test delete action"""
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com")
        
        mbox.delete()
        
        # Verify delete_message was called for each matching email
        self.assertEqual(self.mock_client.delete_message.call_count, 2)
        calls = self.mock_client.delete_message.call_args_list
        self.assertEqual(calls[0][0][0], "1")  # First email UID
        self.assertEqual(calls[1][0][0], "3")  # Third email UID

    def test_store_local_action(self):
        """Test store local action"""
        from unittest.mock import Mock
        from mailquery import StorageBackend
        
        # Create a mock storage backend
        mock_storage = Mock(spec=StorageBackend)
        mock_storage.store_email.return_value = True
        mock_storage.describe.return_value = "Mock storage"
        mock_storage.close.return_value = None
        
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com")
        
        # This should call the storage backend for each matching email
        mbox.store_local(mock_storage)
        
        # Verify store_email was called for each matching email
        self.assertEqual(mock_storage.store_email.call_count, 2)
        mock_storage.close.assert_called_once()
    
    def test_subquery_creation(self):
        """Test creating a subquery from a mailbox"""
        mbox = Mailbox(self.mock_client)
        subquery = mbox.subquery()
        
        # Should be a SubqueryMailbox instance
        from mailquery.mailbox import SubqueryMailbox
        self.assertIsInstance(subquery, SubqueryMailbox)
        self.assertEqual(subquery.parent, mbox)
    
    def test_subquery_filtering(self):
        """Test that subquery filters work independently"""
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com")  # 2 emails
        
        # Create subquery with additional filter
        subquery = mbox.subquery().subject_contains("Hello")  # 1 email
        
        # Original should still have 2 emails
        original_results = list(mbox.fetch())
        self.assertEqual(len(original_results), 2)
        
        # Subquery should have 1 email
        subquery_results = list(subquery.fetch())
        self.assertEqual(len(subquery_results), 1)
        self.assertEqual(subquery_results[0]["subject"], "Hello")
    
    def test_nested_subqueries(self):
        """Test creating subqueries from subqueries"""
        mbox = Mailbox(self.mock_client)
        mbox.from_("alice@example.com")  # 2 emails
        
        # First subquery
        subquery1 = mbox.subquery().subject_contains("Hello")  # 1 email
        
        # Second subquery from first subquery
        subquery2 = subquery1.subquery().body_contains("foobar")  # 1 email
        
        # All should work correctly
        self.assertEqual(len(list(mbox.fetch())), 2)
        self.assertEqual(len(list(subquery1.fetch())), 1)
        self.assertEqual(len(list(subquery2.fetch())), 1)
    
    def test_subquery_shared_cache(self):
        """Test that subqueries share the parent's cache"""
        mbox = Mailbox(self.mock_client)
        subquery = mbox.subquery()
        
        # First access should populate cache
        list(mbox.fetch())
        
        # Second access should use cache
        list(subquery.fetch())
        
        # Both should have accessed the same cached data
        self.assertTrue(mbox._message_ids_fetched)
        self.assertEqual(len(mbox._cached_emails), 4)
    
    def test_filtered_mailbox_with_subquery(self):
        """Test a filtered mailbox with a subquery that further restricts the collection"""
        mbox = Mailbox(self.mock_client)
        
        # Apply initial filter to main mailbox
        mbox.from_("alice@example.com")  # Should match 2 emails: "Hello" and "Update"
        
        # Create subquery with additional filter
        urgent_emails = mbox.subquery().subject_contains("Hello")  # Should match 1 email: "Hello"
        
        # Verify main mailbox has correct emails (2 emails from alice@example.com)
        main_results = list(mbox.fetch())
        self.assertEqual(len(main_results), 2)
        self.assertTrue(all("alice@example.com" in email["sender"] for email in main_results))
        subjects = [email["subject"] for email in main_results]
        self.assertIn("Hello", subjects)
        self.assertIn("Update", subjects)
        
        # Verify subquery has correct emails (1 email: "Hello" from alice@example.com)
        subquery_results = list(urgent_emails.fetch())
        self.assertEqual(len(subquery_results), 1)
        self.assertEqual(subquery_results[0]["subject"], "Hello")
        self.assertIn("alice@example.com", subquery_results[0]["sender"])
        
        # Verify parent's filters are preserved and not affected by subquery
        main_results_again = list(mbox.fetch())
        self.assertEqual(len(main_results_again), 2)  # Still 2 emails
        self.assertEqual(main_results, main_results_again)  # Same results
    
    def test_subquery_with_multiple_filters(self):
        """Test subquery with multiple filters applied"""
        mbox = Mailbox(self.mock_client)
        
        # Apply initial filter to main mailbox
        mbox.from_("alice@example.com")  # 2 emails
        
        # Create subquery with multiple filters
        filtered_subquery = mbox.subquery()\
            .subject_contains("Hello")\
            .body_contains("foobar")  # Should match 1 email: "Hello" with "foobar" in body
        
        # Verify main mailbox still has 2 emails
        main_results = list(mbox.fetch())
        self.assertEqual(len(main_results), 2)
        
        # Verify subquery has 1 email (both filters must pass)
        subquery_results = list(filtered_subquery.fetch())
        self.assertEqual(len(subquery_results), 1)
        self.assertEqual(subquery_results[0]["subject"], "Hello")
        self.assertIn("foobar", subquery_results[0].get_plain_text_body())
    
    def test_subquery_exclude_filter(self):
        """Test subquery with exclude filter"""
        mbox = Mailbox(self.mock_client)
        
        # Apply initial filter to main mailbox
        mbox.from_("alice@example.com")  # 2 emails
        
        # Create subquery that excludes emails with "Update" in subject
        filtered_subquery = mbox.subquery().exclude_when(lambda e: "Update" in e["subject"])
        
        # Verify main mailbox still has 2 emails
        main_results = list(mbox.fetch())
        self.assertEqual(len(main_results), 2)
        
        # Verify subquery has 1 email (excluded the "Update" email)
        subquery_results = list(filtered_subquery.fetch())
        self.assertEqual(len(subquery_results), 1)
        self.assertEqual(subquery_results[0]["subject"], "Hello")


class TestMailboxChaining(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.mock_client.list_messages.return_value = []

    def test_method_chaining(self):
        """Test that filter methods can be chained"""
        mbox = Mailbox(self.mock_client)
        
        # This should not raise an exception
        result = mbox.from_("test@example.com")\
                    .body_contains("important")\
                    .subject_contains("urgent")\
                    .exclude_when(lambda e: "spam" in e["subject"])
        
        self.assertIs(result, mbox)  # Should return self for chaining

    def test_empty_filters(self):
        """Test behavior with no filters applied"""
        mbox = Mailbox(self.mock_client)
        results = list(mbox.fetch())
        self.assertEqual(len(results), 0)  # No emails in mock


if __name__ == "__main__":
    unittest.main() 