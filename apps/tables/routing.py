from django.urls import path

from .consumers import TableStatusConsumer

websocket_urlpatterns = [
    path("ws/tables/", TableStatusConsumer.as_asgi()),
]
