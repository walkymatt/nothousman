from django.conf.urls import url, include
from channels.routing import URLRouter
from channels.http import AsgiHandler
from channels.auth import AuthMiddlewareStack
import django_eventstream

urlpatterns = [
    url(r'^events/(?P<tag>\w+)/', AuthMiddlewareStack(URLRouter(django_eventstream.routing.urlpatterns)), { 'format-channels' : [ '{tag}' ] }),
    url(r'', AsgiHandler),
]
