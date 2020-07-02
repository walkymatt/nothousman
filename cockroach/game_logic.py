# -*- coding: utf-8 -*-
from .models import Game, Player
import random, math, uuid, collections

MIN_PLAYERS = 3
MAX_PLAYERS = 8
SUITS = 8
CARDS_PER_SUIT = 8
DECK_SIZE = SUITS * CARDS_PER_SUIT
SUIT_NAMES = [ 'cockroach', 'stinkbug', 'spider', 'scorpion',
               'bat', 'rat', 'fly', 'toad' ]
SUIT_PLURALS = [ 'cockroaches', 'stinkbugs', 'spiders', 'scorpions',
                 'bats', 'rats', 'flies', 'toads' ]
LOSE_COUNT = 4

EMOJIS = { 'NEXT' : '▶️', 'WINNER' : '🏆', 'LOSER' : '🤮',
           'AVAIL' : '', 'UNAVAIL' : '♻️', 'STARTER' : '🔰' }

def deal ( num_players ):
    '''
    Create the initial hands of cards.
    '''
    deck = list(range(SUITS)) * CARDS_PER_SUIT
    random.shuffle(deck)
    
    hand_sizes = [math.floor(DECK_SIZE / num_players)] * num_players
    
    # first player gets an extra card if there is one
    if DECK_SIZE % num_players:
        hand_sizes[0] += 1
    
    hands = []
    for hh in hand_sizes:
        hand, deck = deck[:hh], deck[hh:]
        hands.append(sorted(hand))
        
    return hands
    
def encode_cards ( cards ):
    '''
    Convert cards (list of int) to a comma-delimited string for storage.
    '''
    return ','.join([str(x) for x in cards])

def decode_cards ( card_str ):
    '''
    Convert an encoded card string into a list of ints.
    '''
    if not card_str:
        return []
    
    try:
        return [ int(x) for x in card_str.split(',') ]
    except Exception:
        return []


def join ( tag, nickname, house_rules=False ):
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
        
        player_count = len(game.player_set.all())
        
        if player_count >= MAX_PLAYERS:
            return None, 'Game %s already has the maximum number of players (%i)' % (tag, MAX_PLAYERS), False
            
        game.player_set.create(nickname=nickname)
        token = str(game.player_set.get(nickname=nickname).token)
        player_count += 1
        
        if player_count < MIN_PLAYERS:
            needed = MIN_PLAYERS - player_count
            sub_msg = "Waiting for at least %i more player%s" % (needed, 's' if (needed > 1) else '')
        else:
            sub_msg = "Game is ready to begin"
        return token, 'Player %s joined game %s. %s.' % (nickname, tag, sub_msg), True
        
    except Game.DoesNotExist:
        game = Game.create(tag, nickname, house_rules=house_rules)
        token = str(game.player_set.get(nickname=nickname).token)
        return token, 'Game %s created, owned by %s. Waiting for at least %i more players.' % (tag, nickname, MIN_PLAYERS - 1), True


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
    hands = deal(len(players))
    for ii in range(count):
        players[ii].reset(turn_order=seq[ii], hand=encode_cards(hands[seq[ii]]))
        players[ii].round_start()
        
    game.round_start()
    
    first = game.player_set.get(turn_order=0)
    return 'Started game %s, %s to start' % (tag, first.nickname), True
    

def play ( tag, token, card_idx, target, claim ):
    '''
    Choose a card from your hand and pass it to another player
    with a claim as to what it is.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage != Game.Stage.STARTING:
        return 'Playing a card is not a valid move at this game stage', False

    if game.next_player != player.turn_order:
        return "It is not %s's turn to play" % player.nickname, False
    
    hand = decode_cards(player.hand)
    if (card_idx < 0) or (card_idx >= len(hand)):
        return "Chosen card is out of range of player %s's hand (%i)" % (player.nickname, card_idx), False
    
    if target == player.turn_order:
        return "Player cannot play a card to themself", False
    
    try:
        victim = game.player_set.get(turn_order=target)
    except Exception:
        return "Target player not found (%i)" % target, False
    
    if (claim < 0) or (claim >= SUITS):
        return "Claimed suit is out of range (%i)" % claim, False
    
    card = hand.pop(card_idx)
    
    game.next_player = target
    game.stage = Game.Stage.PLAYING
    game.card = card
    game.save()
    
    player.target = target
    player.claim = claim
    player.hand = encode_cards(hand)
    player.seen = True
    player.status = Player.Status.WATCHING
    player.save()
    
    victim.nominator = player.turn_order
    victim.status = Player.Status.PLAYING
    victim.save()
    
    return '%s plays a card to %s, claiming it is a %s. %s must pass or call.' % (player.nickname,
                                                                                  victim.nickname,
                                                                                  SUIT_NAMES[claim],
                                                                                  victim.nickname), True

def peek ( tag, token ):
    '''
    Look at the passed card, limiting subsequent action to refer.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage != Game.Stage.PLAYING:
        return 'Looking at the card is not a valid move at this game stage', False

    if game.next_player != player.turn_order:
        return "It is not %s's turn" % player.nickname, False
    
    if len(game.player_set.all().filter(nominator=-1)) == 0:
        return 'Cannot look at the card when there is no-one left to pass to', False
    
    player.seen = True
    player.save()
    
    return '%s looks at the passed card' % player.nickname, True


def refer ( tag, token, target, claim ):
    '''
    Nominate another player to receive the card in play, with an updated (or not) claim.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage != Game.Stage.PLAYING:
        return 'Passing the card is not a valid move at this game stage', False

    if game.next_player != player.turn_order:
        return "It is not %s's turn" % player.nickname, False
    
    if target == player.turn_order:
        return "Player cannot play a card to themself", False
    
    try:
        victim = game.player_set.get(turn_order=target)
    except Exception:
        return "Target player not found (%i)" % target, False
    
    if (claim < 0) or (claim >= SUITS):
        return "Claimed suit is out of range (%i)" % claim, False
        
    game.next_player = target
    game.save()
    
    player.target = target
    player.claim = claim
    player.status = Player.Status.WATCHING
    player.save()
    
    victim.nominator = player.turn_order
    victim.status = Player.Status.PLAYING
    victim.save()
    
    avail = game.player_set.all().filter(nominator=-1)
    acts = 'pass or call' if len(avail) else 'call'
    seen = '' if player.seen else ' (unseen)'
    
    return '%s passes the card%s to %s, claiming it is a %s. %s must %s.' % (player.nickname,
                                                                             seen,
                                                                             victim.nickname,
                                                                             SUIT_NAMES[claim],
                                                                             victim.nickname,
                                                                             acts), True

    
def call ( tag, token, verdict ):
    '''
    Declare whether the nominator's claim is correct.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return err, False
    
    if game.stage != Game.Stage.PLAYING:
        return 'Calling is not a valid move at this game stage', False

    if game.next_player != player.turn_order:
        return "It is not %s's turn" % player.nickname, False
    
    if player.seen:
        return 'Calling is not an option once the card has been seen, %s must pass.' % player.nickname, False
    
    nominator = game.player_set.get(turn_order=player.nominator)
    
    if verdict == (nominator.claim == game.card):
        msg = '%s calls correctly, the card is a %s' % (player.nickname, SUIT_NAMES[game.card])
        loser = nominator
    else:
        msg = '%s calls incorrectly, the card is a %s' % (player.nickname, SUIT_NAMES[game.card])
        loser = player
    
    tricks = decode_cards(loser.tricks)
    tricks.append(game.card)
    loser.tricks = encode_cards(sorted(tricks))
    loser.save()
    
    over = False
    loser_status = Player.Status.PLAYING
    other_status = Player.Status.WATCHING
    
    if collections.Counter(tricks)[game.card] == LOSE_COUNT:
        # player loses, everyone else wins
        over = True
        loser_status = Player.Status.LOST
        other_status = Player.Status.WON
        msg = '%s. %s takes the card and loses the game with %i %s.' % (msg, loser.nickname, LOSE_COUNT, SUIT_PLURALS[game.card])
        
    elif game.house_rules:
        wins = True
        for ii in range(SUITS):
            if ii not in tricks:
                wins = False
        if wins:
            # player wins, everyone else loses
            over = True
            loser_status = Player.Status.WON
            other_status = Player.Status.LOST
            msg = '%s. %s takes the card and wins the game by having all the suits.' % (msg, loser.nickname)
    
    if not over:
        hand = decode_cards(loser.hand)
        if len(hand) == 0:
            msg = '%s. %s takes the card and has no cards left, so loses the game.' % (msg, loser.nickname)
            over = True
            loser_status = Player.Status.LOST
            other_status = Player.Status.WON
    
    players = game.player_set.all()
    
    if over:
        for pp in players:
            pp.status = loser_status if (pp.turn_order == loser.turn_order) else other_status
            pp.save()
        game.end_game()

    else:
        for pp in players:
            pp.round_start(next_player=loser.turn_order)
        msg = '%s. %s takes the card and starts the next round.' % ( msg, loser.nickname )
        game.round_start(next_player=loser.turn_order)
    
    return msg, True


def destroy ( tag, token ):
    '''
    Delete a game and all its players.
    '''
    game, player, err = get_game_and_player( tag, token )
    if err is not None:
        return False, err
        
    game.delete()
    return True, 'game %s deleted' % tag


def visible_state ( tag, token, emojify=True ):
    '''
    Return a dict defining the game state as visible to the specified
    player. (Unrecognised players see only public state.)
    '''
    game, player, err = get_game_and_player( tag, token )
    if game is None:
        return { 'tag' : tag, 'token' : token, 'err' : err }
    
    result = { 'tag' : tag, 'token' : token, 'card' : '-1', 'suits' : SUIT_NAMES }
    
    # stage seems to come out as an int, failing comparisons
    stage = Game.Stage(game.stage)
    
    if player:
        result['nickname'] = player.nickname
        if (stage==Game.Stage.STARTING) and (player.turn_order == game.next_player):
            avail = game.player_set.all().filter(nominator=-1)
            result['referrable'] = [pp.turn_order for pp in avail]
            result['actions'] = ['play']
        elif (stage==Game.Stage.PLAYING) and (player.turn_order == game.next_player):
            avail = game.player_set.all().filter(nominator=-1)
            result['referrable'] = [pp.turn_order for pp in avail]
            
            if player.seen:
                result['actions'] = ['refer']
            elif len(avail):
                result['actions'] = ['peek', 'refer', 'call']
            else:
                result['actions'] = ['call']
        
        elif (stage == Game.Stage.GAME_OVER):
            result['actions'] = ['start', 'destroy']            
        elif (stage == Game.Stage.GATHERING) and (len(game.player_set.all()) >= MIN_PLAYERS):
            result['actions'] = ['start']            
        else:
            result['actions'] = []
        
        if player.seen: result['card'] = game.card
        
    else:
        result['actions'] = []
    
    result['stage'] = stage.label
    result['next_player'] = game.next_player
    result['status'] = game.status

    # these will be overwritten later for real players
    result['your_hand'] = []
    result['your_tricks'] = []
    result['card'] = 'absent'
    
    result['players'] = []
        
    for pp in game.player_set.all().order_by('turn_order'):
        desc = { 'nickname' : pp.nickname, 
                 'you' : (token == str(pp.token)),
                 'hand_size' : len(decode_cards(pp.hand)),
                 'tricks' : decode_cards(pp.tricks),
                 'is_next' : (game.next_player != -1) and (pp.turn_order == game.next_player),
                 'owner' : pp.owner,
                 'turn_order' : pp.turn_order,
                 'seen' : pp.seen,
                 'claim' : pp.claim,
                 'target' : pp.target,
                 'nominator' : pp.nominator }
        
        desc['status'] = ('WINNER' if ((game.stage == Game.Stage.GAME_OVER) and (pp.status == Player.Status.WON))
                          else 'LOSER' if ((game.stage == Game.Stage.GAME_OVER) and (pp.status == Player.Status.LOST))
                          else 'NEXT' if desc['is_next']
                          else 'STARTER' if ((game.stage == Game.Stage.PLAYING) and (pp.nominator==pp.turn_order))
                          else 'AVAIL' if ((game.stage in [Game.Stage.PLAYING, Game.Stage.STARTING]) and (pp.nominator == -1))
                          else 'UNAVAIL' if (game.stage in [Game.Stage.PLAYING, Game.Stage.STARTING])
                          else '&nbsp;')
        
        if emojify:
            desc['status'] = EMOJIS.get(desc['status'], desc['status'])

        
        if token == str(pp.token):
            result['your_turn_order'] = pp.turn_order
            result['your_nickname'] = pp.nickname
            result['your_hand'] = decode_cards(pp.hand)
            result['your_tricks'] = decode_cards(pp.tricks)
            
            if desc['is_next']:
                result['card'] = SUIT_NAMES[game.card] if pp.seen else 'back'
        
        result['players'].append(desc)
    
    return result
    

def purge ():
    '''
    Destroy all games. For testing only, not to be exposed to outside world!
    '''
    Game.objects.all().delete()


    
