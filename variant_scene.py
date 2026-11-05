"""Shared 400x240 pixel scene, drawn by either graphical engine."""
from __future__ import annotations
import math

WIDTH, HEIGHT = 400, 240
INK = '#111827'
WHITE = '#f8f5e9'
GOLD = '#f5ce72'
CYAN = '#57d6df'
ROSE = '#d896e8'


def _center(c, y, text, color=WHITE, scale=1):
    # Both canvases use a consistent four-pixel text advance at scale one.
    text = str(text).replace('♥', '<3')
    c.text(max(2, (WIDTH - len(text) * 4 * scale) // 2), y, text, color, scale=scale)


def _caption(c, y, text, color=GOLD):
    """Reserve an opaque reading band above busy scenery."""
    width = min(WIDTH, len(str(text).replace('♥', '<3')) * 4 + 16)
    c.rect((WIDTH-width)//2, y-3, width, 12, INK)
    _center(c, y, text, color)


def _panel(c, title, top=65, bottom=192):
    c.rect(80, top+3, 246, bottom-top, '#493e68')
    c.rect(77, top, 246, bottom-top, '#736887')
    c.rect(79, top+2, 242, bottom-top-4, GOLD)
    c.rect(80, top+3, 240, bottom-top-6, INK)
    c.line(94,top+23,306,top+23,GOLD)
    _center(c,top+10,title,GOLD,2)


def _tile(c, name, x, y, scale=2):
    c.sprite('platformer', name, x, y, scale=scale)


def _cloud(c, x, y):
    for offset, part in enumerate(('cloud_left', 'cloud', 'cloud_right')):
        _tile(c, part, x+offset*36, y)


def _tree(c, x, y):
    # Layer the trunk behind a tiled crown; every tile shares Kenney's palette.
    for ty in range(y+36, 177, 36):
        _tile(c, 'trunk', x+36, ty)
    _tile(c, 'roots', x+36, 164)
    for row, names in enumerate((('leaves_tl','leaves_top','leaves_tr'),
                                  ('leaves_left','leaves','leaves_right'),
                                  ('leaves_bl','leaves_bottom','leaves_br'))):
        for col, name in enumerate(names):
            _tile(c, name, x+col*36, y+row*36)


def _roof(c, x, y, w, h):
    c.rect(x-2,y+h,w+4,3,'#493b68')
    for row in range(0,h,3):
        inset=(h-row)//2
        c.rect(x+inset,y+row,w-inset*2,3,'#665899')
        c.line(x+inset,y+row,x+w-inset-1,y+row,'#9682bc')
    c.line(x+w//2,y-5,x+w//2,y+2,'#f8e4b2')
    c.rect(x+w//2+1,y-5,9,5,'#ed7b8c')


def _castle(c):
    # Warm stonework, contrasting roofs, inset windows and a projecting balcony.
    for x in (130,248):
        c.rect(x,86,24,112,'#736887')
        c.rect(x+2,86,20,110,'#b3a9b6')
        c.rect(x+3,86,4,110,'#ddd1c1')
        for y in range(99,195,13):
            c.line(x+7,y,x+20,y,'#91899d')
        _roof(c,x-4,62,32,24)
        for y in (104,145):
            c.rect(x+9,y,8,15,'#655779')
            c.rect(x+10,y+2,4,10,'#b7d9df')
            c.line(x+12,y+2,x+12,y+10,'#776784')
    c.rect(151,77,98,121,'#82748c')
    c.rect(154,77,91,121,'#c9bec2')
    c.rect(154,77,6,121,'#e5d8cc')
    for row,y in enumerate(range(82,199,9)):
        for x in range(160-(row%2)*9,243,18):
            c.line(x,y,x+13,y,'#a69aaf')
            c.line(x,y,x,y+3,'#b9a9b6')
    _roof(c,145,55,110,23)
    # Recessed balcony large enough for both wedding characters.
    c.rect(167,88,65,47,'#796082')
    c.rect(170,91,59,44,'#493e68')
    c.line(170,91,228,91,'#f5dfaf')
    for x in (166,230):
        c.rect(x,89,3,47,'#f5dfaf')
        c.rect(x-2,132,7,4,'#a895ab')
    c.rect(161,135,77,4,'#f6e5c7')
    c.rect(164,139,71,4,'#9d8a9e')
    c.rect(168,143,63,2,'#7c6b87')
    c.rect(187,164,26,33,'#796082')
    c.rect(190,167,20,30,'#644b64')
    for x in range(192,210,4):
        c.line(x,168,x,196,'#98717b')
    c.rect(202,181,2,3,'#f5ce72')
    for i in range(3):
        c.rect(180-i*5,192+i*3,40+i*10,3,'#ddd1c1')
        c.line(180-i*5,194+i*3,220+i*5,194+i*3,'#9d8a9e')
    for x in (177,218):
        c.rect(x,149,5,9,'#866389')
        c.rect(x+1,148,3,3,'#ffd77c')


def _background(c,tick):
    c.clear('#9cd6e4')
    c.rect(0,62,400,77,'#b4e0df')
    c.rect(0,139,400,62,'#c9e6d5')
    # Clouds drift independently of combat, behind the castle and forest.
    for x,y,speed in ((-30,38,18),(172,64,25),(340,26,18)):
        _cloud(c,(x+tick//speed)%520-100,y)
    # Softer, stepped hill silhouettes make depth without competing with combat.
    for x,y,w in ((-20,129,130),(70,151,94),(256,140,120),(350,120,90)):
        c.rect(x,y,w,75,'#88bd9d')
        c.rect(x+12,y-8,w-24,8,'#88bd9d')
        c.rect(x+26,y-15,w-52,7,'#88bd9d')
        c.rect(x,y+30,w,50,'#6fae89')
    _castle(c)
    _tree(c,-54,43)
    _tree(c,348,34)
    for x in (20,83,301,370):
        _tile(c,'sprout',x,169)
    for x in (49,337):
        _tile(c,'flower',x,170)
    _tile(c,'mushroom',100,179,1)
    _tile(c,'mushroom',291,179,1)
    _tile(c,'crate',-12,165)
    _tile(c,'crate',378,165)
    # A continuous, flat collision surface with a readable textured grass edge.
    for x in range(-18,400,36):
        _tile(c,'grass',x,201)
        _tile(c,'earth',x,237)


def draw_scene(controller, canvas, assets=None):
    c, game, tick = canvas, controller.game, controller.tick
    _background(c,tick)
    married = game.state == 'match_over' or (game.state == 'wedding' and game.state_time>=4.4)
    c.sprite('princess','idle',207 if married else 191,107,scale=2,tick=tick)
    for y in range(116,190,4):
        c.line(224,y,226,y+2,GOLD)
        c.line(226,y+2,224,y+4,GOLD)
    if married:
        champion,_ = game.story_fighters()
        c.sprite('knight_cyan' if champion.color == 2 else 'knight_magenta','balcony',177,107,scale=2,tick=tick)
        _tile(c,'heart',282,99,3)

    if game.state == 'title':
        # Keep the castle and its princess visible beside a compact menu sign.
        c.rect(12,24,164,171,'#493e68')
        c.rect(10,22,164,171,GOLD)
        c.rect(12,24,160,167,INK)
        c.text(30,37,'NEON DOJO',GOLD,scale=3)
        c.text(27,59,'THE TOWER TOURNAMENT',ROSE)
        c.line(24,73,160,73,'#736887')
        for index,label in enumerate(('SINGLE PLAYER','ADD SERVER','JOIN SERVER','SETTINGS')):
            y=88+index*23
            if index == game.menu_index:
                c.rect(23,y-5,139,17,'#344b5a')
                c.text(28,y,'>',GOLD)
            c.text(42,y,label,GOLD if index == game.menu_index else WHITE)
        c.text(26,179,'A LEGEND IN EVERY DUEL', '#9bb6be')
        c.sprite('knight_cyan','victory',270,147,scale=3,tick=tick)
        _caption(c,225,'UP / DOWN SELECT    ENTER PLAY    Q QUIT',WHITE)
    elif game.state == 'settings':
        _panel(c,'PLAYER SETTINGS',57,194)
        _center(c,90,'NAME: '+game.settings.character_name,CYAN)
        for i,label in enumerate(('USE OS USERNAME','SET CUSTOM NAME','BACK')):
            _center(c,111+i*19,('> ' if i==game.settings_index else '  ')+label,GOLD if i==game.settings_index else WHITE)
        _center(c,179,game.settings_message,ROSE)
        _caption(c,225,'ENTER SELECT    ESC BACK',WHITE)
    elif game.state in ('hosting','searching'):
        _panel(c,'ADD SERVER' if game.state=='hosting' else 'JOIN SERVER',57,196)
        _center(c,95,'WAITING FOR A KNIGHT'+'.'*(1+tick//15%3),CYAN)
        status=game.network_status
        for index in range(0,min(len(status),110),50):
            _center(c,114+index//50*10,status[index:index+50],WHITE)
        if game.state=='hosting':
            addresses=game.server_address.split(' / ')
            for i,address in enumerate(addresses[:2]):
                _center(c,146+i*10,address,GOLD)
        _center(c,179,'I ENTER ADDRESS    ESC BACK',ROSE)
    else:
        if game.state not in ('wedding','match_over'):
            c.rect(0,0,400,39,INK)
            c.line(0,38,399,38,'#415c70')
            for fighter,x in ((game.player,10),(game.enemy,245)):
                color=CYAN if fighter.color==2 else ROSE
                c.text(x,5,fighter.name[:16],color)
                c.rect(x,15,145,7,'#344052')
                health_width = round(145*fighter.health/100)
                c.rect(x,15,health_width,7,color)
                if health_width > 0:
                    c.line(x,15,x+health_width-1,15,'#f8f5e9')
                c.rect(x,26,110,3,'#344052')
                c.rect(x,26,round(110*fighter.meter/100),3,GOLD)
                c.text(x+115,25,'ARC',GOLD)
                c.text(x,32,'WINS '+str(fighter.wins),WHITE)
            _center(c,9,str(math.ceil(game.round_time)),GOLD,2)
        if game.state not in ('wedding','match_over'):
            for fighter in (game.player,game.enemy):
                action='block' if fighter.blocking else fighter.action
                c.sprite('knight_cyan' if fighter.color==2 else 'knight_magenta',action,
                         round(fighter.x*4)-25,201-54-round(fighter.jump_y*2),
                         flip=fighter.facing==-1,scale=3,tick=tick)
        elif game.state=='wedding' and not married:
            champion,_=game.story_fighters()
            # Move from field to the balcony during the story's climb phase.
            progress=max(0,min(1,(game.state_time-1.6)/2.8))
            y=147-round(progress*48)
            c.sprite('knight_cyan' if champion.color==2 else 'knight_magenta',champion.action,
                     round(champion.x*4)-25,y,scale=3,tick=tick)
        for particle in game.particles:
            c.rect(round(particle.x*4),201-round(particle.y*2),2,2,GOLD)
        if game.banner:
            _caption(c,46,game.banner,GOLD)
        elif game.state=='fight':
            cheers=('TANGLED: FIGHT, BRAVE KNIGHTS!','TANGLED: SHOW YOUR COURAGE!')
            _caption(c,46,cheers[tick//180%2],GOLD)
        if game.state=='round_over':
            _caption(c,218,'WAITING FOR HOST' if game.mode=='client' else 'ENTER CONTINUE',WHITE)
        elif game.state=='match_over':
            _caption(c,188,'THE CHAMPION AND TANGLED ARE MARRIED',GOLD)
            _caption(c,218,'WAITING FOR HOST' if game.mode=='client' else 'ENTER REMATCH    Q QUIT',WHITE)
        elif game.state=='paused':
            _panel(c,'PAUSED',85,145)
            _center(c,122,'WAITING FOR HOST' if game.mode=='client' else 'P / ESC RESUME',WHITE)
        elif game.state=='wedding':
            _caption(c,218,'A NEW LEGEND BEGINS' if married else 'THE CHAMPION ASCENDS TO THE CASTLE',GOLD)
        elif game.state=='fight':
            c.rect(0,228,400,12,INK)
            _center(c,232,'ARROWS MOVE  Z/X/C ATTACK  SPACE BLOCK  P PAUSE  Q QUIT',WHITE)
    if controller.text_prompt is not None:
        _panel(c,controller.text_prompt,84,157)
        _center(c,119,controller.text_buffer[-45:]+'_',CYAN)
        _center(c,143,'ENTER CONFIRM    ESC CANCEL',WHITE)
