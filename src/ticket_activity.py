"""Demo of a Message Rate Control ticket with a "Help" escalation flow.

Flow:
  1. ``/ticket`` posts a sample rate-control ticket with a countdown. If none of
     the decision buttons are clicked within :data:`TICKET_EXPIRY_SECONDS`, the
     ticket is marked expired and its action buttons are removed.
  2. Clicking "Help!" stops the countdown (this is the one action that does not
     resolve the ticket) and swaps the message for a help form: a topic
     dropdown, a free-text box, and the original ticket for context.
  3. Submitting the help form creates a dedicated incident room named after the
     ticket, adds the requester to it, and posts a branded welcome message.
     "Cancel" instead restores the ticket card and resumes the countdown from
     where it left off.
"""
import asyncio
import logging

from jinja2 import Environment, FileSystemLoader
from symphony.bdk.core.activity.command import CommandContext, SlashCommandActivity
from symphony.bdk.core.activity.form import FormReplyActivity, FormReplyContext
from symphony.bdk.core.service.message.message_service import MessageService
from symphony.bdk.core.service.stream.stream_service import StreamService
from symphony.bdk.gen.pod_model.v3_room_attributes import V3RoomAttributes

from .ticket_service import (
    COUNTDOWN_TICK_SECONDS,
    DECISION_ACTIONS,
    HELP_TOPICS,
    TICKET_EXPIRY_SECONDS,
    Ticket,
    TicketRegistry,
    generate_ticket_fields,
    generate_ticket_id,
)

logger = logging.getLogger(__name__)

TICKET_FORM_ID = "rate-control-ticket"
HELP_FORM_ID = "rate-control-help"

_HELP_TOPIC_LABELS = dict(HELP_TOPICS)

_templates = Environment(loader=FileSystemLoader("resources/templates"), autoescape=True)


def _render_ticket(ticket: Ticket, expired: bool = False, resolved_label: str = None, rationale: str = None) -> str:
    template = _templates.get_template("ticket.jinja2")
    return template.render(
        **ticket.as_template_context(),
        expired=expired,
        resolved_label=resolved_label,
        rationale=rationale,
        TICKET_EXPIRY_SECONDS=TICKET_EXPIRY_SECONDS,
    )


def _render_help_form(ticket: Ticket) -> str:
    template = _templates.get_template("ticket_help_form.jinja2")
    return template.render(**ticket.as_template_context(), help_topics=HELP_TOPICS)


class TicketCommandActivity(SlashCommandActivity):
    """``/ticket`` - raises a sample Message Rate Control ticket to demo the Help flow."""

    def __init__(self, messages: MessageService, registry: TicketRegistry):
        super().__init__("/ticket", True, self._on_ticket_command)
        self._messages = messages
        self._registry = registry

    async def _on_ticket_command(self, context: CommandContext):
        fields = generate_ticket_fields()
        ticket = Ticket(ticket_id=generate_ticket_id(), stream_id=context.stream_id, message_id="", **fields)

        sent = await self._messages.send_message(context.stream_id, _render_ticket(ticket))
        ticket.message_id = sent.message_id
        self._registry.add(ticket)
        self.start_countdown(ticket)

    def start_countdown(self, ticket: Ticket) -> None:
        ticket.timer_task = asyncio.create_task(self._run_countdown(ticket))

    async def _run_countdown(self, ticket: Ticket) -> None:
        try:
            while ticket.remaining_seconds > 0:
                await asyncio.sleep(COUNTDOWN_TICK_SECONDS)
                ticket.remaining_seconds = max(0, ticket.remaining_seconds - COUNTDOWN_TICK_SECONDS)
                expired = ticket.remaining_seconds <= 0
                if expired:
                    ticket.status = "expired"
                try:
                    updated = await self._messages.update_message(ticket.stream_id, ticket.message_id, _render_ticket(ticket, expired=expired))
                    # Each update replaces the message with a new one under a new id - the next
                    # update must target that new id, not the one we started the countdown with.
                    ticket.message_id = updated.message_id
                except Exception:
                    # A single failed tick (e.g. a transient network blip) must not kill the
                    # countdown - log it and keep trying on the next tick.
                    logger.exception("Failed to update countdown for ticket %s", ticket.ticket_id)
                if expired:
                    self._registry.remove(ticket.ticket_id)
        except asyncio.CancelledError:
            # Expected when a decision button or Help! stops the countdown - not an error.
            raise


class TicketFormReplyActivity(FormReplyActivity):
    """Handles the original ticket's decision buttons and the "Help!" escalation."""

    def __init__(self, messages: MessageService, registry: TicketRegistry, ticket_command: TicketCommandActivity):
        self._messages = messages
        self._registry = registry
        self._ticket_command = ticket_command

    def matches(self, context: FormReplyContext) -> bool:
        return context.form_id == TICKET_FORM_ID

    async def on_activity(self, context: FormReplyContext):
        ticket = self._registry.get(context.get_form_value("ticket_id"))
        if ticket is None:
            return  # Ticket already expired/resolved and evicted - ignore the stale click.

        action = context.get_form_value("action")
        stream_id = context.source_event.stream.stream_id
        message_id = context.source_event.form_message_id
        ticket.cancel_timer()

        if action == "help":
            ticket.status = "help_requested"
            updated = await self._messages.update_message(stream_id, message_id, _render_help_form(ticket))
            ticket.message_id = updated.message_id
            return

        label = DECISION_ACTIONS.get(action)
        if label is None:
            logger.warning("Unknown action '%s' on ticket %s", action, ticket.ticket_id)
            return

        ticket.status = "actioned"
        self._registry.remove(ticket.ticket_id)
        rationale = context.get_form_value("rationale")
        await self._messages.update_message(stream_id, message_id, _render_ticket(ticket, resolved_label=label, rationale=rationale))


class TicketHelpFormReplyActivity(FormReplyActivity):
    """Handles submission of the Help form: raises an incident room, or cancels back to the ticket."""

    def __init__(self, messages: MessageService, streams: StreamService, registry: TicketRegistry, ticket_command: TicketCommandActivity):
        self._messages = messages
        self._streams = streams
        self._registry = registry
        self._ticket_command = ticket_command

    def matches(self, context: FormReplyContext) -> bool:
        return context.form_id == HELP_FORM_ID

    async def on_activity(self, context: FormReplyContext):
        ticket = self._registry.get(context.get_form_value("ticket_id"))
        if ticket is None:
            return

        stream_id = context.source_event.stream.stream_id
        message_id = context.source_event.form_message_id
        action = context.get_form_value("action")

        if action == "cancel_help":
            ticket.status = "pending"
            updated = await self._messages.update_message(stream_id, message_id, _render_ticket(ticket))
            ticket.message_id = updated.message_id
            self._ticket_command.start_countdown(ticket)
            return

        if action != "submit_help":
            logger.warning("Unknown action '%s' on help form for ticket %s", action, ticket.ticket_id)
            return

        topic = context.get_form_value("topic")
        details = context.get_form_value("details") or ""
        requester_user_id = context.initiator.user.user_id

        room = await self._streams.create_room(V3RoomAttributes(
            name=f"Incident - {ticket.ticket_id}",
            description=f"Escalation raised against Message Rate Control ticket {ticket.ticket_id}",
            public=False,
        ))
        room_id = room.room_system_info.id
        await self._streams.add_member_to_room(requester_user_id, room_id)

        welcome_template = _templates.get_template("incident_room_welcome.jinja2")
        await self._messages.send_message(room_id, welcome_template.render(
            **ticket.as_template_context(),
            requester_user_id=requester_user_id,
            topic_label=_HELP_TOPIC_LABELS.get(topic, topic),
            details=details,
        ))

        ticket.status = "actioned"
        self._registry.remove(ticket.ticket_id)
        resolved_template = _templates.get_template("ticket_help_resolved.jinja2")
        room_uri = f"https://open.symphony.com/?streamId={room_id}&streamType=chatroom"
        await self._messages.update_message(stream_id, message_id, resolved_template.render(ticket_id=ticket.ticket_id, room_uri=room_uri))
