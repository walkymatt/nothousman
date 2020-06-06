# -*- coding: utf-8 -*-
from .models import Game, Player
import random, uuid

MIN_PLAYERS = 3
MAX_PLAYERS = 6
DECK_MIN = 3
DECK_MAX = 35
DECK_SIZE = 24
NUM_ROUNDS = 3

EMOJIS = { 'NEXT' : '▶️', 'WINNER' : '🏆' }

def make_deck ( count=DECK_SIZE, lo=DECK_MIN, hi=DECK_MAX ):
    '''
    Create the starting deck for a round.
    '''
    deck = random.sample(range(lo, hi+1), count)
    return ','.join([str(x) for x in deck])
    

def join ( tag, nickname, num_rounds=NUM_ROUNDS, house_rules=False ):
    '''
    Attempt to add a player to a game. If the game is in progress, this fails.
    If the game already has a player with the same nickname, reconnects that player.
    If the game doesn't exist, it is created and the player becomes its owner.
    '''
    try:
        game = Game.objects.get(pk=tag)

        try:
            existing = game.player_set.get(nickname=nickname)
            return str(existing.token), 'Rejoining game %s as existing player %s' % (tag, nickname), False
        except Player.DoesNotExist:
            pass

        if game.stage != Game.Stage.GATHERING:
            return None, 'Game %s already in progress' % tag, False
                
        if len(game.player_set.all()) >= MAX_PLAYERS:
            return None, 'Game %s already has the maximum number of players (%i)' % (tag, MAX_PLAYERS), False
            
        game.player_set.create(nickname=nickname)
        token = str(game.player_set.get(nickname=nickname).token)
        
        return token, 'Player %s joined game %s' % (nickname, tag), True
        
    except Game.DoesNotExist:
        game = Game.create(tag, nickname, num_rounds=num_rounds, house_rules=house_rules)
        token = str(game.player_set.get(nickname=nickname).token)
        return token, 'Game %s created, owned by %s' % (tag, nickname), True


def get_game_and_player ( tag, token ):
    '''
    Map game and player PKs to their model objects, if possible.
    '''
    try:
        game = Game.objects.get(pk=tag)
        
        try:
            valid = uuid.UUID(token)
        except Exception:
            return game, None, 'Invalid player token %s' % token
        
        player = Player.objects.get(pk=token)
        
        if player.game != game:
            return game, player, 'Player %s is not in game %s' % (player.nickname, tag)
        
        return game, player, None
        
    except Game.DoesNotExist:
        return None, None, 'Game %s does not exist' % tag
    except Player.DoesNotExist:
        return game, None, 'Player %s does not exist' % token


def start ( tag, token ):
    '''
    Attempt to launch a game.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage not in (Game.Stage.GATHERING, Game.Stage.GAME_OVER):
        return 'Game %s is already in progress' % tag, False
    
    players = game.player_set.all()
    count = len(players)
    if count < MIN_PLAYERS:
        return 'Not enough players to start game %s (%i)' % (tag, count), False
            
    seq = random.sample(range(count), count)
    for ii in range(count):
        players[ii].reset(turn_order=seq[ii])
        
    players = game.player_set.all().order_by('turn_order')
    turn_order = ', '.join([p.nickname for p in players])

    game.round_start(deck=make_deck())
    
    return 'Started game %s, turn order is [%s], %s to lead' % (tag, turn_order, game.player_set.get(turn_order=game.next_player).nickname), True


def take ( tag, token, current_card ):
    '''
    Take the current card and pool.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage != Game.Stage.PLAYING:
        return "taking a card is not a valid move at this game stage", False
    
    try:
        deck = [ int(x) for x in game.deck.split(',') ] if len(game.deck) else []
    except Exception as e:
        return "internal game error: deck is malformed (%s)" % (str(e)), False
    
    if len(deck) == 0:
        return "internal game error: deck is empty", False
    
    card, deck = deck[0], deck[1:]
    
    if current_card != card:
        return 'ignoring duplicate take request for card ' + str(current_card), False
    
    try:
        hand = [ int(x) for x in player.hand.split(',') ] if len(player.hand) else []
    except Exception as e:
        return "internal game error: player hand is malformed (%s)" % (str(e)), False
    
    hand.append(card)
    player.hand = ','.join([str(x) for x in sorted(hand)])
    game.deck = ','.join([str(x) for x in deck])

    player.cash += game.pool
    game.pool = 0
    
    game.save()
    player.save()
    
    if len(deck) == 0:
        game.stage = Game.Stage.ROUND_OVER
        game.save()
        msg = "%s takes the last card" % player.nickname
    else:
        if game.house_rules:
            game.advance_player()
            msg = "%s takes the card, %s is next to go and reveals %i" % (player.nickname,  game.player_set.get(turn_order=game.next_player).nickname, deck[0])
        else:
            msg = "%s takes the card, reveals %i and must go again" % (player.nickname, deck[0])
    
    return msg, True 
    

def pay ( tag, token, pool_size ):
    '''
    Pay 1 to refuse the current card.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False

    if game.stage != Game.Stage.PLAYING:
        return "paying is not a valid move at this game stage", False
    
    if game.pool != pool_size:
        return 'ignoring duplicate pay request at pool size ' + str(pool_size), False
    
    if player.cash < 1:
        return "%s has no tokens so cannot pay", False
    
    player.cash -= 1
    player.save()
    
    game.pool += 1
    game.advance_player()
    
    next_player = game.player_set.get(turn_order=game.next_player)
    
    return "%s pays a token, %s is next to go" % (player.nickname,  next_player.nickname), True


def calculate_score ( player ):
    '''
    Calculate a player's score for a round, as:
    sum of lowest card values in each continuous run, minus remaining cash.
    '''
    hand = [ int(x) for x in player.hand.split(',') ] if len(player.hand) else []     # should be already sorted
    score = 0
    
    prev = -100
    for card in hand:
        if card > (prev + 1):
            score += card
        prev = card
    
    return score - player.cash
        
    
def end_round ( tag, token ):
    '''
    Finalise the round, calculate points and either start next round or end game.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
        
    if game.stage != Game.Stage.ROUND_OVER:
        return 'round is not ready to end', False
    
    players = game.player_set.all().order_by('turn_order')
    round_scores = {}
    running_scores = {}
    
    for pp in players:
        score = calculate_score(pp)
        round_scores[pp.nickname] = score
        pp.points += score
        pp.save()
        running_scores[pp.nickname] = pp.points
    
    game.round += 1
    game.save()
    
    if game.round >= game.num_rounds:
        game.stage = Game.Stage.GAME_OVER
        game.save()
        
        best = game.player_set.all().order_by('points')[0].points
        winners = game.player_set.all().filter(points=best)
        
        if len(winners) == 1:
            win_msg = "%s wins!" % winners[0].nickname
        else:
            win_msg = "%s and %s are joint winners" % ( ', '.join([x.nickname for x in winners[:(len(winners)-1)]]), winners[len(winners)-1].nickname)
        
        stage_msg = 'Final scores: %s. %s' % (', '.join( [ '%s: %i' % (nick, running_scores[nick]) for nick in running_scores]), win_msg)
                                                
    else:
        if game.round > 1:
            run_msg = 'Overall scores: %s.' % (', '.join( [ '%s: %i' % (nick, running_scores[nick]) for nick in running_scores]))
        
        # TODO: settle on rule for next player
        game.round_start(deck=make_deck(), next_player=game.next_player)
        for pp in players:
            pp.round_start()
        stage_msg = 'Starting round %i/%i' % (game.round + 1, game.num_rounds)
    
    return 'Scores for round %i: %s. %s' % (game.round, ', '.join( [ '%s: %i' % (nick, round_scores[nick]) for nick in round_scores] ), stage_msg), True


def destroy ( tag, token ):
    '''
    Delete a game and all its players.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return False, err
        
    game.delete()
    return True, 'game %s deleted' % tag


def visible_state ( tag, token, emojify=True, emojify_status=True, hide_own_miniview=True ):
    '''
    Return a dict defining the game state as visible to the specified
    player. (Unrecognised players see only public state.)
    '''
    game, player, err = get_game_and_player( tag, token )
    if game is None:
        return { 'tag' : tag, 'token' : token, 'err' : err }
    
    result = { 'tag' : tag, 'token' : token }
    
    # stage seems to come out as an int, failing comparisons
    stage = Game.Stage(game.stage)
    
    if player:
        result['nickname'] = player.nickname
        if (stage==Game.Stage.PLAYING) and (player.turn_order == game.next_player):
            if (player.cash < 1):
                result['actions'] = ['take']
            else:
                result['actions'] = ['take', 'pay']
        elif stage == Game.Stage.ROUND_OVER:
            result['actions'] = ['end_round']
        elif (stage == Game.Stage.GAME_OVER):
            result['actions'] = ['start', 'destroy']            
        elif (stage == Game.Stage.GATHERING) and (len(game.player_set.all()) >= MIN_PLAYERS):
            result['actions'] = ['start']            
        else:
            result['actions'] = []            
    else:
        result['actions'] = []
    
    result['stage'] = stage.label
    result['next_player'] = game.next_player
    
    if game.deck:
        try:
            deck = [ int(x) for x in game.deck.split(',') ]
        except Exception as e:
            return { 'err' : 'internal game error: deck is malformed (%s)' % (str(e)) }
    else:
        deck = []
    
    result['pool'] = game.pool
    result['card'] = deck[0] if deck else 0
    result['deck_size'] = len(deck)
    result['status'] = game.status

    # these will be overwritten later for real players
    result['your_hand'] = []
    result['your_cash'] = 0
    
    result['players'] = []
    
    best = game.player_set.all().order_by('points')[0].points
    
    for pp in game.player_set.all().order_by('turn_order'):
        desc = { 'nickname' : pp.nickname, 
                 'you' : (token == str(pp.token)),
                 'points' : pp.points,
                 'is_next' : (game.next_player != -1) and (pp.turn_order == game.next_player),
                 'owner' : pp.owner,
                 'turn_order' : pp.turn_order,
                 'hand' : [ int(x) for x in pp.hand.split(',') ] if pp.hand else [] }
        
        desc['status'] = ('WINNER' if ((game.stage == Game.Stage.GAME_OVER) and (pp.points == best))
                          else 'NEXT' if desc['is_next']
                          else '&nbsp;')
        
        if emojify_status:
            desc['status'] = EMOJIS.get(desc['status'], desc['status'])

        
        if token == str(pp.token):
            result['your_turn_order'] = pp.turn_order
            result['your_points'] = pp.points
            result['your_nickname'] = pp.nickname
            result['your_hand'] = desc['hand']
            result['your_cash'] = pp.cash            
        
        result['players'].append(desc)
    
    return result
    

def purge ():
    '''
    Destroy all games. For testing only, not to be exposed to outside world!
    '''
    Game.objects.all().delete()


    
