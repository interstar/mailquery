import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from mailquery import Mailbox, ImapClient
from mailquery.parsed_email import ParsedEmail


class TestTimeFilters:
    """Test the older_than and younger_than filter methods"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        # Create a stub client
        self.client = ImapClient('test')
        self.mailbox = Mailbox(self.client)
        
        # Mock datetime.now() to return a fixed date for consistent testing
        # We'll use 2024-12-20 as "today" for our tests
        self.fixed_now = datetime(2024, 12, 20, 12, 0, 0)
    
    @patch('mailquery.mailbox.datetime')
    def test_older_than_days(self, mock_datetime):
        """Test filtering emails older than a specified number of days"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails older than 5 days
        filtered_mailbox = self.mailbox.older_than(5)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2023 (much older) and some from 2024
        # Emails older than 5 days from 2024-12-20: 2024-12-13 (7 days ago), 2024-11-20 (30 days ago)
        # Note: 2024-12-15 is exactly 5 days ago, so it's not "older than 5 days"
        assert len(emails) == 7  # 5 from 2023 + 2 from 2024 that are older than 5 days
        subjects = [email.envelope['subject'] for email in emails]
        assert 'Week Ago Email' in subjects  # 2024-12-13 (7 days ago)
        assert 'Month Ago Email' in subjects  # 2024-11-20 (30 days ago)
    
    @patch('mailquery.mailbox.datetime')
    def test_older_than_weeks(self, mock_datetime):
        """Test filtering emails older than a specified number of weeks"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails older than 7 days
        filtered_mailbox = self.mailbox.older_than(7)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2023 (much older) and some from 2024
        # Emails older than 7 days from 2024-12-20: 2024-11-20 (30 days ago)
        # Note: 2024-12-13 is exactly 7 days ago, so it's not "older than 7 days"
        assert len(emails) == 6  # 5 from 2023 + 1 from 2024 that is older than 7 days
        subjects = [email.envelope['subject'] for email in emails]
        assert 'Month Ago Email' in subjects  # 2024-11-20 (30 days ago)
    
    @patch('mailquery.mailbox.datetime')
    def test_younger_than_days(self, mock_datetime):
        """Test filtering emails newer than a specified number of days"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails newer than 5 days
        filtered_mailbox = self.mailbox.younger_than(5)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2024 that are newer than 5 days
        # Emails newer than 5 days from 2024-12-20: 2024-12-20, 2024-12-19, 2024-12-15
        # Note: 2024-12-15 is exactly 5 days ago, so it's not "newer than 5 days" either
        assert len(emails) == 3
        subjects = [email.envelope['subject'] for email in emails]
        assert "Today's Email" in subjects  # 2024-12-20 (today)
        assert "Yesterday's Email" in subjects  # 2024-12-19 (1 day ago)
        assert 'Recent Email' in subjects  # 2024-12-15 (5 days ago)
    
    @patch('mailquery.mailbox.datetime')
    def test_younger_than_weeks(self, mock_datetime):
        """Test filtering emails newer than a specified number of weeks"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails newer than 7 days
        filtered_mailbox = self.mailbox.younger_than(7)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2024 that are newer than 7 days
        # Emails newer than 7 days from 2024-12-20: 2024-12-20, 2024-12-19, 2024-12-15, 2024-12-13
        # Note: 2024-12-13 is exactly 7 days ago, so it's included in "newer than 7 days"
        assert len(emails) == 4
        subjects = [email.envelope['subject'] for email in emails]
        assert "Today's Email" in subjects  # 2024-12-20 (today)
        assert "Yesterday's Email" in subjects  # 2024-12-19 (1 day ago)
        assert 'Recent Email' in subjects  # 2024-12-15 (5 days ago)
        assert 'Week Ago Email' in subjects  # 2024-12-13 (7 days ago)
    
    @patch('mailquery.mailbox.datetime')
    def test_older_than_months(self, mock_datetime):
        """Test filtering emails older than a specified number of months"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails older than 31 days (1 month)
        filtered_mailbox = self.mailbox.older_than(31)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2023 (much older) and some from 2024
        # Emails older than 31 days from 2024-12-20: 2024-11-20 (30 days ago)
        # Note: 2024-11-20 is exactly 30 days ago, so it's not "older than 31 days"
        assert len(emails) == 5  # 5 from 2023 (no emails from 2024 are older than 31 days)
        subjects = [email.envelope['subject'] for email in emails]
        # All emails from 2023 should be included
    
    @patch('mailquery.mailbox.datetime')
    def test_younger_than_months(self, mock_datetime):
        """Test filtering emails newer than a specified number of months"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails newer than 31 days (1 month)
        filtered_mailbox = self.mailbox.younger_than(31)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2024 that are newer than 31 days
        # Emails newer than 31 days from 2024-12-20: 2024-12-20, 2024-12-19, 2024-12-15, 2024-12-13, 2024-11-20
        # Note: 2024-11-20 is exactly 30 days ago, so it's included in "newer than 31 days"
        assert len(emails) == 5
        subjects = [email.envelope['subject'] for email in emails]
        assert "Today's Email" in subjects  # 2024-12-20 (today)
        assert "Yesterday's Email" in subjects  # 2024-12-19 (1 day ago)
        assert 'Recent Email' in subjects  # 2024-12-15 (5 days ago)
        assert 'Week Ago Email' in subjects  # 2024-12-13 (7 days ago)
        assert 'Month Ago Email' in subjects  # 2024-11-20 (30 days ago)
    
    @patch('mailquery.mailbox.datetime')
    def test_older_than_years(self, mock_datetime):
        """Test filtering emails older than a specified number of years"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails older than 365 days (1 year)
        filtered_mailbox = self.mailbox.older_than(365)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2023 (much older than 1 year)
        assert len(emails) == 5  # All 5 emails from 2023
        subjects = [email.envelope['subject'] for email in emails]
        assert 'Hello' in subjects
        assert 'Update' in subjects
        assert 'Spam' in subjects
        assert 'Newsletter' in subjects
        assert 'Meeting' in subjects
    
    @patch('mailquery.mailbox.datetime')
    def test_younger_than_years(self, mock_datetime):
        """Test filtering emails newer than a specified number of years"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails newer than 365 days (1 year)
        filtered_mailbox = self.mailbox.younger_than(365)
        emails = list(filtered_mailbox)
        
        # Should include emails from 2024 that are newer than 1 year
        # All emails from 2024 are newer than 1 year from 2024-12-20
        assert len(emails) == 5  # All 5 emails from 2024
        subjects = [email.envelope['subject'] for email in emails]
        assert 'Recent Email' in subjects
        assert "Today's Email" in subjects
        assert "Yesterday's Email" in subjects
        assert 'Week Ago Email' in subjects
        assert 'Month Ago Email' in subjects
    
    @patch('mailquery.mailbox.datetime')
    def test_method_chaining(self, mock_datetime):
        """Test that time filters can be chained with other filters"""
        # Mock datetime.now() to return our fixed date
        mock_datetime.now.return_value = self.fixed_now
        
        # Filter emails older than 5 days AND from a specific sender
        filtered_mailbox = self.mailbox.older_than(5).from_('john@example.com')
        emails = list(filtered_mailbox)
        
        # Should include emails from john@example.com that are older than 5 days
        assert len(emails) == 2  # john@example.com has 2 emails that are older than 5 days
        for email in emails:
            assert email.envelope['from'] == 'john@example.com' 