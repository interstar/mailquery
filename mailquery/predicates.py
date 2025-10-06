"""
Predicate classes for server-side filtering optimization.

These classes provide the same interface as lambda functions for client-side filtering,
but can be recognized by clients for server-side optimization.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from .parsed_email import ParsedEmail


class OR:
    def __init__(self, *xs):
        self.xs = xs


class Predicate(ABC):
    """Base class for optimizable filter predicates"""
    
    @abstractmethod
    def __call__(self, email: ParsedEmail) -> bool:
        """Filter function - returns True if email matches the predicate"""
        pass


class BEFORE(Predicate):
    """Filter for emails before a given date"""
    
    def __init__(self, date_str: str, mailbox=None):
        """
        Initialize with date string in YYYY-MM-DD format
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            mailbox: Reference to mailbox for verbose setting
        """
        self.date_str = date_str
        self.mailbox = mailbox
        # Validate date format immediately
        try:
            self.cutoff_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD format.") from e
    
    @property
    def verbose(self):
        """Get verbose setting from mailbox if available"""
        return getattr(self.mailbox, '_verbose', True) if self.mailbox else True
    
    def __call__(self, email: ParsedEmail) -> bool:
        """Return True if email date is before the cutoff date"""
        # Get the date string first (might raise KeyError)
        try:
            date_str = email["date"]
        except KeyError:
            if self.verbose:
                print(f"BEFORE predicate: No date field found for email from {email.envelope.get('from', 'unknown')}")
            return False
        
        try:
            # Try multiple date formats that Gmail might return
            
            # Handle empty date strings (likely chat messages or corrupted emails)
            if not date_str or date_str.strip() == '':
                # Check if this looks like a chat message
                message_id = email.envelope.get('message_id', '')
                if self.verbose:
                    if 'chat' in message_id.lower():
                        print(f"BEFORE predicate: Skipping chat message from {email.envelope.get('from', 'unknown')} (date: '{date_str}')")
                    else:
                        print(f"BEFORE predicate: Empty date string for email from {email.envelope.get('from', 'unknown')} (date: '{date_str}')")
                        print(f"Subject: {email.envelope.get('subject', 'No Subject')}")
                return False
            
            # Try multiple date formats in order of preference
            email_date = None
            
            # Format 1: RFC 2822 with day of week and timezone
            try:
                email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                pass
            
            # Format 2: RFC 2822 with day of week, no timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
                except ValueError:
                    pass
            
            # Format 3: RFC 2822 without day of week, with timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %z")
                except ValueError:
                    pass
            
            # Format 4: RFC 2822 without day of week, no timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%d %b %Y %H:%M:%S")
                except ValueError:
                    pass
            
            # Format 5: Clean up common variations and try again
            if email_date is None:
                try:
                    # Remove extra text like "(GMT)" at the end
                    cleaned_date = date_str.split(' (')[0]  # Remove anything after " ("
                    # Replace "GMT" with "+0000" for timezone
                    cleaned_date = cleaned_date.replace(' GMT', ' +0000')
                    # Replace "-0000" with "+0000" (common Gmail variation)
                    cleaned_date = cleaned_date.replace(' -0000', ' +0000')
                    
                    # Try with day of week
                    try:
                        email_date = datetime.strptime(cleaned_date, "%a, %d %b %Y %H:%M:%S %z")
                    except ValueError:
                        # Try without day of week
                        email_date = datetime.strptime(cleaned_date, "%d %b %Y %H:%M:%S %z")
                except ValueError:
                    pass
            
            # Format 6: YYYY-MM-DD format (fallback)
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass
            
            if email_date is None:
                raise ValueError(f"Could not parse date: '{date_str}'")
            
            # Convert to naive datetime for comparison
            if email_date.tzinfo is not None:
                email_date = email_date.replace(tzinfo=None)
            
            return email_date < self.cutoff_date
        except ValueError as e:
            # If date parsing fails, exclude the email (fail safe)
            if self.verbose:
                print()
                print("===================")
                print(f"BEFORE predicate: Failed to parse date '{date_str}': {e}")
                print(f"From: {email.cleaned_sender()}")
                print(f"Subject: {email.envelope.get('subject', 'No Subject')}")
                print("---------------")
                print()
            return False
    
    def __repr__(self):
        return f"BEFORE('{self.date_str}')"


class AFTER(Predicate):
    """Filter for emails after a given date"""
    
    def __init__(self, date_str: str, mailbox=None):
        """
        Initialize with date string in YYYY-MM-DD format
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            mailbox: Reference to mailbox for verbose setting
        """
        self.date_str = date_str
        self.mailbox = mailbox
        # Validate date format immediately
        try:
            self.cutoff_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD format.") from e
    
    @property
    def verbose(self):
        """Get verbose setting from mailbox if available"""
        return getattr(self.mailbox, '_verbose', True) if self.mailbox else True
    
    def __call__(self, email: ParsedEmail) -> bool:
        """Return True if email date is after the cutoff date"""
        try:
            # Try multiple date formats that Gmail might return
            date_str = email["date"]
            
            # Handle empty date strings (likely chat messages or corrupted emails)
            if not date_str or date_str.strip() == '':
                # Check if this looks like a chat message
                message_id = email.envelope.get('message_id', '')
                if self.verbose:
                    if 'chat' in message_id.lower():
                        print(f"AFTER predicate: Skipping chat message from {email.envelope.get('from', 'unknown')}")
                    else:
                        print(f"AFTER predicate: Empty date string for email from {email.envelope.get('from', 'unknown')}")
                return False
            
            # Try multiple date formats in order of preference
            email_date = None
            
            # Format 1: RFC 2822 with day of week and timezone
            try:
                email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                pass
            
            # Format 2: RFC 2822 with day of week, no timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
                except ValueError:
                    pass
            
            # Format 3: RFC 2822 without day of week, with timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %z")
                except ValueError:
                    pass
            
            # Format 4: RFC 2822 without day of week, no timezone
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%d %b %Y %H:%M:%S")
                except ValueError:
                    pass
            
            # Format 5: Clean up common variations and try again
            if email_date is None:
                try:
                    # Remove extra text like "(GMT)" at the end
                    cleaned_date = date_str.split(' (')[0]  # Remove anything after " ("
                    # Replace "GMT" with "+0000" for timezone
                    cleaned_date = cleaned_date.replace(' GMT', ' +0000')
                    # Replace "-0000" with "+0000" (common Gmail variation)
                    cleaned_date = cleaned_date.replace(' -0000', ' +0000')
                    
                    # Try with day of week
                    try:
                        email_date = datetime.strptime(cleaned_date, "%a, %d %b %Y %H:%M:%S %z")
                    except ValueError:
                        # Try without day of week
                        email_date = datetime.strptime(cleaned_date, "%d %b %Y %H:%M:%S %z")
                except ValueError:
                    pass
            
            # Format 6: YYYY-MM-DD format (fallback)
            if email_date is None:
                try:
                    email_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass
            
            if email_date is None:
                raise ValueError(f"Could not parse date: '{date_str}'")
            
            # Convert to naive datetime for comparison
            if email_date.tzinfo is not None:
                email_date = email_date.replace(tzinfo=None)
            
            return email_date > self.cutoff_date
        except (ValueError, KeyError) as e:
            # If date parsing fails, exclude the email (fail safe)
            if self.verbose:
                print(f"AFTER predicate: Failed to parse date '{email.get('date', 'MISSING') if hasattr(email, 'get') else getattr(email, 'date', 'MISSING')}': {e}")
            return False
    
    def __repr__(self):
        return f"AFTER('{self.date_str}')"


class FROM(Predicate):
    """Filter for emails from a specific sender"""
    
    def __init__(self, sender, mailbox=None):
        """
        Initialize with sender string or OR object
        
        Args:
            sender: Sender email address/name to match, or OR object containing multiple senders
            mailbox: Reference to mailbox for verbose setting
        """
        if isinstance(sender, OR):
            self.senders = [s.lower() for s in sender.xs]
        else:
            self.senders = [sender.lower()]
        self.mailbox = mailbox
    
    @property
    def verbose(self):
        """Get verbose setting from mailbox if available"""
        return getattr(self.mailbox, '_verbose', True) if self.mailbox else True
    
    def __call__(self, email: ParsedEmail) -> bool:
        """Return True if email is from any of the specified senders"""
        try:
            # Check both From and Sender headers
            from_field = email["from"]
            sender_field = email["sender_header"]
            
            # Check if any of our target emails appears in either field
            for sender in self.senders:
                from_matches = sender in from_field.lower() if from_field else False
                sender_matches = sender in sender_field.lower() if sender_field else False
                
                if from_matches or sender_matches:
                    return True
            
            if self.verbose:
                print(f"FROM predicate: No match - looking for {self.senders} in from='{from_field}' sender='{sender_field}'")
            
            return False
        except (KeyError, AttributeError) as e:
            if self.verbose:
                print(f"FROM predicate: Error accessing sender fields: {e}")
            return False
    
    def __repr__(self):
        if len(self.senders) == 1:
            return f"FROM('{self.senders[0]}')"
        else:
            return f"FROM({self.senders})"


class TO(Predicate):
    """Filter for emails to a specific recipient"""
    
    def __init__(self, recipient, mailbox=None):
        """
        Initialize with recipient string or OR object
        
        Args:
            recipient: Recipient email address/name to match, or OR object containing multiple recipients
            mailbox: Reference to mailbox for verbose setting
        """
        if isinstance(recipient, OR):
            self.recipients = [r.lower() for r in recipient.xs]
        else:
            self.recipients = [recipient.lower()]
        self.mailbox = mailbox
    
    @property
    def verbose(self):
        """Get verbose setting from mailbox if available"""
        return getattr(self.mailbox, '_verbose', True) if self.mailbox else True
    
    def __call__(self, email: ParsedEmail) -> bool:
        """Return True if email is to any of the specified recipients"""
        try:
            # Check To, Cc, and Bcc headers
            to_field = email["to"]
            cc_field = email["cc"] if "cc" in email.envelope else ""
            bcc_field = email["bcc"] if "bcc" in email.envelope else ""
            
            # Check if any of our target emails appears in any recipient field
            for recipient in self.recipients:
                to_matches = recipient in to_field.lower() if to_field else False
                cc_matches = recipient in cc_field.lower() if cc_field else False
                bcc_matches = recipient in bcc_field.lower() if bcc_field else False
                
                if to_matches or cc_matches or bcc_matches:
                    return True
            
            if self.verbose:
                print(f"TO predicate: No match - looking for {self.recipients} in to='{to_field}' cc='{cc_field}' bcc='{bcc_field}'")
            
            return False
        except (KeyError, AttributeError) as e:
            if self.verbose:
                print(f"TO predicate: Error accessing recipient fields: {e}")
            return False
    
    def __repr__(self):
        if len(self.recipients) == 1:
            return f"TO('{self.recipients[0]}')"
        else:
            return f"TO({self.recipients})"


class INVOLVES(Predicate):
    """Filter for emails that involve a specific person (sender, recipient, cc, bcc, reply-to)"""
    
    def __init__(self, person, mailbox=None):
        """
        Initialize with person string or OR object
        
        Args:
            person: Person email address/name to match, or OR object containing multiple persons
            mailbox: Reference to mailbox for verbose setting
        """
        if isinstance(person, OR):
            self.persons = [p.lower() for p in person.xs]
        else:
            self.persons = [person.lower()]
        self.mailbox = mailbox
    
    @property
    def verbose(self):
        """Get verbose setting from mailbox if available"""
        return getattr(self.mailbox, '_verbose', True) if self.mailbox else True
    
    def __call__(self, email: ParsedEmail) -> bool:
        """Return True if person is involved in any capacity"""
        try:
            # Check all relevant fields: From, Sender, To, Cc, Bcc, Reply-To
            from_field = email["from"]
            sender_field = email["sender_header"]
            to_field = email["to"]
            cc_field = email["cc"] if "cc" in email.envelope else ""
            bcc_field = email["bcc"] if "bcc" in email.envelope else ""
            reply_to_field = email["reply_to"] if "reply_to" in email.envelope else ""
            
            # Check if any of our target persons appears in any field
            for person in self.persons:
                from_matches = person in from_field.lower() if from_field else False
                sender_matches = person in sender_field.lower() if sender_field else False
                to_matches = person in to_field.lower() if to_field else False
                cc_matches = person in cc_field.lower() if cc_field else False
                bcc_matches = person in bcc_field.lower() if bcc_field else False
                reply_to_matches = person in reply_to_field.lower() if reply_to_field else False
                
                if from_matches or sender_matches or to_matches or cc_matches or bcc_matches or reply_to_matches:
                    if self.verbose:
                        print(f"INVOLVES predicate: Found person '{person}' in email from {email.cleaned_sender()}")
                    return True
            
            if self.verbose:
                print(f"INVOLVES predicate: No match - looking for {self.persons} in from='{from_field}' sender='{sender_field}' to='{to_field}' cc='{cc_field}' bcc='{bcc_field}' reply_to='{reply_to_field}'")
            
            return False
        except (KeyError, AttributeError) as e:
            if self.verbose:
                print(f"INVOLVES predicate: Error accessing fields: {e}")
            return False
    
    def __repr__(self):
        if len(self.persons) == 1:
            return f"INVOLVES('{self.persons[0]}')"
        else:
            return f"INVOLVES({self.persons})" 