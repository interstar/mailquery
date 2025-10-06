from typing import Iterable, Callable, List, Any
from abc import ABC, abstractmethod
from .parsed_email import ParsedEmail
from .predicates import BEFORE, AFTER, FROM, TO, INVOLVES, OR
from datetime import datetime, timedelta


class EmailIterator:
    """
    Context manager for iterating over emails with automatic StopIteration handling.
    
    This encapsulates the pattern of looping through a generator and handling
    StopIteration exceptions cleanly, eliminating the need for try/except blocks
    in every method that iterates over emails.
    """
    
    def __init__(self, mailbox, verbose=True):
        self.mailbox = mailbox
        self.verbose = verbose
        self.count = 0
        self._iterator = None
        
    def __enter__(self):
        """Start the iteration context"""
        self._iterator = iter(self.mailbox._get_emails())
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Handle StopIteration and other exceptions"""
        if exc_type is StopIteration:
            if self.verbose:
                print(f"Stopped early: {exc_val}")
            return True  # Suppress the StopIteration
        return False  # Let other exceptions propagate
        
    def __iter__(self):
        """Return self as an iterator"""
        return self
        
    def __next__(self):
        """Get the next email, applying filters and handling StopIteration"""
        while True:
            try:
                email = next(self._iterator)
                # Apply filters - this may raise StopIteration
                if not self.mailbox._apply_filters(email):
                    continue  # Skip this email, try the next one
                self.count += 1
                return email
            except StopIteration:
                # Re-raise StopIteration to be handled by __exit__
                raise


def INCLUDE_OR(pred):
    def f(self, arg):
        if not isinstance(arg, OR):
            return self.include_when(lambda e: pred(self, arg, e))
        else:
            return self.include_when(lambda e: any(
                pred(self, x, e) for x in arg.xs
            ))
    return f


def EXCLUDE_OR(pred):
    def f(self, arg):
        if not isinstance(arg, OR):
            return self.exclude_when(lambda e: pred(arg, e))
        else:
            return self.exclude_when(lambda e: any(
                pred(x, e) for x in arg.xs
            ))
    return f


class FilterableMailbox(ABC):
    """Abstract base class for mailboxes that support filtering"""
    
    def __init__(self):
        self._filters: List[Callable[[ParsedEmail], bool]] = []
        self._extra_attributes = []  # Track extra attribute keys being added
    
    def include_when(self, predicate: Callable[[ParsedEmail], bool]):
        """Add a filter that includes emails when predicate returns True"""
        self._filters.append(predicate)
        return self

    def exclude_when(self, predicate: Callable[[ParsedEmail], bool]):
        """Add a filter that excludes emails when predicate returns True"""
        self._filters.append(lambda m: not predicate(m))
        return self

    def from_(self, sender, verbose: bool = True):
        """Filter by sender (server-side optimized)"""
        return self.include_when(FROM(sender, self))

    @INCLUDE_OR
    def body_contains(self, text: str, e):
        """Filter by text in email body"""
        return text.lower() in e.get_plain_text_body().lower()

    @INCLUDE_OR
    def subject_contains(self, text: str, e):
        """Filter by text in email subject"""
        return e["subject"] and text.lower() in e["subject"].lower()

    @INCLUDE_OR
    def reply_to(self, email_address: str, e):
        """Filter by Reply-To email address"""
        return e["reply_to"] and email_address.lower() in e["reply_to"].lower()

    def to(self, recipient, verbose: bool = True):
        """Filter by To email address (server-side optimized)"""
        return self.include_when(TO(recipient, self))

    def involves(self, person, verbose: bool = True):
        """Filter by person involved in any capacity (sender, recipient, cc, bcc, reply-to)"""
        return self.include_when(INVOLVES(person, self))

    def before(self, date_str: str, verbose: bool = True):
        """Filter emails before a given date (YYYY-MM-DD format)"""
        return self.include_when(BEFORE(date_str, self))

    def after(self, date_str: str, verbose: bool = True):
        """Filter emails after a given date (YYYY-MM-DD format)"""
        return self.include_when(AFTER(date_str, self))

    def older_than(self, days: int, verbose: bool = True):
        """Filter emails older than a given number of days"""
        # Calculate cutoff date
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        # Format as YYYY-MM-DD for BEFORE predicate
        date_str = cutoff_date.strftime("%Y-%m-%d")
        return self.include_when(BEFORE(date_str, self))

    def younger_than(self, days: int, verbose: bool = True):
        """Filter emails newer than a given number of days"""
        # Calculate cutoff date
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        # Format as YYYY-MM-DD for AFTER predicate
        date_str = cutoff_date.strftime("%Y-%m-%d")
        return self.include_when(AFTER(date_str, self))

    def limit(self, max_count: int):
        """
        Limit the number of emails that pass through this filter.
        
        This filter counts emails that pass through and raises StopIteration
        after the specified limit is reached. It can be chained with other filters.
        
        Args:
            max_count: Maximum number of emails to allow through
            
        Returns:
            self for method chaining
        """
        # Create a closure to capture the count
        count = [0]  # Use list to make it mutable in closure
        
        def limit_filter(email):
            count[0] += 1
            if count[0] > max_count:
                raise StopIteration(f"Limit of {max_count} emails reached")
            return True  # Always include the email up to the limit
        
        self._filters.append(limit_filter)
        return self

    def subquery(self) -> 'SubqueryMailbox':
        """Create a subquery that filters over this mailbox's results"""
        return SubqueryMailbox(self)

    def add_attribute(self, key: str, func: Callable[['ParsedEmail'], Any]):
        """
        Add a computed attribute to emails as they pass through.
        
        Args:
            key: The key to store the computed value under in email.extra_attributes
            func: Function that takes a ParsedEmail and returns a value
            
        Returns:
            self for method chaining
        """
        # Track the attribute key in the mailbox
        if key not in self._extra_attributes:
            self._extra_attributes.append(key)
        
        # Add a filter that always returns True but modifies the email
        def attribute_filter(email):
            email.extra_attributes[key] = func(email)
            return True  # Always include the email
        
        self._filters.append(attribute_filter)
        return self

    def show_attributes(self):
        """
        Display the extra attributes that have been added to emails.
        
        Returns:
            self for method chaining
        """
        if self._extra_attributes:
            print(f"Added attributes: {', '.join(self._extra_attributes)}")
        else:
            print("No extra attributes added")
        return self

    def human(self, limit: int = 10):
        """
        Invoke human interactive triage on the filtered emails.
        
        This method shows emails one by one and allows the user to decide
        which ones to delete, keep, or reply to.
        
        Args:
            limit: Maximum number of emails to show for triage
            
        Returns:
            self for method chaining (emails marked for deletion will be deleted)
        """
        from .mailreader.core import TriagePredicate
        return self.include_when(TriagePredicate(limit))

    def _apply_filters(self, email):
        """Apply all filters to an email"""
        if not self._filters:
            return True
        
        # Apply filters - StopIteration will bubble up naturally
        for filter_func in self._filters:
            result = filter_func(email)
            if not result:
                return False
        
        return True

    @abstractmethod
    def fetch(self) -> Iterable[ParsedEmail]:
        """Apply filters and return matching emails"""
        pass

    @abstractmethod
    def _get_client(self):
        """Get the client for operations like delete"""
        pass

    @abstractmethod
    def _set_verbose(self, verbose: bool):
        """Set verbose mode for this mailbox"""
        pass

    def __iter__(self):
        """Allow iteration over filtered emails with transparent StopIteration handling"""
        def safe_generator():
            try:
                for email in self.fetch():
                    yield email
            except RuntimeError as e:
                # Check if this RuntimeError is wrapping a StopIteration
                if "StopIteration" in str(e):
                    # Just stop yielding - this is normal behavior
                    pass
                else:
                    # Re-raise if it's a different RuntimeError
                    raise
        return safe_generator()

    def clear_cache(self):
        """Clear the email cache"""
        # Default implementation - subclasses can override
        pass

    def delete(self, verbose=True):
        """Delete all matching emails from the server"""
        deleted_count = 0
        
        with EmailIterator(self, verbose) as iterator:
            for email in iterator:
                if verbose:
                    print("Deleting : %s" % email.envelope)
                
                success = self._get_client().delete_message(email.uid)
                if success:
                    # Mark as deleted on server instead of removing from cache
                    email.deleted_on_server = True
                    deleted_count += 1
        
        if verbose:
            print(f"Successfully deleted {deleted_count} emails")
        
        return self

    def list_all(self, limit: int = None, verbose: bool = True):
        """List all matching emails with formatted output"""
        # Set verbose mode for this operation
        self._set_verbose(verbose)
        
        count = 0
        if verbose:
            print("Starting list_all() iteration...")
        
        with EmailIterator(self, verbose) as iterator:
            for email in iterator:
                count += 1
                if verbose:
                    print(f"Processing email {count}...")
                
                # Get cleaned sender name
                sender = email.cleaned_sender()
                
                # Print email info
                print(f"{count:3d}. {sender}")
                print(f"     Subject: {email['subject']}")
                print(f"     Date: {email['date']}")
                print()
                
                # Check limit
                if limit and count >= limit:
                    break
        
        if verbose:
            print(f"Total emails: {count}")
        return self

    def store_local(self, storage_backend):
        """Store emails locally using the provided storage backend"""
        # Setup the storage backend with mailbox information
        storage_backend.setup(self)
        
        stored_count = 0
        total_count = 0
        
        with EmailIterator(self, verbose=True) as iterator:
            for email in iterator:
                total_count += 1
                if storage_backend.store_email(email):
                    stored_count += 1
        
        print(f"Stored {stored_count}/{total_count} emails successfully using\n {storage_backend.describe()}")
        
        # Clean up storage backend
        storage_backend.close()
        
        return self

    def reduce_all(self, reducer, verbose: bool = True):
        """
        Apply a Reducer object to all matching emails.
        
        Args:
            reducer: A Reducer object that implements init_value(), fold(), and final()
            verbose: Whether to print progress information
            
        Returns:
            The final result from reducer.final()
        """
        # Set verbose mode for this operation
        self._set_verbose(verbose)
        
        if verbose:
            print("Starting reduce_all() iteration...")
        
        # Initialize the reducer
        reducer.init_value()
        if verbose:
            print("Reducer initialized")
        
        # Process all emails
        count = 0
        with EmailIterator(self, verbose) as iterator:
            for email in iterator:
                count += 1
                if verbose:
                    print(f"Processing email {count}...")
                
                reducer.fold(email)
        
        if verbose:
            print(f"Reduction completed. Processed {count} emails.")
        
        # Get final result
        result = reducer.final()
        if verbose:
            print(f"Final result: {result}")
        
        return result


class Mailbox(FilterableMailbox):
    def __init__(self, client):
        """Initialize a Mailbox with a client"""
        super().__init__()
        self.client = client
        self._cached_emails = {}  # Cache for ParsedEmail objects
        self._message_ids_fetched = False  # Track if we've already fetched message IDs
        self._verbose = True  # Default verbose setting

    def fetch(self) -> Iterable[ParsedEmail]:
        """Apply filters and return matching emails"""
        # Get emails from cache or client
        emails = self._get_emails()
        
        for email in emails:
            # Apply all filters - all must pass
            if not self._apply_filters(email):
                continue
            
            yield email
    
    def _get_emails(self) -> Iterable[ParsedEmail]:
        """Get emails from cache or fetch from client"""
        if self._message_ids_fetched:
            # Use cached emails
            return self._cached_emails.values()
        else:
            # Create a generator that caches emails as they're yielded
            def cached_generator():
                for email in self.client.list_messages(filters=self._filters, verbose=self._verbose):
                    self._cached_emails[email.uid] = email
                    yield email
                self._message_ids_fetched = True
            return cached_generator()

    def _get_client(self):
        """Get the client for operations like delete"""
        return self.client

    def _set_verbose(self, verbose: bool):
        """Set verbose mode for this mailbox"""
        self._verbose = verbose

    def clear_cache(self):
        """Clear the email cache"""
        self._cached_emails.clear()
        self._message_ids_fetched = False
        print("Email cache cleared")


class SubqueryMailbox(FilterableMailbox):
    """A mailbox that filters over another mailbox's results"""
    
    def __init__(self, parent_mailbox):
        """Initialize with a reference to the parent mailbox"""
        super().__init__()
        self.parent = parent_mailbox

    def fetch(self) -> Iterable[ParsedEmail]:
        """Apply filters to parent's results and return matching emails"""
        for email in self.parent.fetch():
            # Apply all filters - all must pass
            if not self._apply_filters(email):
                continue
            
            yield email

    def _get_client(self):
        """Get the client for operations like delete"""
        return self.parent.client

    def _set_verbose(self, verbose: bool):
        """Set verbose mode for this mailbox"""
        self.parent._verbose = verbose

    def clear_cache(self):
        """Clear the parent's email cache"""
        self.parent.clear_cache()
