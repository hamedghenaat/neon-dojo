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
    c.rect(77, top, 246, bottom-top, '#253146')
    c.rect(79, top+2, 242, bottom-top-4, INK)
    c.line(94,top+23,306,top+23,GOLD)
    _center(c,top+10,title,GOLD,2)


def _heart(c,x,y,color):
    shape = ('0110110','1111111','1111111','0111110','0011100','0001000')
    for row,line in enumerate(shape):
        for col,value in enumerate(line):
            if value == '1':
                c.rect(x+col*3,y+row*3,3,3,color)


def _background(c,tick):
    c.clear('#111b2d')
    c.rect(0,42,400,100,'#182c38')
    c.rect(0,142,400,63,'#23443e')
    for i in range(18):
        x=(i*67+13)%400
        c.rect(x,25+(i*19)%100,1,1,'#526b70')
    for x in (10,45,340,380):
        c.rect(x+7,69,7,133,'#263a35')
        for y,w in ((45,33),(60,45),(80,35),(100,27)):
            c.rect(x+12-w//2,y,w,13,'#234c43')
            c.rect(x+10-w//2,y,w-7,5,'#36614b')
        c.line(x+25,75,x+20,146,'#648658')
    # Towers, central balcony and a stone stair leading into the jungle.
    c.rect(130,72,140,117,'#45576c')
    c.rect(138,77,124,110,'#566b7b')
    for x in (119,263):
        c.rect(x,82,18,110,'#394b62')
        for crenel in (0,7,14):
            c.rect(x+crenel,76,4,8,'#62768a')
        c.rect(x+6,105,5,12,'#142235')
        c.rect(x+6,145,5,12,'#142235')
    for y in range(74,52,-1):
        inset=(74-y)*2
        c.line(142+inset,y,258-inset,y,'#6f4d70')
    c.rect(195,45,2,15,GOLD)
    c.rect(197,46,13,6,ROSE)
    c.rect(166,83,68,54,'#182334')
    c.line(165,82,235,82,GOLD)
    c.line(165,82,165,137,GOLD)
    c.line(235,82,235,137,GOLD)
    c.rect(160,137,80,5,'#9da7a0')
    c.rect(164,142,72,3,'#35475a')
    c.rect(192,162,16,29,'#182334')
    for i in range(4):
        c.rect(183-i*4,187+i*3,34+i*8,3,'#657369')
    for y in range(145,191,12):
        for x in range(143,260,22):
            if not (185<x<212 and y>157):
                c.line(x,y,x+9,y,'#71828b')
    c.rect(0,203,400,37,'#26392d')
    c.rect(0,201,400,3,'#75995b')
    for x in range(4,400,17):
        c.line(x,201,x+2,197,'#9bbd69')
        c.rect(x,211+(x%3)*4,4,1,'#3a5038')
    for i in range(8):
        x=(i*51+tick//3)%400
        y=99+(i*17+tick//5)%87
        c.rect(x,y,1,1,GOLD)


def draw_scene(controller, canvas, assets=None):
    c, game, tick = canvas, controller.game, controller.tick
    _background(c,tick)
    married = game.state == 'match_over' or (game.state == 'wedding' and game.state_time>=4.4)
    c.sprite('princess','idle',204 if married else 191,106,scale=2,tick=tick)
    for y in range(115,190,4):
        c.line(224,y,226,y+2,GOLD)
        c.line(226,y+2,224,y+4,GOLD)
    if married:
        champion,_ = game.story_fighters()
        c.sprite('knight_cyan' if champion.color == 2 else 'knight_magenta','victory',170,101,scale=2,tick=tick)
        _heart(c,290,102,ROSE if tick%30<15 else '#f58f9c')

    if game.state == 'title':
        _panel(c,'NEON DOJO',55,193)
        _center(c,86,'THE TOWER TOURNAMENT',ROSE)
        for index,label in enumerate(('SINGLE PLAYER','ADD SERVER','JOIN SERVER','SETTINGS')):
            y=105+index*18
            if index == game.menu_index:
                c.rect(105,y-4,190,15,'#344b5a')
            _center(c,y,label,GOLD if index == game.menu_index else WHITE)
        _center(c,209,'UP / DOWN SELECT    ENTER PLAY    Q QUIT',WHITE)
    elif game.state == 'settings':
        _panel(c,'PLAYER SETTINGS',57,194)
        _center(c,90,'NAME: '+game.settings.character_name,CYAN)
        for i,label in enumerate(('USE OS USERNAME','SET CUSTOM NAME','BACK')):
            _center(c,111+i*19,('> ' if i==game.settings_index else '  ')+label,GOLD if i==game.settings_index else WHITE)
        _center(c,179,game.settings_message,ROSE)
        _center(c,210,'ENTER SELECT    ESC BACK',WHITE)
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
            c.rect(0,0,400,40,INK)
            for fighter,x in ((game.player,10),(game.enemy,245)):
                color=CYAN if fighter.color==2 else ROSE
                c.text(x,5,fighter.name[:16],color)
                c.rect(x,15,145,7,'#344052')
                c.rect(x,15,round(145*fighter.health/100),7,color)
                c.rect(x,26,round(145*fighter.meter/100),3,GOLD)
                c.text(x,32,'WINS '+str(fighter.wins),WHITE)
            _center(c,9,str(math.ceil(game.round_time)),GOLD,2)
        if game.state not in ('wedding','match_over'):
            for fighter in (game.player,game.enemy):
                action='block' if fighter.blocking else fighter.action
                c.sprite('knight_cyan' if fighter.color==2 else 'knight_magenta',action,
                         round(fighter.x*4)-17,201-36-round(fighter.jump_y*2),
                         flip=fighter.facing==-1,scale=2,tick=tick)
        elif game.state=='wedding' and not married:
            champion,_=game.story_fighters()
            # Move from field to the balcony during the story's climb phase.
            progress=max(0,min(1,(game.state_time-1.6)/2.8))
            y=165-round(progress*64)
            c.sprite('knight_cyan' if champion.color==2 else 'knight_magenta',champion.action,
                     round(champion.x*4)-17,y,scale=2,tick=tick)
        for particle in game.particles:
            c.rect(round(particle.x*4),201-round(particle.y*2),2,2,GOLD)
        if game.banner:
            _caption(c,46,game.banner,GOLD)
        elif game.state=='fight':
            cheers=('TANGLED: FIGHT, BRAVE KNIGHTS!','TANGLED: SHOW YOUR COURAGE!')
            _caption(c,46,cheers[tick//180%2],GOLD)
        if game.state=='round_over':
            _center(c,218,'WAITING FOR HOST' if game.mode=='client' else 'ENTER CONTINUE',WHITE)
        elif game.state=='match_over':
            _caption(c,188,'THE CHAMPION AND TANGLED ARE MARRIED',GOLD)
            _center(c,218,'WAITING FOR HOST' if game.mode=='client' else 'ENTER REMATCH    Q QUIT',WHITE)
        elif game.state=='paused':
            _panel(c,'PAUSED',85,145)
            _center(c,122,'WAITING FOR HOST' if game.mode=='client' else 'P / ESC RESUME',WHITE)
        elif game.state=='wedding':
            _center(c,218,'A NEW LEGEND BEGINS' if married else 'THE CHAMPION ASCENDS TO THE CASTLE',GOLD)
        elif game.state=='fight':
            _center(c,218,'ARROWS MOVE/JUMP/CROUCH   Z/X/C ATTACK   SPACE BLOCK',WHITE)
            _center(c,230,'P PAUSE    Q QUIT',WHITE)
    if controller.text_prompt is not None:
        _panel(c,controller.text_prompt,84,157)
        _center(c,119,controller.text_buffer[-45:]+'_',CYAN)
        _center(c,143,'ENTER CONFIRM    ESC CANCEL',WHITE)
