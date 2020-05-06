# -*- coding: utf-8 -*-
from .models import Game, Player
import random, uuid

MIN_PLAYERS = 3
MAX_PLAYERS = 10
WINNING_POINTS = 2

EMOJIS = { '0' : '🌺', '1' : '💀', 'X' : '☣️' }

def join ( tag, nickname ):
    '''
    Attempt to add a player to a game. If the game is in progress, this fails.
    If the game already has a player with the same nickname, this fails.
    If the game doesn't exist, it is created and the player becomes its owner.
    '''
    try:
        game = Game.objects.get(pk=tag)
        
        if game.stage != Game.Stage.GATHERING:
            return None, 'Game %s already in progress' % tag, False
        
        try:
            existing = game.player_set.get(nickname=nickname)
            return None, 'Game %s already has a player named %s' % (tag, nickname), False
        except Player.DoesNotExist:
            pass
        
        if len(game.player_set.all()) >= MAX_PLAYERS:
            return None, 'Game %s already has the maximum number of players (%i)' % (tag, MAX_PLAYERS), False
            
        game.player_set.create(nickname=nickname)
        token = str(game.player_set.get(nickname=nickname).token)
        
        return token, 'Player %s joined game %s' % (nickname, tag), True
        
    except Game.DoesNotExist:
        game = Game.create(tag, nickname)
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
    Attempt to launch a game. Currently, only owner is allowed to do this.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage not in (Game.Stage.GATHERING, Game.Stage.OVER):
        return 'Game %s is already in progress' % tag, False
    
    if not player.owner:
        return '%s is not the owner of game %s' % (player.nickname, tag), False

    players = game.player_set.all()
    count = len(players)
    if count < MIN_PLAYERS:
        return 'Not enough players to start game %s (%i)' % (tag, count), False
            
    seq = random.sample(range(count), count)
    for ii in range(count):
        players[ii].reset(turn_order=seq[ii])
        
    players = game.player_set.all().order_by('turn_order')
    turn_order = ', '.join([p.nickname for p in players])

    game.round_start()
    
    return 'Started game %s, turn order is [%s], %s to lead, all players must place their first card' % (tag, turn_order, game.player_set.get(turn_order=game.next_player).nickname), True


def pop_string ( ss, ii ):
    '''
    Similar functionality to `pop()` but for strings.
    Extracts a character by index, returns the rest of the string and the character
    separately.
    '''
    remainder = ss[:ii] + ss[(ii+1):]
    popped = ss[ii]
    return remainder, popped


def place ( tag, token, card ):
    '''
    Take a card from a player's hand by index and put it on their stack.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    try:
        ii = int(card)
    except ValueError:
        return 'invalid card selection: ' + str(card), False

    if game.stage == Game.Stage.STARTING:
        if len(player.stack):
            return '%s has already placed their first card' % player.nickname, False
        if (ii < 0) or (ii >= len(player.hand)):
            return "selected card is out of range for %s's hand (%i)" % (player.nickname, ii), False
        
        hand, card = pop_string(player.hand, ii)       
        player.hand = hand
        player.stack = card
        player.save()
        
        game.placed += 1
        
        if len(game.player_set.filter(stack='', alive=True))==0:
            game.stage = Game.Stage.PLACING
            game.save()
            return 'all players have placed first card, %s must place or bid' % game.player_set.get(turn_order=game.next_player).nickname, True
        else:
            game.save()
            return '%s has placed their first card' % player.nickname, True
    
    elif game.stage == Game.Stage.PLACING:
        if player.turn_order != game.next_player:
            return "it is not player %s's turn to place now" % player.nickname, False
        
        if ii > len(player.hand):
            return "selected card is not in %s's hand (%i)" % (player.nickname, ii), False
       
        hand, card = pop_string(player.hand, ii)       
        player.hand = hand
        player.stack += card
        player.save()
        
        game.placed += 1
        game.advance_player()
        return '%s has placed, %s must place or bid' % (player.nickname, game.player_set.get(turn_order=game.next_player).nickname), True
    
    else:
        return 'placing a card is not allowed at this game stage', False


def bid ( tag, token, count ):
    '''
    Bid to turn over a certain number of cards.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False

    try:
        count = int(count)
    except ValueError:
        return 'invalid bid amount: ' + str(count), False

    if game.stage == Game.Stage.PLACING:
        if player.turn_order != game.next_player:
            return "it is not %s's turn to place now" % player.nickname, False
        
        if (count < 1) or (count > game.placed):
            return 'bid of %i is not valid (%i cards available)' % (count, game.placed), False
        
        game.bidder = game.next_player
        game.bid = count
        
        if count < game.placed:
            game.stage = Game.Stage.BIDDING
            game.advance_player()
            
            return '%s started the bidding at %i, %s must bid higher or pass' % (player.nickname, count, game.player_set.get(turn_order=game.next_player).nickname), True
        else:
            game.stage = Game.Stage.FLIPPING
            game.save()
            
            return '%s bid %i for all placed cards and now must flip' % (player.nickname, count), True
    
    elif game.stage == Game.Stage.BIDDING:
        if player.turn_order != game.next_player:
            return "it is not %s's turn to bid now" % player.nickname, False
        
        if (count <= game.bid) or (count > game.placed):
            return 'bid of %i is not valid (bid stands at %i with %i cards available)' % (count, game.bid, game.placed), False
        
        game.bidder = game.next_player
        game.bid = count
        
        if count < game.placed:
            game.advance_player()
            return '%s raised bid to %i, %s must bid higher or pass' % (player.nickname, count, game.player_set.get(turn_order=game.next_player).nickname), True
        else:
            game.stage = Game.Stage.FLIPPING
            game.save()
            
            return '%s bid %i for all placed cards and now must flip' % (player.nickname, count), True
    else:
        return 'bidding is not allowed at this game stage', False
       
def decline ( tag, token ):
    '''
    Surrender bidding for the rest of the round.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err

    if game.stage == Game.Stage.BIDDING:
        if player.turn_order != game.next_player:
            return "it is not %s's turn to bid now" % player.nickname, False
    
        player.passed = True
        player.save()
        game.advance_player()
        
        if game.bidder == game.next_player:
            game.stage = Game.Stage.FLIPPING
            game.save()
            return '%s passed, %s wins the bid and must now flip %i' % (player.nickname, game.player_set.get(turn_order=game.next_player).nickname, game.bid), True
        else:
            return '%s passed, %s must bid or pass' % (player.nickname,  game.player_set.get(turn_order=game.next_player).nickname), True
    else:
        return 'passing is not a valid move at this game stage', False

def flip ( tag, token, nickname ):
    '''
    Flip the top unflipped card of the target's pile. Target is identified by nickname
    (since token is not exposed to other players).
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False

    if game.stage == Game.Stage.FLIPPING:
        if player.turn_order != game.next_player:
            return '%s is not the player flipping' % player.nickname, False
        
        # player must flip own stack first
        # rather than mess around sending back pointless errors, just enforce this if player stack is not empty
        
        if player.flipped < len(player.stack):
            player.flipped += 1
            player.save()
            
            game.flipped += 1
            
            flipped_card = player.stack[-player.flipped]
            
            if flipped_card == '1':
                # player loses round
                game.stage = Game.Stage.FLIPPER_LOST
                game.skuller = game.next_player
                game.save()
                
                return '%s died on their own skull, losing the round' % player.nickname, True
            else:
                if player.flipped == game.bid:
                    # player wins round
                    game.stage = Game.Stage.FLIPPER_WON
                    game.save()
                    
                    return '%s matched their bid of %i to win the round' % (player.nickname, game.bid), True
                else:
                    game.save()
                    
                    return '%s found a flower, leaving %i still to flip' % (player.nickname, game.bid - game.flipped), True
        else:
            # ok, we care who the target is
            try:
                target = game.player_set.get(nickname=nickname)
                
                if len(target.stack) < target.flipped:
                    return "no cards available to flip in %s's stack" % target.nickname, False
                
                target.flipped += 1
                target.save()
                
                game.flipped += 1
                
                flipped_card = target.stack[-target.flipped]
                
                if flipped_card == '1':
                    # player loses round
                    game.stage = Game.Stage.FLIPPER_LOST
                    game.skuller = target.turn_order
                    game.save()
                
                    return "%s died on %s's skull, losing the round" % (player.nickname, target.nickname), True
                else:
                    if game.flipped == game.bid:
                        # player wins round
                        game.stage = Game.Stage.FLIPPER_WON
                        game.save()
                    
                        return '%s matched their bid of %i to win the round' % (player.nickname, game.bid), True
                    else:
                        game.save()
                    
                        return '%s found a flower, leaving %i still to flip' % (player.nickname, game.bid - game.flipped), True
                
            except Player.DoesNotExist:
                return 'cannot flip for non-existent player %s' % nickname, False
            
    
    else:
        return 'flipping is not a valid action at this game stage', False

def end_round ( tag, token ):
    '''
    Finalise the round, allocate a point or discard a card, kill player if appropriate,
    end game if appropriate, otherwise reset everything for next round.
    
    Currently, only owner is allowed to do this.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if (game.stage in (Game.Stage.FLIPPER_LOST, Game.Stage.FLIPPER_WON) and not player.owner):
        return '%s is not the owner of game %s' % (player.nickname, tag), False
    
    flipper = game.player_set.get(turn_order=game.next_player)
    
    if game.stage == Game.Stage.FLIPPER_LOST:
        flipper.hand += flipper.stack
        flipper.stack = ''
        flipper.hand, lost = pop_string(flipper.hand, random.randrange(len(flipper.hand)))
        print('lost: %s, remaining: %s' % (lost, flipper.hand))
        flipper.save()
        
        if len(flipper.hand) == 0:
            flipper.alive = False
            flipper.save()
            
            survivors = game.player_set.filter(alive=True)
            if len(survivors) == 1:
                game.stage = Game.Stage.OVER
                game.winner = game.skuller
                game.save()
                
                return '%s loses their last card, leaving %s as the winner!' % (flipper.nickname, game.player_set.get(turn_order=game.skuller).nickname), True
            else:
                game.round_start(next_player=game.skuller)
                for pp in game.player_set.all():
                    pp.round_start()
                                
                return '%s loses their last card, %s starts the next round, all surviving players must place their first card' % (flipper.nickname, game.player_set.get(turn_order=game.next_player).nickname), True
        else:
            game.round_start(next_player=game.skuller)
            for pp in game.player_set.all():
                pp.round_start()
                
            return '%s loses a card, %s starts the next round, all surviving players must place their first card' % (flipper.nickname, game.player_set.get(turn_order=game.next_player).nickname), True
                 
    elif game.stage == Game.Stage.FLIPPER_WON:
        flipper.points += 1
        flipper.save()
        
        if flipper.points >= WINNING_POINTS:
            game.stage = Game.Stage.OVER
            game.winner = game.next_player
            game.save()
            
            return '%s wins the game with %i points' % (flipper.nickname, flipper.points), True
        else:
            game.round_start(next_player=game.next_player)
            for pp in game.player_set.all():
                pp.round_start()
            
            return '%s starts the next round, all surviving players must place their first card' % flipper.nickname, True
    else:
        return 'round is not ready to end', False

def destroy ( tag, token ):
    '''
    Delete a game and all its players.
    Currently only the owner is allowed to do this.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return False, err
        
    if not player.owner:
        return False, '%s is not the owner of game %s' % (player.nickname, tag)
    
    game.delete()
    return True, 'game %s deleted'


def visible_state ( tag, token, emojify=True ):
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
        if (stage==Game.Stage.STARTING) and (player.stack == '') and player.alive:
            result['actions'] = ['place']
        elif (stage == Game.Stage.PLACING) and (player.turn_order == game.next_player):
            result['actions'] = ['place', 'bid']
        elif (stage == Game.Stage.BIDDING) and (player.turn_order == game.next_player):
            result['actions'] = ['bid', 'decline']        
        elif (stage == Game.Stage.FLIPPING) and (player.turn_order == game.next_player):
            result['actions'] = ['flip']
        elif (stage in (Game.Stage.FLIPPER_LOST, Game.Stage.FLIPPER_WON)) and player.owner:
            result['actions'] = ['end_round']
        elif (stage == Game.Stage.OVER) and player.owner:
            result['actions'] = ['start', 'destroy']            
        elif (stage == Game.Stage.GATHERING) and (len(game.player_set.all()) >= MIN_PLAYERS) and player.owner:
            result['actions'] = ['start']            
        else:
            result['actions'] = []            
    else:
        result['actions'] = []
    
    if 'bid' in result['actions']:
        result['possible_bids'] = list(range(game.bid + 1, game.placed + 1))
    
    result['stage'] = stage.label
    result['next_player'] = game.next_player
    result['placed'] = game.placed
    result['bidder'] = game.bidder
    result['bid'] = game.bid
    result['flipped'] = game.flipped
    result['skuller'] = game.skuller
    result['winner'] = game.winner
    result['status'] = game.status
    
    result['players'] = []
    
    for pp in game.player_set.all().order_by('turn_order'):
        desc = { 'nickname' : pp.nickname,  'you' : (token == str(pp.token)),
                 'points' : pp.points, 'alive' : pp.alive,
                 'passed' : pp.passed, 'owner' : pp.owner,
                 'turn_order' : pp.turn_order, 'flipped' : pp.flipped,
                 'hand' : list(pp.hand), 'stack' : list(pp.stack) }
        
        if token != str(pp.token):
            # hide private state
            desc['hand'] = [ 'X' for x in desc['hand'] ]
            for ii in range(len(desc['stack'])-pp.flipped):
                desc['stack'][ii] = 'X'
        else:
            # expose at top level for client simplicity
            if emojify:
                result['your_hand'] = [EMOJIS.get(x, x) for x in list(pp.hand)]
                result['your_stack'] = [EMOJIS.get(x, x) for x in list(pp.stack)]
            else:
                result['your_hand'] = list(pp.hand)
                result['your_stack'] = list(pp.stack)
        
        if emojify:
            desc['hand'] = [EMOJIS.get(x, x) for x in desc['hand']]
            desc['stack'] = [EMOJIS.get(x, x) for x in desc['stack']]
                
        
        result['players'].append(desc)
    
    return result
    

def purge ():
    '''
    Destroy all games. For testing only, not to be exposed to outside world!
    '''
    Game.objects.all().delete()
    

def make_test ( tag='g' ):
    '''
    Create a test game with three players
    named 'owner', 'p2' and 'p3' and start it.
    For testing only, obviously.
    '''
    owner, _, _ = join(tag, 'owner')
    p2, _, _ = join(tag, 'p2')
    p3, _, _ = join(tag, 'p3')
    _, _ = start_game(tag, owner)
    
    # lay initial cards: skull for owner, flowers for the others
    _, _ = place(tag, owner, 3)
    _, _ = place(tag, p2, 0)
    status, _ = place(tag, p3, 0)
    
    game = Game.objects.get(pk=tag)
    
    return game, owner, p2, p3, status
    
