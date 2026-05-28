import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class TableStatusConsumer(AsyncWebsocketConsumer):
    GROUP = "tables_floor"
    ADMIN_GROUP = "admins_billing"

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
            validated_token = JWTAuthentication().get_validated_token(token)
        except (InvalidToken, TokenError):
            await self.close(code=4001)
            return

        user = await self.get_authenticated_user(validated_token)
        if user is None:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        if user.is_admin:
            await self.channel_layer.group_add(self.ADMIN_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)
        await self.channel_layer.group_discard(self.ADMIN_GROUP, self.channel_name)

    @database_sync_to_async
    def get_authenticated_user(self, validated_token):
        try:
            user = JWTAuthentication().get_user(validated_token)
        except (InvalidToken, TokenError):
            return None

        if not user or not user.is_active:
            return None

        return user

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

    async def bill_request_notification(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "billing.bill_request",
                    "audience": event.get("audience", "admin"),
                    "table_id": event["table_id"],
                    "table_number": event["table_number"],
                    "order_id": event["order_id"],
                    "requested_by": event["requested_by"],
                    "requested_by_id": event["requested_by_id"],
                    "requested_at": event["requested_at"],
                }
            )
        )
