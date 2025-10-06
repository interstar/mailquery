import pytest
from unittest.mock import Mock
from mailquery import Mailbox, ImapClient, CountReducer, SubjectConcatenator, SenderCollector
from mailquery import WordCountReducer, LongestSubjectFinder, EmailStatistics, HTMLPageBuilder
from mailquery import TextDocumentBuilder, AISummaryReducer
from mailquery.parsed_email import ParsedEmail


class TestReduceAll:
    """Test the reduce_all method with Reducer objects"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        # Create a stub client
        self.client = ImapClient('test')
        self.mailbox = Mailbox(self.client)
        
        # The stub client has 10 emails (5 from 2023, 5 from 2024)
        # We'll use these for testing various reduction scenarios
    
    def test_count_reducer(self):
        """Test counting total number of emails"""
        reducer = CountReducer()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should count all 10 emails in the stub data
        assert result == 10
    
    def test_subject_concatenator(self):
        """Test concatenating all email subjects"""
        reducer = SubjectConcatenator()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should concatenate all subjects
        assert "Hello" in result
        assert "Update" in result
        assert "Spam" in result
        assert "Newsletter" in result
        assert "Meeting" in result
        assert "Recent Email" in result
        assert "Today's Email" in result
        assert "Yesterday's Email" in result
        assert "Week Ago Email" in result
        assert "Month Ago Email" in result
        assert result.count(" | ") == 9  # 10 subjects joined by 9 separators
    
    def test_sender_collector(self):
        """Test collecting all unique sender email addresses"""
        reducer = SenderCollector()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should collect all unique senders
        assert len(result) == 9  # 9 unique senders in stub data (john@example.com appears twice)
        assert "john@example.com" in result
        assert "jane@example.com" in result
        assert "alice@example.com" in result
        assert "bob@example.com" in result
        assert "recent@example.com" in result
        assert "today@example.com" in result
        assert "yesterday@example.com" in result
        assert "week_ago@example.com" in result
        assert "month_ago@example.com" in result
    
    def test_word_count_reducer(self):
        """Test counting total words across all email bodies"""
        reducer = WordCountReducer()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should count words in all email bodies
        assert result > 0
        # Each stub email has a body with multiple words
    
    def test_longest_subject_finder(self):
        """Test finding the email with the longest subject line"""
        reducer = LongestSubjectFinder()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should return the email with the longest subject
        assert isinstance(result, ParsedEmail)
        # The longest subject in stub data is "Yesterday's Email" (18 chars)
        assert result['subject'] == "Yesterday's Email"
    
    def test_email_statistics(self):
        """Test building email statistics"""
        reducer = EmailStatistics()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should build comprehensive statistics
        assert result['total_emails'] == 10
        assert len(result['senders']) == 9  # 9 unique senders (john@example.com appears twice)
        assert len(result['subjects']) == 10
        assert result['has_html'] >= 0  # Some emails might have HTML
        assert result['total_subject_length'] > 0
        assert result['longest_subject'] != ''
        assert len(result['sender_counts']) == 9  # 9 unique senders
    
    def test_html_page_builder(self):
        """Test building an HTML page from all emails"""
        reducer = HTMLPageBuilder()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should build a complete HTML page
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "</html>" in result
        assert "<title>Email Collection</title>" in result
        assert "Hello" in result  # Should contain email content
        assert "Today&#x27;s Email" in result  # HTML escaped apostrophe
        assert "john@example.com" in result
    
    def test_text_document_builder(self):
        """Test building a plain text document from all emails"""
        reducer = TextDocumentBuilder()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should build a complete text document
        assert isinstance(result, str)
        assert "EMAIL COLLECTION" in result
        assert "Hello" in result  # Should contain email content
        assert "Today's Email" in result
        assert "john@example.com" in result
        assert "From:" in result
        assert "Subject:" in result
        assert "Date:" in result
    
    def test_ai_summary_reducer(self):
        """Test preparing emails for AI summarization"""
        reducer = AISummaryReducer()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should return structured data for AI processing
        assert isinstance(result, list)
        assert len(result) == 10
        
        # Check structure of first email
        first_email = result[0]
        assert 'sender' in first_email
        assert 'subject' in first_email
        assert 'date' in first_email
        assert 'body' in first_email
        assert 'uid' in first_email
        assert isinstance(first_email['sender'], str)
        assert isinstance(first_email['subject'], str)
        assert isinstance(first_email['body'], str)
    
    def test_filtered_reduction(self):
        """Test reduce_all with filtered mailbox"""
        # Filter to only recent emails (from 2024)
        recent_mailbox = self.mailbox.younger_than(365, verbose=False)
        
        reducer = CountReducer()
        result = recent_mailbox.reduce_all(reducer, verbose=False)
        
        # Should only count emails from 2024 (5 emails)
        assert result == 5
    
    def test_empty_mailbox(self):
        """Test reduce_all with empty mailbox (no matching emails)"""
        # Filter to get no emails
        empty_mailbox = self.mailbox.older_than(1000, verbose=False)  # Very old filter
        
        reducer = CountReducer()
        result = empty_mailbox.reduce_all(reducer, verbose=False)
        
        # Should return 0 when no emails match
        assert result == 0
    
    def test_verbose_output(self, capsys):
        """Test that verbose output works correctly"""
        reducer = CountReducer()
        result = self.mailbox.reduce_all(reducer, verbose=True)
        
        # Check that verbose output was printed
        captured = capsys.readouterr()
        assert "Starting reduce_all() iteration..." in captured.out
        assert "Reducer initialized" in captured.out
        assert "Processing email" in captured.out
        assert "Reduction completed" in captured.out
        assert "Final result: 10" in captured.out
    
    def test_method_chaining(self):
        """Test that reduce_all can be chained with other methods"""
        reducer = CountReducer()
        
        # Chain filtering with reduction
        result = (self.mailbox
                 .from_('john@example.com', verbose=False)
                 .reduce_all(reducer, verbose=False))
        
        # Should count emails from john@example.com (2 emails in stub data)
        assert result == 2
    
    def test_custom_reducer(self):
        """Test using a custom Reducer implementation"""
        class CustomReducer:
            def init_value(self):
                self.emails = []
            
            def fold(self, email):
                self.emails.append(email['subject'])
            
            def final(self):
                return f"Found {len(self.emails)} emails: {', '.join(self.emails[:3])}..."
        
        reducer = CustomReducer()
        result = self.mailbox.reduce_all(reducer, verbose=False)
        
        # Should return custom formatted result
        assert "Found 10 emails:" in result
        assert "Hello" in result
        assert "..." in result
    
    def test_reducer_state_isolation(self):
        """Test that reducer state is isolated between calls"""
        reducer1 = CountReducer()
        reducer2 = CountReducer()
        
        # Use same reducer instance twice
        result1 = self.mailbox.reduce_all(reducer1, verbose=False)
        result2 = self.mailbox.reduce_all(reducer1, verbose=False)
        
        # Both should return the same result (state is reset each time)
        assert result1 == 10
        assert result2 == 10
        
        # Use different reducer instances
        result3 = self.mailbox.reduce_all(reducer2, verbose=False)
        assert result3 == 10 