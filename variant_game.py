"""Engine-independent menu/input/network controller for graphical editions."""
from __future__ import annotations

from neon_dojo import (FPS, Fighter, Game, Particle, MENU_ITEMS, SETTINGS_ITEMS,
                       apply_control, load_settings, save_settings,
                       normalize_character_name, update_ai)
from networking import NetworkSession, apply_game_data, local_server_addresses

WORLD_WIDTH = 100
COMMANDS = {'up': 'jump', 'w': 'jump', 'down': 'crouch', 's': 'crouch',
            'left': 'left', 'a': 'left', 'right': 'right', 'd': 'right',
            'z': 'punch', 'x': 'kick', 'c': 'special', 'space': 'block'}


class Controller:
    def __init__(self):
        settings = load_settings()
        self.game = Game(Fighter(settings.character_name, 22, 2),
                         Fighter('ONYX', 72, 3, facing=-1), settings=settings)
        self.tick = 0
        self.running = True
        self.text_prompt: str | None = None
        self.text_buffer = ''
        self._prompt_kind = ''
        self._elapsed = 0.0
        self._held_time = 0.0
        self.network: NetworkSession | None = None

    def close(self):
        if self.network:
            self.network.close()
            self.network = None

    def text(self, value: str):
        if self.text_prompt is not None:
            self.text_buffer = (self.text_buffer + ''.join(c for c in value if c.isprintable()))[:60]

    def backspace(self):
        if self.text_prompt is not None:
            self.text_buffer = self.text_buffer[:-1]

    def _prompt(self, kind, label):
        self._prompt_kind, self.text_prompt, self.text_buffer = kind, label, ''

    def _submit(self):
        value = self.text_buffer.strip()
        self.text_prompt = None
        if not value:
            return
        if self._prompt_kind == 'name':
            self.game.settings.name_source = 'custom'
            self.game.settings.custom_name = normalize_character_name(value)
            self.game.player.name = self.game.settings.character_name
            self.game.settings_message = 'Saved' if save_settings(self.game.settings) else 'Could not save settings'
        elif self.network:
            try:
                method = self.network.connect_direct if self._prompt_kind == 'direct' else self.network.invite_player
                self.game.network_status = method(value)
            except (OSError, ValueError) as error:
                self.game.network_status = f'Connection error: {error}'

    def _start_network(self, role):
        self.close()
        game = self.game
        game.mode = role
        game.state = 'hosting' if role == 'host' else 'searching'
        game.player.name = game.settings.character_name
        game.enemy.name = 'PLAYER'
        try:
            self.network = NetworkSession(role, game.player.name,
                state_applier=lambda target, payload: apply_game_data(target, payload, Fighter, Particle))
            game.server_address = local_server_addresses() if role == 'host' else ''
            game.network_status = 'Waiting for another knight' if role == 'host' else 'Scanning networks and Tailscale'
        except OSError as error:
            game.network_status = f'Network error: {error}'

    def _command(self, command):
        if self.game.state != 'fight':
            return
        if self.network and self.network.role == 'client':
            self.network.send_command(command)
        else:
            apply_control(self.game, self.game.player, command, 1 / FPS)

    def press(self, key: str):
        key = key.lower()
        game = self.game
        if self.text_prompt is not None:
            if key == 'escape':
                self.text_prompt = None
            elif key == 'enter':
                self._submit()
            return
        if key == 'q':
            self.running = False
            return
        if game.state == 'title':
            if key in ('up', 'w', 'down', 's'):
                game.menu_index = (game.menu_index + (-1 if key in ('up','w') else 1)) % len(MENU_ITEMS)
            elif key == 'enter':
                if game.menu_index == 0:
                    self.close()
                    game.mode = 'single'
                    game.player.name = game.settings.character_name
                    game.enemy.name = 'ONYX'
                    game.start_match(WORLD_WIDTH)
                elif game.menu_index in (1, 2):
                    self._start_network('host' if game.menu_index == 1 else 'client')
                else:
                    game.state, game.settings_index = 'settings', 0
            return
        if game.state == 'settings':
            if key == 'escape':
                game.state = 'title'
            elif key in ('up','w','down','s'):
                game.settings_index = (game.settings_index + (-1 if key in ('up','w') else 1)) % len(SETTINGS_ITEMS)
            elif key == 'enter':
                if game.settings_index == 0:
                    game.settings.name_source = 'os'
                    game.player.name = game.settings.character_name
                    game.settings_message = 'Saved' if save_settings(game.settings) else 'Could not save settings'
                elif game.settings_index == 1:
                    self._prompt('name', 'CHARACTER NAME')
                else:
                    game.state = 'title'
            return
        if game.state in ('hosting','searching'):
            if key == 'escape':
                self.close()
                game.state = 'title'
            elif key == 'i' and self.network:
                self._prompt('invite' if game.state == 'hosting' else 'direct', 'PLAYER IP[:PORT]' if game.state == 'hosting' else 'SERVER IP[:PORT]')
            return
        client = self.network is not None and self.network.role == 'client'
        if not client:
            if key == 'enter' and game.state == 'round_over':
                game.advance(WORLD_WIDTH)
            elif key == 'enter' and game.state == 'match_over':
                game.start_match(WORLD_WIDTH)
            elif key in ('p','escape') and game.state in ('fight','paused'):
                game.state = 'paused' if game.state == 'fight' else 'fight'
                game.state_time = 0
        # Movement/block/crouch are handled at a fixed held-input cadence.
        if key in ('z','x','c','up','w'):
            self._command(COMMANDS[key])

    def _events(self, events):
        game = self.game
        for event in events:
            if event == 'joined' and self.network and self.network.role == 'host':
                game.start_match(WORLD_WIDTH)
            elif event.startswith('input:') and self.network and self.network.role == 'host' and game.state == 'fight':
                apply_control(game, game.enemy, event.split(':', 1)[1], 1 / FPS)
            elif event in ('left','timeout','busy') and self.network:
                role = self.network.role
                self.network.reset_peer()
                game.state = 'hosting' if role == 'host' else 'searching'
                game.network_status = 'Peer unavailable — waiting again'
            elif event == 'connected':
                game.network_status = 'Connected'
            elif event == 'found':
                game.network_status = 'Server found — joining'

    def update(self, dt: float, held: set[str]):
        dt = max(0.0, min(0.05, dt))
        self._elapsed += dt
        self.tick = int(self._elapsed * FPS)
        if self.network:
            self._events(self.network.poll(self.game))
        self._held_time += dt
        if self._held_time >= 1 / FPS:
            self._held_time %= 1 / FPS
            if self.text_prompt is None:
                normalized = {COMMANDS[key] for key in held if key in COMMANDS}
                for command in ('block','crouch','left','right'):
                    if command in normalized:
                        self._command(command)
        if self.network is None:
            update_ai(self.game, dt)
            self.game.update(dt, WORLD_WIDTH)
        elif self.network.role == 'host' and self.network.peer:
            self.game.update(dt, WORLD_WIDTH)
        if self.network:
            self._events(self.network.tick(self.game))
