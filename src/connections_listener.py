from symphony.bdk.core.service.datafeed.real_time_event_listener import RealTimeEventListener
from jinja2 import Template
import logging.config

supportEmail = "vinay@symphony.com"
salesEmail = "partners@symphony.com"
company = "Awesome Company, LLC"
botUserId = "devcertbot1098@bots.symphony.com"

class ConnectionsListener(RealTimeEventListener):
    def __init__(self, bdk, user_id):
        self.bdk = bdk
        self.user_id = user_id

    async def greeting(self, user_id):
        stream = await self.bdk.streams().create_im_or_mim([user_id])
        room = await self.bdk.streams().get_stream(stream.id)
        
        self.template = Template(open('resources/templates/welcome.jinja2').read(), autoescape=True)
        logging.debug(user_id)
        message = self.template.render(userId=user_id, botUserId=botUserId, company=company, supportEmail=supportEmail, salesEmail=salesEmail)
        await self.bdk.messages().send_message(stream.id, message)

    async def on_connection_requested(self, initiator, event):
        print("Incoming connection request received")
        await self.bdk.connections().accept_connection(initiator.user.user_id)
        await self.greeting(initiator.user.user_id)

    async def on_connection_accepted(self, initiator, event):
        print("Outgoing connection request accepted")
        await self.greeting(initiator.user.user_id)
