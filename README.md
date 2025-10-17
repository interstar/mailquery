# 📬 MailQuery - Fluent Email Processing Library

![WARNING](warning.png)

WARNING

This is a library of code that can log into your Gmail account and delete your emails.

It was vibe coded with AI by some random guy on the internet who you don't know and have no reason to trust.

Furthermore ... it's way overpowered. And by that I mean, in one line of Python, you can connect to your Gmail account and delete EVERY EMAIL IN IT!

Don't believe me? Here's what you should NEVER type :

    Mailbox(my_gmail_client).delete()

That's the equivalent of `rm -rf /*` in your Unix file-system. Don't do it.

This library was designed to be overpowered because I needed a power-tool. 

I connect it to my Gmail account and regularly use it to delete emails. Or save and back them up locally. I trust it. And although it was "vibe-coded", it was under meticulous instruction. I'm actually pretty damned proud of the design and architecture of this library. Which I came up with, and the AI, to its credit, understood and implemented. I think this library has a good separation of concerns. It's insanely composable. And it's very easy to make large scale changes to your mailbox.

BUT ... I cannot emphasize enough that this is a dangerous weapon and if you are not confident you understand how to use it. Or aren't responsible enough to use it properly, DO NOT USE IT AT ALL.
 
 
You probably aren't stupid enough to call delete() on the raw Mailbox.

But you should be aware that if you type

    Mailbox(my_gmail_client).include_when(custom_filter).delete()
    
And your `custom_filter` function has a bug which matches every email in your mailbox, this will ALSO delete every email in your mailbox.

Similarly, if you write 

    Mailbox(my_gmail_client).from_("a").delete()
    
It's going to delete every email from someone who has "a" in either their name, or their email address.

So it's easy make big mistakes. THERE IS NO UNDO.

WITH GREAT POWER COMES GREAT RESPONSIBILITY

Read below for advice on how to use this library sensibly.

Anyway, that's why I've decided not to put this library on PyPI. At least for the moment. You'll have to download the repo from Github or Gitlab and install it locally. I won't tell you how to do that. If you can't figure it out yourself, you probably shouldn't be using this library anyway.

So having said all that ... welcome to MailQuery


## What is MailQuery?

I admit, I like jQuery. Not jQuery as a full web UI framework, but the notion of a simple, "fluent" interface for accessing something complicated like the DOM, that jQuery introduced me to.

Every now and then I need to do something with another complicated thing and a light-bulb goes off in my head and I think "I wish I had an xQuery for that."

I originally did it when I got bored with crawling around my file-system the old-fashioned way. And wrote https://github.com/interstar/FSQuery

Meanwhile, I've always hated Gmail filters. And increasingly I've been thinking about whether AI might finally help to get my aburdly cluttered Gmail inbox under control.

But then I realised I just wanted a better way to talk to my mailbox from Python. So I've been vibe-coding for a few days, and here's the result.

Here's how I can currently manage my Gmail account, in the REPL with a fluent interface and FP attitude.


Import from the library

    from mailquery import GmailClient, Mailbox, SQLiteStorage, OR, spit, HTMLPageBuilder, SenderCollector, EmailStatistics

Create the Gmail client. The credentials are in "credentials.json". Note the library also has a plain IMAP client

    client = GmailClient("credentials.json",allow_delete=True)

Create mailbox from the client. Filter for emails later than 1st August, 2025 that are from either one of hello@restofworld.org or ai.plus@axios. This is how you stack filters together. There are standard built in ones like from_, to, before, after, subject_contains etc. You can add as many as you like.

    news = Mailbox(client).after("2025-08-01").from_(OR("hello@restofworld.org","ai.plus@axios.com",))

There are also the two generic filters : include_when() and exclude_when()

These take "predicate" functions. That is, functions which map from an email object to a True/False value

Make sure you understand this concept clearly. "include_when()" means if the predicate returns True, then this filter allows the email through to the next stage "exclude_when()" means that if the predicate returns True, the mail is blocked from passing through to the next stage. But will pass through if the predicate returns False

OR is a special class that represents any of the arguments. from_(OR("hello@restofworld.org","ai.plus@axios.com")) matches emails from either of these two addresses.

The OR can handle as many values as you give it.

Anyway, after the last command, "news" now contains a mailbox with the after and from_ filters attached. 

But note that nothing has actually run yet. MailQuery is a pretty lazy library.

Let's just list the mails that match. verbose=False prints just the basic header, verbose=True would print a bunch of extra warnings and diagnostics.

    news.list_all(verbose=False)

This has now triggered the query to execute. It ran through the mailbox looking for emails that matched the filters. 

Note that all the filtering is done on the client. Which means downloading all the email headers to test them against the criteria. BUT as an optimisation for Gmail, both the after() filter and the from_() filter get turned into Gmail server-side filters by our GmailClient. This makes things MUCH faster, but is completely transparent to the user. You don't need to know anything about Gmail to get this benefit. It's entirely handled by the Gmail client you used when you created the Mailbox

If you aren't using Gmail, or a server where we can use such optmisations, then MailQuery will just chug along, slowly, downloading all the mail 
and filtering it locally. It's much slower, but it works identically

Remember I said MailQuery was lazy?

At this point the mail headers have been downloaded and cached. If we run list_all() again, we'll just pull them out of the local cache.

However the bodies of the emails are not yet downloaded. And won't be until something calls a get body or get html type function on them.
body_contains() is one such filter. 

Once bodies are downloaded, the Email objects in the mailbox will cache that too.

Perhaps we want to store the emails that matched

    storage = SQLiteStorage("newsletters.db")
    news.store_local(storage)

And that's it, the emails are stored in the database. We can now delete them from the gmail account

    news.delete()

But wait, there's more! These newsletters have all their useful stuff in an HTML attachment field. That's a pain. We can extract the text from the html with Beautiful Soup. But we don't really want to hardwire Beautiful Soup into our mail library do we?

We would like a way to optionally process a field in the mail record into some further information. 

We also want to store this extra information in the email.

Fortunately, MailQuery has a mechanism for that : "add_attribute(att_name,fn)" 

`add_attribute()` works like a filter. But it always returns True. It never removes anything from the mailbox.

What it DOES do is transform the email in some way. The function `fn` needs to be a function that maps emails to some other value. `att_name` is a string . The `add_attribute` filter calls f on each mail passing through, and stores the result in an extra attribute under the name `att_name`

For example, we can use Beautiful Soup to extract text from the html like this.

```python
def extract_html_text(email):
    try:
        html_content = email.get_html()
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        return ""
    except Exception as e:
        print(f"Error extracting HTML text: {e}")
        return ""
```

Now we can add this as a new attribute

    news.add_attribute("html_as_text",extract_html_text).store_local(storage)

Not only does the add_attribute add the extra attribute to all the emails. It also registers the extra attribute name in the Mailbox

Then when we call store_local(storage), storage finds out about the extra attribute name and creates an extra column for it in the SQLite database


**But wait there's MORE ....**

We can filter. We can "map" mails to other values? Why not have trifecta and add some kind of fold or reduce?

list_all(), delete() and store_local() are three functions we can add at the end of the pipeline to do something with our email

But we also have a generic way to roll them up to get some kind of aggregate value out of them.

Unsurprisingly it's called reduce_all(reducer)
 
Here's what a Reducer has to look like

```python
class Reducer :
    def init_value(self) : # returns initial value
    def fold(self, next:ParsedEmail)  : # folds the next email into its internal accumulator 
    def final(self) : return the final value of the accumulator
```

Let's use one to count the emails in our mailbox

```python
class Counter(Reducer):
    
    def init_value(self):
        self.count = 0
    
    def fold(self, email: ParsedEmail):
        self.count += 1
    
    def final(self) -> int:
        return self.count


mails.reduce_all(Counter())
```

Something more useful is to discover all the unique email addresses in a matching mail set

```python
class SenderCollector(Reducer):
    """Collect all unique sender email addresses"""
    
    def init_value(self):
        self.senders: Set[str] = set()
    
    def fold(self, email: ParsedEmail):
        self.senders.add(email.envelope['from'])
    
    def final(self) -> List[str]:
        return list(self.senders)

mails.reduce_all(SenderCollector())
```

I hope you see how this thing starts to stack up

Apart from the delete() ... WHICH IS BLOODY DANGEROUS ... BE VERY CAREFUL WITH IT

Apart from the delete() nothing else changes your mailbox. And everything gets cached locally

So once you've run a mailbox filtering once, whether to print or store, runnning these further reducers will just iterate through mails in memory

MailQuery is powerful for any automated email application. But my goal is to be able to use it in Python REPL to interact with my Gmail dynamically but programatically.

One thing missing from all the automation above is a way to bring the human back into the loop. Sometimes even I can't think of a criterion for deleting or saving emails except by reading the mail and making a personal decision

Never fear, we can bring the human back simply by invoking human()

    mails.subject_contains("important").human().delete()

human() works like any other filter on the email chain. Except it turns the terminal into an interactive window where a human user can review and decide the fate of an email. The human can type "D" or SPACE. "D" is obviously intended to signal "delete this email". In fact, because human() is just another filter stage, what it ACTUALLY does is return a True, indicating that the email is to pass through to the next stage of the filter chain. SPACE on the other hand returns False, removing the email from the filter chain. These obviously only work as intended if the human() is slotted into a chain which ends at a delete(). You could obviously use the human() elsewhere, but you are likely to confuse yourself or your users. Again, MailQuery is a dangerous power-tool which will hurt you if you are not incredibly careful.
 



## AI Written Overview

**MailQuery** is a Python library that provides a jQuery-like fluent interface for email filtering, processing, and analysis. It connects to various email sources (Gmail API, IMAP servers, mbox files), downloads emails, and allows you to filter, analyze, and process them using an intuitive method-chaining API.


---

## 🧱 Architecture

- **`GmailClient`**: Gmail API client with OAuth2 authentication and server-side optimization
- **`RealImapClient`**: Real IMAP implementation using `imaplib`
- **`DummyClient`**: Stub client for testing and development
- **`MboxClient`**: Client for reading mbox format email files
- **`ParsedEmail`**: Lazily fetches and parses email metadata and body on demand
- **`Mailbox`**: Provides a jQuery-like fluent interface to filter and process emails
- **`Predicate`**: Filter logic with server-side optimization capabilities
- **`Reducer`**: Processing and aggregation framework for email analysis
- **`StorageBackend`**: Pluggable storage systems (SQLite, Maildir, Mbox)

---

## ✅ Features Implemented

### **Core Functionality**
- ✅ **Multiple email sources**: Gmail API, IMAP servers, mbox files
- ✅ **Gmail API integration** with OAuth2 authentication and server-side optimization
- ✅ **Lazy fetching** of message bodies for performance optimization
- ✅ **Fluent interface** via `Mailbox()` with method chaining
- ✅ **Comprehensive filtering** with multiple filter types
- ✅ **Interactive email triage** with human-in-the-loop processing
- ✅ **Full test suite** with unit tests for all components

### **Fluent Interface Features**
- ✅ **Method chaining**: `mails.from_("spotify").subject_contains("likes").list_all()`
- ✅ **Multiple filter types**:
  - `from_(email)` - Filter by sender (matches name, email, or domain)
  - `to(email)` - Filter by recipient
  - `involves(email)` - Filter by any involvement (sender, recipient, cc, bcc, reply-to)
  - `reply_to(email)` - Filter by Reply-To address
  - `subject_contains(text)` - Filter by subject content
  - `body_contains(text)` - Filter by body content
  - `before(date)` / `after(date)` - Filter by date
  - `older_than(days)` / `younger_than(days)` - Filter by relative date
- ✅ **Interactive triage**: `human(limit)` - Interactive email review and decision making
- ✅ **Smart parsing** of sender components (name vs email)
- ✅ **Case-insensitive matching** for all filters
- ✅ **Empty string handling** for all filters
- ✅ **Action methods**: `delete()`, `list_all()`, `reduce_all()`, `store_local()`

### **Email Parsing Features**
- ✅ **Header parsing** (From, To, Subject, Date, Reply-To, Message-ID)
- ✅ **Body parsing** (text and HTML with automatic HTML-to-text conversion)
- ✅ **Sender component parsing** (name vs email address)
- ✅ **Cleaned sender display** for user-friendly output
- ✅ **Lazy body loading** with memoization
- ✅ **Robust encoding handling** for malformed emails

### **Testing & Quality**
- ✅ **Unit tests** for all filter types and edge cases
- ✅ **Mock-based testing** for reliable test execution
- ✅ **Error handling** for connection issues
- ✅ **Debug output** for troubleshooting
- ✅ **Interactive triage testing** with terminal UI

---

## 🧪 Usage Examples

### **Basic Filtering**
```python
from mailquery import Mailbox, GmailClient

# Connect to Gmail
client = GmailClient("credentials.json", batch_size=500, fetch_limit=1000)
mails = Mailbox(client)

# List all emails
mails.list_all()

# Filter by sender
mails.from_("spotify").list_all()

# Filter by email domain
mails.from_("spotify.com").list_all()

# Filter by subject
mails.subject_contains("likes").list_all()

# Complex filtering
mails.from_("soundcloud").subject_contains("notification").list_all(limit=5)
```

### **Advanced Filtering**
```python
# Chain multiple filters
mails.from_("spotify").reply_to("noreply").subject_contains("playlist").list_all()

# Filter by date
mails.after("2023-01-01").before("2023-12-31").list_all()

# Filter by relative date
mails.older_than(7).younger_than(30).list_all()

# Filter by body content
mails.body_contains("unsubscribe").list_all()

# Interactive triage
mails.from_("newsletters").human(10).delete()

# Find emails with empty headers
mails.reply_to("").list_all()
```

### **Actions & Analysis**
```python
# Delete matching emails
mails.from_("spam@example.com").delete()

# Store locally
mails.subject_contains("newsletter").store_local(storage)

# Generate statistics
stats = mails.reduce_all(EmailStatistics())
print(f"Total emails: {stats['total_emails']}")

# Create HTML report
html_report = mails.from_("support@example.com").reduce_all(HTMLPageBuilder())
```

### **Multiple Email Sources**
```python
# Gmail API (OAuth2)
client = GmailClient("credentials.json", batch_size=500, fetch_limit=1000)

# IMAP Server
from mailquery import RealImapClient
client = RealImapClient(credentials)

# Mbox files (for old email archives)
from mailquery import MboxClient
client = MboxClient("emails.mbox", verbose=True)

# Testing
from mailquery import DummyClient
client = DummyClient("stub-credentials")
```

---

## 🔜 Outstanding Work

### **High Priority**
- **Reply functionality** - Implement reply feature in interactive triage
- **Mbox deletion** - Implement message deletion for mbox files
- **Gmail threads** - Support for Gmail conversation threading
- **Advanced filtering** - Regex support, complex date ranges
 

---

## 🚀 Getting Started

### **Prerequisites**
```bash
pip install -r requirements.txt
```

### **Quick Start**
```python
from mailquery import Mailbox, GmailClient

# Connect to Gmail
client = GmailClient("credentials.json")
mails = Mailbox(client)

# List recent emails
mails.list_all(limit=10)

# Interactive triage
mails.from_("newsletters").human(5).delete()
```

### **For Gmail Users**
1. Enable 2-Factor Authentication
2. Generate an App Password or use OAuth2
3. Download credentials.json from Google Cloud Console

---

## 🧾 License

GPL3 - Gnu Public License
