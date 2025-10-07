#!/usr/bin/env python3
"""
Interactive Mail Reader Core - Simplified interactive email display and controls

This module provides a simplified interactive mail reader that acts as a predicate
and handles early termination internally.
"""

import sys
import termios
import tty
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich import box
from ..parsed_email import ParsedEmail


class TriagePredicate:
    """
    Interactive mail triage predicate that shows emails and gets user decisions.
    
    This class acts as a predicate filter that can be used with include_when().
    It handles early termination internally when the limit is reached or user quits.
    """
    
    def __init__(self, limit: int = 10):
        """
        Initialize the triage predicate.
        
        Args:
            limit: Maximum number of emails to process before stopping
        """
        self.limit = limit
        self.processed_count = 0
        self.console = Console()
        self.replies: List[Dict[str, Any]] = []  # Store replies for later processing
        
        # Terminal state management
        self.original_termios = None
        self.setup_terminal()
    
    def setup_terminal(self):
        """Setup terminal for raw input (no echo, immediate response)"""
        if sys.stdin.isatty():
            self.original_termios = termios.tcgetattr(sys.stdin.fileno())
    
    def restore_terminal(self):
        """Restore terminal to original state"""
        if self.original_termios:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.original_termios)
    
    def get_key(self) -> str:
        """Get a single keypress from the user"""
        if not sys.stdin.isatty():
            # Fallback for non-interactive environments
            return input().strip().lower()
        
        tty.setraw(sys.stdin.fileno())
        key = sys.stdin.read(1)
        self.restore_terminal()
        
        # Handle special keys
        if ord(key) == 27:  # ESC sequence
            key2 = sys.stdin.read(1)
            if key2 == '[':
                key3 = sys.stdin.read(1)
                if key3 == 'A':
                    return 'up'
                elif key3 == 'B':
                    return 'down'
        
        return key.lower()
    
    def format_email_display(self, email: ParsedEmail, scroll_offset: int = 0) -> Layout:
        """
        Create a formatted display of the email with headers and body.
        
        Args:
            email: The email to display
            scroll_offset: Number of lines to scroll down in the body
            
        Returns:
            Rich Layout object containing the formatted email
        """
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=8),
            Layout(name="body"),
            Layout(name="controls", size=3)
        )
        
        # Header section - just show the information directly
        header_text = Text()
        header_text.append("From: ", style="bold cyan")
        header_text.append(email.cleaned_sender(), style="white")
        header_text.append("\nSubject: ", style="bold cyan")
        header_text.append(email.envelope.get('subject', 'No Subject'), style="white")
        header_text.append("\nDate: ", style="bold cyan")
        header_text.append(email.envelope.get('date', 'No Date'), style="white")
        header_text.append("\nUID: ", style="bold cyan")
        header_text.append(email.uid, style="white")
        
        layout["header"].update(Panel(header_text, border_style="cyan"))
        
        # Body section with scrolling
        try:
            body_text = email.get_plain_text_body()
            if not body_text.strip():
                body_text = "[italic]No body content available[/italic]"
        except Exception as e:
            # Handle encoding errors more gracefully
            error_msg = str(e)
            if "unknown encoding" in error_msg.lower():
                body_text = "[red]Error loading body: Encoding issue - email may be corrupted[/red]"
            else:
                body_text = f"[red]Error loading body: {error_msg}[/red]"
        
        # Split body into lines for scrolling
        body_lines = body_text.split('\n')
        
        # Calculate visible lines (approximate)
        console_height = self.console.size.height
        visible_lines = max(1, console_height - 15)  # Reserve space for header and controls
        
        # Apply scroll offset
        start_line = scroll_offset
        end_line = start_line + visible_lines
        visible_body_lines = body_lines[start_line:end_line]
        
        # Add scroll indicators
        scroll_info = ""
        if len(body_lines) > visible_lines:
            total_lines = len(body_lines)
            scroll_info = f" (Line {start_line + 1}-{min(end_line, total_lines)} of {total_lines})"
        
        body_panel = Panel(
            '\n'.join(visible_body_lines),
            title=f"Email Body{scroll_info}",
            title_align="left",
            border_style="blue"
        )
        layout["body"].update(body_panel)
        
        # Controls section
        controls_text = Text()
        controls_text.append("Controls: ", style="bold")
        controls_text.append("[D]", style="bold red")
        controls_text.append("elete  ", style="white")
        controls_text.append("[Space]", style="bold green")
        controls_text.append("Keep  ", style="white")
        controls_text.append("[R]", style="bold blue")
        controls_text.append("eply  ", style="white")
        controls_text.append("[Q]", style="bold yellow")
        controls_text.append("uit  ", style="white")
        controls_text.append("[↑↓]", style="bold cyan")
        controls_text.append("Scroll", style="white")
        
        progress_text = Text()
        progress_text.append(f"Email {self.processed_count + 1} of {self.limit}", style="dim")
        
        controls_panel = Panel(
            Text.assemble(controls_text, "\n", progress_text),
            title="Controls",
            border_style="green"
        )
        layout["controls"].update(controls_panel)
        
        return layout
    
    def show_email_interactive(self, email: ParsedEmail) -> str:
        """
        Display email interactively and get user's decision.
        
        Args:
            email: The email to display
            
        Returns:
            User's choice: 'd' for delete, 'keep' for keep, 'r' for reply, 'q' for quit
        """
        scroll_offset = 0
        
        with Live(auto_refresh=False) as live:
            while True:
                # Update display
                layout = self.format_email_display(email, scroll_offset)
                live.update(layout)
                live.refresh()
                
                # Get user input
                key = self.get_key()
                
                if key == 'd':
                    return 'delete'
                elif key == ' ':  # Space
                    return 'keep'
                elif key == 'r':
                    return 'reply'
                elif key == 'q':
                    return 'quit'
                elif key == 'up':
                    scroll_offset = max(0, scroll_offset - 1)
                elif key == 'down':
                    scroll_offset += 1
                # Invalid key - continue loop
    
    def __call__(self, email: ParsedEmail) -> bool:
        """
        Process a single email interactively (predicate interface).
        
        This method is called for each email when used as a predicate filter.
        Raises StopIteration when user quits or limit is reached.
        
        Args:
            email: The email to process
            
        Returns:
            True if email should be deleted, False if it should be kept
            
        Raises:
            StopIteration: When user quits or limit is reached
        """
        # Check if we've hit our limit
        if self.processed_count >= self.limit:
            raise StopIteration(f"Reached limit of {self.limit} emails")
        
        try:
            # Show email and get user decision
            decision = self.show_email_interactive(email)
            
            if decision == 'delete':
                self.console.print(f"\n[red]Email {email.uid} marked for deletion[/red]")
                self.processed_count += 1
                return True
                
            elif decision == 'keep':
                self.console.print(f"\n[green]Email {email.uid} kept[/green]")
                self.processed_count += 1
                return False
                
            elif decision == 'reply':
                self.console.print(f"\n[blue]Email {email.uid} marked for reply (not implemented yet)[/blue]")
                # TODO: Implement reply functionality
                self.replies.append({
                    'original_email': email,
                    'reply_text': None  # Will be filled in later
                })
                self.processed_count += 1
                return False  # Don't delete emails we want to reply to
                
            elif decision == 'quit':
                self.console.print(f"\n[yellow]Quitting early after {self.processed_count} emails[/yellow]")
                raise StopIteration("User requested to quit")
                
        except KeyboardInterrupt:
            self.console.print(f"\n[yellow]Interrupted by user after {self.processed_count} emails[/yellow]")
            raise StopIteration("User interrupted")
        except StopIteration:
            # Re-raise StopIteration to allow it to propagate
            raise
        except Exception as e:
            self.console.print(f"\n[red]Error processing email {email.uid}: {str(e)}[/red]")
            return False
        
        return False
    
    def get_replies(self) -> List[Dict[str, Any]]:
        """
        Get the list of emails marked for reply.
        
        Returns:
            List of reply dictionaries with original_email and reply_text
        """
        return self.replies
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup terminal"""
        self.restore_terminal()

