"""Demo command that renders sample AI tool-call approval cards."""
import asyncio
import logging
import uuid

from jinja2 import Environment, FileSystemLoader
from symphony.bdk.core.activity.command import CommandContext, SlashCommandActivity
from symphony.bdk.core.activity.form import FormReplyActivity, FormReplyContext
from symphony.bdk.core.service.message.message_service import MessageService


_templates = Environment(loader=FileSystemLoader("resources/templates"), autoescape=True)
CALL_APPROVAL_FORM_ID = "call-approval-form"
logger = logging.getLogger(__name__)


CALL_APPROVAL_EXAMPLES = [
    {
        "agent": "Melody",
        "provider": "Jira",
        "tool": "searchJiraIssuesUsingJql",
        "safety_level": "readOnly",
        "summary": "Searches Jira for open high-priority bugs assigned to Sprint 24. Reads issue metadata without modifying records.",
        "inputs": '{"jql": "project = CORE AND priority = High AND statusCategory != Done AND sprint = 24"}',
        "accent": "#1687F8",
        "tone": "info",
    },
    {
        "agent": "Melody",
        "provider": "Salesforce",
        "tool": "updateAccountDetails",
        "safety_level": "createOrUpdate",
        "summary": "Updates the primary contact phone number and renewal date for Acme Corp. Modifies existing CRM fields.",
        "inputs": '{"account": "Acme Corp", "primary_contact_phone": "+1 415 555 0134", "renewal_date": "2026-12-31"}',
        "accent": "#1687F8",
        "tone": "info",
    },
    {
        "agent": "Melody",
        "provider": "PostgreSQL · Production",
        "tool": "deleteDatabaseTable",
        "safety_level": "destructive",
        "summary": "Irreversibly drops the temporary staging table `temp_staging_logs_v2` from the production cluster. This cannot be undone.",
        "inputs": '{"database": "production", "schema": "public", "table": "temp_staging_logs_v2"}',
        "accent": "#F28C28",
        "tone": "warning",
    },
    {
        "agent": "Melody",
        "provider": "Unverified provider",
        "tool": "executeUserScript",
        "safety_level": "unknown",
        "summary": "Runs an unverified user-provided Python script on a sandbox node. The safety impact cannot be determined before execution.",
        "inputs": '{"script": "<user-provided Python script>", "target": "sandbox-node-03"}',
        "accent": "#F28C28",
        "tone": "warning",
    },
]


class CallApprovalCommandActivity(SlashCommandActivity):
    """``/call-approval`` - posts four sample tool-call approval scenarios."""

    def __init__(self, messages: MessageService, registry):
        self._messages = messages
        self._registry = registry
        super().__init__("/call-approval", True, self._on_command)

    async def _on_command(self, context: CommandContext):
        template = _templates.get_template("call_approval.jinja2")
        for index, example in enumerate(CALL_APPROVAL_EXAMPLES):
            approval_id = uuid.uuid4().hex
            self._registry.add(approval_id, example)
            message_mml = template.render(
                item=example,
                approval_id=approval_id,
                decision=None,
            )
            logger.debug("Sending /call-approval MessageML (stream_id=%s):\n%s", context.stream_id, message_mml)
            await self._messages.send_message(context.stream_id, message_mml)
            if index < len(CALL_APPROVAL_EXAMPLES) - 1:
                await asyncio.sleep(4)


class CallApprovalRegistry:
    """Tracks demo approval cards until a decision is submitted."""

    def __init__(self):
        self._approvals = {}

    def add(self, approval_id: str, item: dict) -> None:
        self._approvals[approval_id] = {"item": item, "decision": None}

    def get(self, approval_id: str):
        return self._approvals.get(approval_id)

    def decide(self, approval_id: str, decision: str) -> None:
        approval = self._approvals.get(approval_id)
        if approval is not None:
            approval["decision"] = decision


class CallApprovalFormReplyActivity(FormReplyActivity):
    """Records the selected demo decision and replaces the card with its outcome."""

    DECISIONS = {
        "accept": "Accepted",
        "accept_session": "Accepted for this session",
        "deny": "Denied",
    }

    def __init__(self, messages: MessageService, registry: CallApprovalRegistry):
        self._messages = messages
        self._registry = registry

    def matches(self, context: FormReplyContext) -> bool:
        return context.form_id == CALL_APPROVAL_FORM_ID

    async def on_activity(self, context: FormReplyContext):
        approval_id = context.get_form_value("approval_id")
        approval = self._registry.get(approval_id)
        action = context.get_form_value("action")
        decision = self.DECISIONS.get(action)
        if approval is None or decision is None or approval["decision"] is not None:
            return

        self._registry.decide(approval_id, decision)
        message_mml = _templates.get_template("call_approval_result.jinja2").render(
            item=approval["item"],
            decision=decision,
        )
        logger.debug(
            "Updating /call-approval decision MessageML (stream_id=%s, decision=%s):\n%s",
            context.source_event.stream.stream_id,
            decision,
            message_mml,
        )
        await self._messages.update_message(
            context.source_event.stream.stream_id,
            context.source_event.form_message_id,
            message_mml,
        )
