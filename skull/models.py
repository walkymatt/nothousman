import uuid
import datetime
from django.utils import timezone
from django.db import models

class Game(models.Model):
    # games are identified by a user-specified tag, as with Codenames
    tag = models.CharField(max_length=32, primary_key=True)
    
    # probably don't care about these, but...
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    
    # the most recent game state notification message
    status = models.CharField(max_length=200, default='')
    
    # game phase
    class Stage(models.IntegerChoices):
        # waiting for players
        GATHERING = 0
        
        # waiting for everyone to place first
        STARTING = 1
        
        # players have option of placing or bidding
        PLACING = 2
        
        # players have option of bidding or passing
        BIDDING = 3
        
        # winner of bid must flip cards
        FLIPPING = 4
        
        # pause at round end for drama
        FLIPPER_LOST = 5
        FLIPPER_WON = 6
        
        # game complete
        OVER = 7

    stage = models.IntegerField(choices=Stage.choices, default=Stage.GATHERING)
    next_player = models.IntegerField(default=-1)
    
    placed = models.IntegerField(default=0)
    bidder = models.IntegerField(default=-1)
    bid = models.IntegerField(default=0)
    flipped = models.IntegerField(default=0)
    skuller = models.IntegerField(default=-1)
    winner = models.IntegerField(default=-1)
        
    @classmethod
    def create(cls, tag, owner_nickname):
        game = cls(tag=tag)
        game.save()
        game.player_set.create(game=game, nickname=owner_nickname, owner=True)
        return game
    
    def round_start (self, next_player=0):
        self.stage = Game.Stage.STARTING
        self.next_player = next_player
        self.placed = 0
        self.bidder = -1
        self.bid = 0
        self.flipped = 0
        self.skuller = -1
        self.winner = -1
        self.save()
        
    def advance_player (self):
        current = self.next_player
        players = self.player_set.order_by('turn_order')
        
        candidate = (current + 1) % len(players)
        
        while candidate != current:
            if players[candidate].alive and not players[candidate].passed:
                self.next_player = candidate
                self.save()
                return True
            else:
                candidate = (candidate + 1) % len(players)
        return False
        
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
    
    points = models.PositiveSmallIntegerField(default=0)
    alive = models.BooleanField(default=True)
    passed = models.BooleanField(default=False)
    
    # using strings for this kinda sucks, but it's easier than trying
    # to do proper data structures in DB tables, and the structs are very simple
    hand = models.CharField(max_length=4, default='0001')
    stack = models.CharField(max_length=4, default='')
    flipped = models.IntegerField(default=0)
    
    # allocated on game start
    turn_order = models.IntegerField(default=-1)
    
    # first player to join a game gets to start it
    owner = models.BooleanField(default=False)
    
    def __str__(self):
        return self.nickname
    
    def reset (self, turn_order=-1):
        self.points = 0
        self.alive = True
        self.passed = False
        self.hand = '0001'
        self.stack = ''
        self.flipped = 0
        self.turn_order = turn_order
        self.save()
    
    def round_start (self):
        self.passed = False
        self.hand += self.stack
        self.stack = ''
        self.flipped = 0
        self.save()
    
    
        
    
    
    