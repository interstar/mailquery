#!/usr/bin/env python3
"""
MailReader - Interactive email triage system

This module provides interactive email triage functionality that can work
with any email client (Gmail, IMAP, etc.).
"""

from .core import TriagePredicate

__all__ = [
    'TriagePredicate'
]
