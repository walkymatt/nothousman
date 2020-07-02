from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse

from django_eventstream import send_event

from .models import Game
from . import game_logic as GM

import json

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

    # send message irrespective of game existence, to notify destruction
    send_event(tag, 'message', {'text':action})

def as_int(x, subst):
    try:
        return int(x)
    except Exception:
        return subst

# index page: join a game
def index(request):
    return render(request, 'cockroach/index.html', {})

# game page: view game state, optionally performing an action
def game(request, tag):
    action = request.POST.get('move', None)
    token = request.session.get('cock_token', request.POST.get('token', 'nobody'))
    how = request.POST.get('how', None)
    notify = False
    
    if action=='join':
        nick = request.POST.get('nick', None)
        if nick is None:
            return render(request, 'cockroach/index.html', { 'msg' : 'you must provide a valid nickname to join a game' })
        house_rules = request.POST.get('house_rules', 'no') == 'yes'
        
        token, msg, notify = GM.join(tag, nick, house_rules=house_rules)
        if token is not None:
            request.session['cock_token'] = token
        
    elif action=='start':
        msg, notify = GM.start(tag, token)


    elif action=='play':
        card_idx = as_int(request.POST.get('card_idx', '-1'), -1)
        target = as_int(request.POST.get('target', '-2'), -2)
        claim = as_int(request.POST.get('claim', '-1'), -1)
        
        msg, notify = GM.play(tag, token, card_idx=card_idx, target=target, claim=claim)


    elif action=='peek':
        msg, notify = GM.peek(tag, token)

    elif action=='refer':
        target = as_int(request.POST.get('target', '-2'), -2)
        claim = as_int(request.POST.get('claim', '-1'), -1)
        
        msg, notify = GM.refer(tag, token, target=target, claim=claim)
    
    elif action=='call':
        verdict = request.POST.get('verdict', 'no') == 'yes'
        
        msg, notify = GM.call(tag, token, verdict)
        
    elif action=='destroy':
        success, msg = GM.destroy(tag, token)
        if success:
            send_notification(request, tag, msg, action='index')
            return render(request, 'cockroach/index.html', { 'msg' : msg })
    else:
        msg = 'You are viewing this game as non-player.' if token=='nobody' else ''
        notify = False
    
    if notify:
        send_notification(request, tag, msg)
        msg = ''
    
    msg = msg or ''

    state = GM.visible_state(tag, token)
    state['msg'] = msg
    
    if how == 'json':
        return JsonResponse(state)
    else:
        state['json_state'] = json.dumps(state)
        return render(request, 'cockroach/game.html', state)
