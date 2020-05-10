from channels.routing import ProtocolTypeRouter, URLRouter
import skull.routing

application = ProtocolTypeRouter({
    'http': URLRouter(skull.routing.urlpatterns),
})