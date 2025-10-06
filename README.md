
# 📬 MailQuery - Fluent Email Processing Library

## Overview

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
