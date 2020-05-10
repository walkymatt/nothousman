import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

class NotificationConsumer(WebsocketConsumer):
    @classmethod
    def group_name_for_game(cls, tag):
        return 'skull_notify_%s' % tag
        
    def connect(self):
        self.game_name = self.scope['url_route']['kwargs']['game_name']
        self.game_group_name = NotificationConsumer.group_name_for_game(self.game_name)
        async_to_sync(self.channel_layer.group_add)(self.game_group_name, self.channel_name)
        print('connect: %s | %s' % (self.channel_name, self.game_group_name))
        self.accept()
    
    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(self.game_group_name, self.channel_name)
    
    def receive(self, text_data):
        # for the moment we don't care about this,
        # as we only want the socket for sending
        print('receive: ' + text_data)
    
    def notify(self, event):
        message = event['message']
        print('notify: ' + message)
        self.send(text_data=json.dumps({'message': message}))
