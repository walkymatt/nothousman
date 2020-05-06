from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

from .models import Game
import skull.game_logic as GM

# send messages to game clients to notify of state changes
# no idea how this is going to work yet,
# for now it's a placeholder
def send_notification (request, tag, msg, action='refresh'):
    try:
        game = Game.objects.get(pk=tag)
        game.status = msg
        game.save()
    except Game.DoesNotExist:
        pass

# index page: join a game
def index(request):
    return render(request, 'skull/index.html', {})

# game page: view game state, optionally performing an action
def game(request, tag):
    action = request.POST.get('move', None)
    token = request.POST.get('token', 'nobody')
    notify = False
    
    if action=='join':
        nick = request.POST.get('nick', None)
        if nick is None:
            return render(request, 'skull/index.html', { 'msg' : 'you must provide a valid nickname to join a game' })
        token, msg, notify = GM.join(tag, nick)
    elif action=='start':
        msg, notify = GM.start(tag, token)
    elif action=='place': 
        card = request.POST['card']
        msg, notify = GM.place(tag, token, card)
    elif action=='bid':
        bid = request.POST['bid']
        msg, notify = GM.bid(tag, token, bid)
    elif action=='decline':
        msg, notify = GM.decline(tag, token)
    elif action=='flip':
        target = request.POST['target']   
        msg, notify = GM.flip(tag, token, target)
    elif action=='end_round': 
        msg, notify = GM.end_round(tag, token)
    elif action=='destroy':
        success, msg = GM.destroy(tag, token)
        if success:
            send_notification(request, tag, msg, action='index')
            return render(request, 'skull/index.html', { 'msg' : msg })
    else:
        msg = 'You are viewing this game as non-player.' if token=='nobody' else ''
        notify = False
    
    if notify:
        send_notification(request, tag, msg)
        msg = ''

    state = GM.visible_state(tag, token)
    return render(request, 'skull/game.html', { **state, 'msg' : msg })
