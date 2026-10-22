"""
CAT Email Automation Subsystem.

Provides modular email workflow integrations:
- Search messages, retrieve threads, summarize conversations
- Draft replies, compose outgoing emails, organize messages
- Strict security & confirmation policy: SENDING or DELETING emails requires explicit user confirmation
- Safe logging: private email contents and auth tokens are never dumped to logs
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("cat.integrations.email")


@dataclass
class EmailMessage:
    id: str
    sender: str
    recipients: List[str]
    subject: str
    body: str
    date: float = field(default_factory=time.time)
    folder: str = "INBOX"
    read: bool = False
    thread_id: Optional[str] = None
    labels: List[str] = field(default_factory=list)


@dataclass
class EmailDraft:
    draft_id: str
    recipients: List[str]
    subject: str
    body: str
    in_reply_to: Optional[str] = None
    confirmed_by_user: bool = False
    created_at: float = field(default_factory=time.time)


class EmailAutomationService:
    """Modular email client with strict approval gating and thread intelligence."""

    def __init__(self):
        self._inbox: Dict[str, EmailMessage] = {}
        self._drafts: Dict[str, EmailDraft] = {}
        self._confirmation_required = True
        self._populate_mock_inbox()

    def _populate_mock_inbox(self):
        """Seed mock messages for testing and offline development."""
        m1 = EmailMessage(
            id="msg-101",
            sender="alex.lead@example.com",
            recipients=["user@example.com"],
            subject="Release 0.8.0 Feature Review",
            body="Hi team, please review the PR for the new agentic engine and confirm all tests pass before tomorrow's deploy.",
            thread_id="thread-release",
        )
        m2 = EmailMessage(
            id="msg-102",
            sender="ci-bot@example.com",
            recipients=["user@example.com"],
            subject="Build #412 PASSED",
            body="All unit and regression tests succeeded on branch main.",
            thread_id="thread-ci",
        )
        self._inbox[m1.id] = m1
        self._inbox[m2.id] = m2

    def search_messages(self, query: str, folder: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches messages by sender, subject, or body query."""
        q = query.lower().strip()
        results = []
        for msg in self._inbox.values():
            if folder and msg.folder.lower() != folder.lower():
                continue
            if q in msg.subject.lower() or q in msg.body.lower() or q in msg.sender.lower():
                results.append({
                    "id": msg.id,
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "snippet": msg.body[:120],
                    "folder": msg.folder,
                })
        return results

    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single email message."""
        msg = self._inbox.get(message_id)
        if not msg:
            return None
        msg.read = True
        return {
            "id": msg.id,
            "sender": msg.sender,
            "recipients": msg.recipients,
            "subject": msg.subject,
            "body": msg.body,
            "thread_id": msg.thread_id,
        }

    def summarize_thread(self, thread_id: str) -> Dict[str, Any]:
        """Summarizes an email thread and identifies action items."""
        thread_msgs = [m for m in self._inbox.values() if m.thread_id == thread_id]
        if not thread_msgs:
            return {"error": f"No messages found in thread '{thread_id}'."}

        snippets = [f"{m.sender}: {m.subject} — {m.body[:150]}" for m in thread_msgs]
        return {
            "thread_id": thread_id,
            "message_count": len(thread_msgs),
            "participants": list({m.sender for m in thread_msgs}),
            "overview": f"Thread regarding '{thread_msgs[0].subject}' across {len(thread_msgs)} messages.",
            "messages": snippets,
        }

    def create_draft(self, recipients: List[str], subject: str, body: str, in_reply_to: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new email draft for user review."""
        did = f"draft-{uuid.uuid4().hex[:8]}"
        draft = EmailDraft(
            draft_id=did,
            recipients=recipients,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
        )
        self._drafts[did] = draft
        return {
            "status": "draft_created",
            "draft_id": did,
            "recipients": recipients,
            "subject": subject,
            "preview": body[:200],
            "ready_to_send": False,
            "note": "Draft saved. Call send_email with user confirmation to transmit.",
        }

    def send_email(
        self,
        draft_id: str,
        user_confirmed: bool = False,
        permission_callback: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Transmits an email draft. Strictly enforces explicit confirmation."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return {"ok": False, "error": f"Draft '{draft_id}' not found."}

        confirmed = user_confirmed
        if not confirmed and permission_callback:
            confirmed = permission_callback()

        if not confirmed:
            return {
                "ok": False,
                "error": "ConfirmationRequired",
                "message": (
                    f"Action Refused: Sending email to {', '.join(draft.recipients)} requires "
                    f"explicit confirmation. Confirmation policy enforced."
                ),
                "draft_id": draft_id,
            }

        # Transmit (mocked / real backend)
        draft.confirmed_by_user = True
        return {
            "ok": True,
            "status": "sent",
            "draft_id": draft_id,
            "recipients": draft.recipients,
            "subject": draft.subject,
            "timestamp": time.time(),
        }


email_service = EmailAutomationService()
