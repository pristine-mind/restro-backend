import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken


class TableStatusConsumer(AsyncWebsocketConsumer):
    GROUP = "tables_floor"

    async def connect(self):
        # Authenticate via JWT in query string: ws://.../?token=<access>
        query_string = self.scope["query_string"].decode()
        token = None
        if "token=" in query_string:
            token = query_string.split("token=")[-1].split("&")[0]

        if not token:
            await self.close(code=4001)
            return

        try:
            UntypedToken(token)
        except (InvalidToken, TokenError):
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    # Receives broadcast from services.py group_send
    async def table_status_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "table.status.update",
                    "table_id": event["table_id"],
                    "status": event["status"],
                    "table_number": event["table_number"],
                }
            )
        )
