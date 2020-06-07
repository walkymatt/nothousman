import uuid
from django.db import models

# this conceptually belongs in game_logic but is too tiresome to put there
INITIAL_CASH = 11

class Game(models.Model):
    # games are identified by a user-specified tag, as with Codenames
    tag = models.CharField(max_length=32, primary_key=True)
    
    # probably don't care about these, but...
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    
    # the most recent game state notification message
    status = models.CharField(max_length=200, default='')
    
    # whether we're playing with the proper rules or the incorrect ones
    house_rules = models.BooleanField(default=False)
    
    # how many rounds to play
    num_rounds = models.IntegerField(default=3)
    
    # current round
    round = models.IntegerField(default=0)
    
    # game phase
    class Stage(models.IntegerChoices):
        # waiting for players
        GATHERING = 0
        
        # waiting for everyone to place first
        PLAYING = 1
        
        # players have option of bidding or passing
        ROUND_OVER = 2
        
        # game complete
        GAME_OVER = 3

    stage = models.IntegerField(choices=Stage.choices, default=Stage.GATHERING)
    next_player = models.IntegerField(default=-1)
    
    # once again, using strings for this is crappy
    # but going full relational seems like overkill
    deck = models.CharField(max_length = 100, default='')
    pool = models.IntegerField(default=0)
    
    @classmethod
    def create(cls, tag, owner_nickname, num_rounds=3, house_rules=False):
        game = cls(tag=tag, num_rounds=num_rounds, house_rules=house_rules)
        game.save()
        game.player_set.create(game=game, nickname=owner_nickname, owner=True)
        return game
    
    def round_start (self, deck, next_player=0):
        self.stage = Game.Stage.PLAYING            
        self.next_player = next_player            
        self.pool = 0
        self.deck = deck
        self.save()
       
    def advance_player (self):
        current = self.next_player
        players = self.player_set.order_by('turn_order')
        self.next_player = (current + 1) % len(players)
        self.save()
        
    def __str__(self):
        return self.tag
    

class Player(models.Model):
    # each player has a unique token which is passed when moving
    # in order to validate their move
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # players exist only within context of a game
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    # players supply their own nickname when joining a game
    nickname = models.CharField(max_length=32)
    
    points = models.IntegerField(default=0)
    cash = models.IntegerField(default=INITIAL_CASH)
    
    # using strings for this kinda sucks, but it's easier than trying
    # to do proper data structures in DB tables, and the structs are very simple
    hand = models.CharField(max_length = 100, default='')
    
    # allocated on game start
    turn_order = models.IntegerField(default=-1)
    
    # first player to join a game gets to start it
    owner = models.BooleanField(default=False)
    
    def __str__(self):
        return self.nickname
    
    def reset (self, turn_order=-1):
        self.points = 0
        self.hand = ''
        self.cash = INITIAL_CASH
        self.turn_order = turn_order
        self.save()
    
    def round_start (self):
        self.hand = ''
        self.cash = INITIAL_CASH
        self.save()
    
    
        
    
    
    