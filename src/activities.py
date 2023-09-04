from symphony.bdk.core.activity.command import CommandContext, SlashCommandActivity
from symphony.bdk.core.activity.command import CommandActivity, CommandContext
from symphony.bdk.core.service.message.message_service import MessageService
from symphony.bdk.core.service.stream.stream_service import StreamService
from jinja2 import Template


class HelpCommandActivity(SlashCommandActivity):
    def __init__(self, messages: MessageService):
        self._messages = messages
        super().__init__("/help", True, self.help_command)

    async def help_command(self, context: CommandContext):
        stream_id = context.stream_id
        template = Template(open('resources/templates/help.jinja2').read(), autoescape=True)
        await self._messages.send_message(stream_id, template.render())

class SalesCommandActivity(SlashCommandActivity):
    def __init__(self, messages: MessageService):
        self._messages = messages
        super().__init__("/sales", True, self.sales_command)

    async def sales_command(self, context: CommandContext):
        stream_id = context.stream_id
        template = Template(open('resources/templates/sales.jinja2').read(), autoescape=True)
        await self._messages.send_message(stream_id, template.render())
        
class SupportCommandActivity(SlashCommandActivity):
    def __init__(self, messages: MessageService):
        self._messages = messages
        super().__init__("/support", True, self.support_command)

    async def support_command(self, context: CommandContext):
        stream_id = context.stream_id
        template = Template(open('resources/templates/support.jinja2').read(), autoescape=True)
        await self._messages.send_message(stream_id, template.render())