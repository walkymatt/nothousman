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

# index page: join a game
def index(request):
    return render(request, 'nothanks/index.html', {})

# game page: view game state, optionally performing an action
def game(request, tag):
    action = request.POST.get('move', None)
    token = request.session.get('nt_token', request.POST.get('token', 'nobody'))
    how = request.POST.get('how', None)
    notify = False
    
    if action=='join':
        nick = request.POST.get('nick', None)
        if nick is None:
            return render(request, 'nothanks/index.html', { 'msg' : 'you must provide a valid nickname to join a game' })
        house_rules = request.POST.get('house_rules', 'no') == 'yes'
        num_rounds = request.POST.get('num_rounds', 3)
        
        try:
            num_rounds = int(num_rounds)
        except Exception:
            num_rounds = 3
        
        token, msg, notify = GM.join(tag, nick, house_rules=house_rules, num_rounds=num_rounds)
        if token is not None:
            request.session['nt_token'] = token
        
    elif action=='start':
        msg, notify = GM.start(tag, token)
    elif action=='take':
        try:
            current_card = int(request.POST.get('card', '-1'))
        except Exception:
            current_card = None
        
        msg, notify = GM.take(tag, token, current_card=current_card)
    elif action=='pay':
        try:
            pool_size = int(request.POST.get('pool_size', '-1'))
        except Exception:
            pool_size = None
        
        msg, notify = GM.pay(tag, token, pool_size=pool_size)
        
    elif action=='end_round': 
        msg, notify = GM.end_round(tag, token)
    elif action=='destroy':
        success, msg = GM.destroy(tag, token)
        if success:
            send_notification(request, tag, msg, action='index')
            return render(request, 'nothanks/index.html', { 'msg' : msg })
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
        return render(request, 'nothanks/game.html', state)
