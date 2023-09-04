from jinja2 import Template
from symphony.bdk.core.activity.command import SlashCommandActivity, CommandContext
from symphony.bdk.core.activity.form import FormReplyActivity, FormReplyContext
from symphony.bdk.core.service.message.message_service import MessageService
import json

data = json.load(open('resources/data.json'))   
prev = None
max_list = 2

class LookupCommandActivity(SlashCommandActivity):
    def __init__(self, messages: MessageService):
        super().__init__("/lookup", True, self.display_lookup_form)
        self._messages = messages
        self.template = Template(open('resources/templates/table.jinja2').read(), autoescape=True)

    async def display_lookup_form(self, context: CommandContext):
        global prev
        message = data_slicer(0, data, max_list)
        prev = await self._messages.send_message(context.stream_id, message)
        print(prev.message_id)
        return prev

class LookupFormReplyActivity(FormReplyActivity):
    # Sends back the selected value on form submission
    def __init__(self, messages: MessageService):
        self._messages = messages

    def matches(self, context: FormReplyContext) -> bool:
        print(context.form_id)
        print(context.form_values)
        return context.form_id == "example" \
            and context.form_values["action"] is not None
    
    async def on_activity(self, context: FormReplyContext):
        global prev
        selection = context.form_values.get("action")
        print(selection)
 
        match selection:
            case "next":
                print("Next set of records")
                message = data_slicer(int(context.form_values.get("next")), data, max_list)
                prev = await self._messages.update_message(context.source_event.stream.stream_id, prev.message_id, message)
                
            case "previous":
                print("Previous set of records")
                print(prev.message_id)
                message = data_slicer(int(context.form_values.get("current")) - max_list, data, max_list)
                prev = await self._messages.update_message(context.source_event.stream.stream_id, prev.message_id, message)

            case _:
                print("Record has been selected")
                await self._messages.send_message(context.source_event.stream.stream_id,
                                          f"<messageML>You selected row, {selection}</messageML>")

def data_slicer(index, data, max_list):
    template = Template(open('resources/templates/table.jinja2').read(), autoescape=True)
    for i in range(index, len(data['body']), max_list):
        message = template.render(data=data['body'][i:i + max_list], current = index, next = index + max_list, length = len(data['body']))
        return message

