import uuid
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
        # waiting for players to join
        GATHERING = 0
        
        # lead player must choose a card
        STARTING = 1
        
        # next player must view, pass or call
        PLAYING = 2
        
        # game is finished
        GAME_OVER = 3

    stage = models.IntegerField(choices=Stage.choices, default=Stage.GATHERING)
    next_player = models.IntegerField(default=-1)
    
    # the card being passed around this round
    card = models.IntegerField(default=-1)
    
    # can a player win by getting all suits?
    house_rules = models.BooleanField(default=False)
    
    @classmethod
    def create(cls, tag, owner_nickname, house_rules):
        game = cls(tag=tag, house_rules=house_rules)
        game.save()
        game.player_set.create(game=game, nickname=owner_nickname, owner=True)
        return game
    
    def round_start (self, next_player=0):
        self.stage = Game.Stage.STARTING
        self.next_player = next_player
        self.card = -1
        self.save()
    
    def end_game (self):
        self.stage = Game.Stage.GAME_OVER
        self.next_player = -1
        self.card = -1
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
    
    # using strings for this kinda sucks, but it's easier than trying
    # to do proper data structures in DB tables, and the structs are very simple
    
    # hidden cards from which player may choose
    hand = models.CharField(max_length = 100, default='')
    
    # face up cards player has had to take
    tricks = models.CharField(max_length = 100, default='')
    
    # allocated on game start
    # -- in this game there isn't a fixed turn order, but we'll keep a
    # a random ordering for display purposes
    turn_order = models.IntegerField(default=-1)
    
    # first player to join a game gets to start it
    owner = models.BooleanField(default=False)
    
    # has this player seen the current card?
    seen = models.BooleanField(default=False)
    
    # what has this player claimed the card to be?
    claim = models.IntegerField(default=-1)
    
    # who has this player passed to?
    target = models.IntegerField(default=-1)
    
    # who did this player receive from?
    nominator = models.IntegerField(default=-1)

    # player status
    class Status(models.IntegerChoices):
        # waiting for players to arrive
        WAITING = 0
        
        # passing cards
        PLAYING = 1
        
        # waiting for players to play
        WATCHING = 2
        
        # player has lost
        LOST = 3
        
        # player has won
        WON = 4
    
    status = models.IntegerField(choices=Status.choices, default=Status.WAITING)
    
    
    def __str__(self):
        return self.nickname
    
    def reset (self, turn_order=-1, hand=''):
        self.turn_order = turn_order
        self.hand = hand
        self.tricks = ''
        self.save()
    
    def round_start (self, next_player=0):
        self.claim = -1
        self.seen = False
        self.target = -1
        if self.turn_order == next_player:
            self.nominator = self.turn_order
            self.status = Player.Status.PLAYING
        else:
            self.nominator = -1
            self.status = Player.Status.WATCHING
            
        self.save()
    
    
        
    
    
    