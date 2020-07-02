from channels.routing import ProtocolTypeRouter, URLRouter
import home.routing

application = ProtocolTypeRouter({
    'http': URLRouter(home.routing.urlpatterns),
})