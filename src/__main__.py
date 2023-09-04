#!/usr/bin/env python3
import asyncio
import logging.config
from pathlib import Path

from symphony.bdk.core.config.loader import BdkConfigLoader
from symphony.bdk.core.service.datafeed.real_time_event_listener import RealTimeEventListener
from symphony.bdk.core.symphony_bdk import SymphonyBdk
from symphony.bdk.gen.agent_model.v4_initiator import V4Initiator
from symphony.bdk.gen.agent_model.v4_message_sent import V4MessageSent
from symphony.bdk.core.service.connection.model.connection_status import ConnectionStatus
from .connections_listener import ConnectionsListener
from .activities import HelpCommandActivity, SalesCommandActivity, SupportCommandActivity
from .lookup_activity import LookupCommandActivity, LookupFormReplyActivity

# Configure logging
current_dir = Path(__file__).parent.parent
logging_conf = Path.joinpath(current_dir, 'resources', 'logging.conf')
logging.config.fileConfig(logging_conf, disable_existing_loggers=False)


async def run():
    config = BdkConfigLoader.load_from_file(Path.joinpath(current_dir, 'resources', 'config.yaml'))

    async with SymphonyBdk(config) as bdk:
        datafeed_loop = bdk.datafeed()
        datafeed_loop.subscribe(MessageListener())
 
        activities = bdk.activities()
        activities.register(HelpCommandActivity(bdk.messages()))
        activities.register(SalesCommandActivity(bdk.messages()))
        activities.register(SupportCommandActivity(bdk.messages()))
        activities.register(LookupCommandActivity(bdk.messages()))
        activities.register(LookupFormReplyActivity(bdk.messages()))

        # Handle potential connection requests received while the bot was offline (at bootstrap)
        connections = await bdk.connections().list_connections(status=ConnectionStatus.PENDING_INCOMING)
        if not connections:
            print("No pending connections to accept")
        for connection in connections:
            await bdk.connections().accept_connection(connection.user_id)
            await ConnectionsListener.greeting(connection.user_id)
            print(f"Accepted connection request from ${connection.user_id}")

        # Start the datafeed read loop
        bdk.datafeed().subscribe(ConnectionsListener(bdk, ConnectionsListener.greeting))
        await datafeed_loop.start()


class MessageListener(RealTimeEventListener):
    async def on_message_sent(self, initiator: V4Initiator, event: V4MessageSent):
        logging.debug("Message received from %s: %s",
                      initiator.user.display_name, event.message.message)


# Start the main asyncio run
try:
    logging.info("Running bot application...")
    asyncio.run(run())
except KeyboardInterrupt:
    logging.info("Ending bot application")
