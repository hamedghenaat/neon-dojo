import unittest
import curses
import os
import tempfile
from unittest.mock import patch

from neon_dojo import (
    ATTACKS,
    DISCOVERY_PORT,
    GAME_PORT,
    IPv4Interface,
    SPRITE_WIDTH,
    Fighter,
    Game,
    Particle,
    PlayerSettings,
    _tailscale_targets,
    _save_setup_cache,
    _setup_cache_matches,
    apply_game_data,
    bar,
    control_from_key,
    fighter_sprite,
    game_to_data,
    load_settings,
    mirrored,
    normalize_character_name,
    parse_server_address,
    save_settings,
    dependency_checks,
    discovery_broadcast_addresses,
    discovery_probe_addresses,
)


class CombatTests(unittest.TestCase):
    def make_game(self):
        return Game(Fighter("P1", 20, 2), Fighter("CPU", 27, 3, facing=-1), state="fight")

    def test_attack_connects_once(self):
        game = self.make_game()
        self.assertTrue(game.player.start_attack("punch"))
        game.player.action_time = ATTACKS["punch"].active_from
        game.resolve_attack(game.player, game.enemy)
        health = game.enemy.health
        game.resolve_attack(game.player, game.enemy)
        self.assertEqual(health, 93)
        self.assertEqual(game.enemy.health, health)

    def test_block_reduces_damage(self):
        game = self.make_game()
        game.enemy.block_time = 1.0
        game.player.start_attack("kick")
        game.player.action_time = ATTACKS["kick"].active_from
        game.resolve_attack(game.player, game.enemy)
        self.assertEqual(game.enemy.health, 97)

    def test_special_spends_meter(self):
        game = self.make_game()
        self.assertFalse(game.player.start_attack("special"))
        game.player.meter = 35
        self.assertTrue(game.player.start_attack("special"))
        self.assertEqual(game.player.meter, 0)

    def test_jump_lands(self):
        game = self.make_game()
        game.jump(game.player)
        for _ in range(120):
            game.player.update(1 / 60)
        self.assertEqual(game.player.jump_y, 0)
        self.assertEqual(game.player.action, "idle")

    def test_walk_pose_returns_to_idle(self):
        fighter = Fighter("P1", 20, 2)
        fighter.action = "walk"
        fighter.update(0.13)
        self.assertEqual(fighter.action, "idle")

    def test_best_of_three_reaches_match_result(self):
        game = self.make_game()
        game.player.wins = 1
        game.enemy.health = 0
        game.end_round()
        self.assertEqual(game.player.wins, 2)
        game.advance(100)
        self.assertEqual(game.state, "match_over")
        self.assertEqual(game.banner, "CHAMPION: P1")

    def test_crouch_uses_shorter_pose_then_stands(self):
        game = self.make_game()
        self.assertEqual(control_from_key(curses.KEY_DOWN), "crouch")
        game.crouch(game.player)
        crouching = fighter_sprite(game.player, 0)
        self.assertEqual(game.player.action, "crouch")
        self.assertEqual(sum(bool(line.strip()) for line in crouching), 7)
        game.player.update(0.46)
        self.assertEqual(game.player.action, "idle")

    def test_health_bar_directions(self):
        self.assertEqual(bar(50, 100, 6), "███░░░")
        self.assertEqual(bar(50, 100, 6, False), "░░░███")

    def test_mirror_is_reversible(self):
        art = [" /[>]\\ "]
        self.assertEqual(mirrored(mirrored(art)), art)

    def test_knight_sprite_has_stable_grid_and_mirrors(self):
        fighter = Fighter("P1", 20, 2)
        facing_right = fighter_sprite(fighter, 0)
        fighter.facing = -1
        facing_left = fighter_sprite(fighter, 0)
        self.assertTrue(all(len(line) == SPRITE_WIDTH for line in facing_right))
        self.assertEqual(facing_left, [line[::-1] for line in facing_right])
        self.assertIn("E", "".join(facing_right))
        self.assertIn("S", "".join(facing_right))

    def test_network_snapshot_round_trip(self):
        game = self.make_game()
        game.player.meter = 72
        game.particles = [Particle(1, 2, 3, 4, 0.5, "*", 4)]
        clone = Game(Fighter("A", 0, 1), Fighter("B", 0, 1))
        self.assertTrue(apply_game_data(clone, game_to_data(game)))
        self.assertEqual(clone.player.meter, 72)
        self.assertEqual(clone.particles[0].char, "*")

    def test_direct_server_address(self):
        self.assertEqual(parse_server_address("127.0.0.1"), ("127.0.0.1", GAME_PORT))
        self.assertEqual(parse_server_address("127.0.0.1:5000"), ("127.0.0.1", 5000))

    def test_discovery_covers_each_interface_and_tailscale_unicast(self):
        interfaces = [
            IPv4Interface("eno1", "172.16.86.200", 24, "172.16.86.255"),
            IPv4Interface("tailscale0", "100.64.0.8", 32, "100.64.0.8"),
        ]
        broadcasts = discovery_broadcast_addresses(interfaces)
        probes = discovery_probe_addresses(interfaces, ["100.64.0.12"])
        self.assertEqual(DISCOVERY_PORT, GAME_PORT)
        self.assertIn("172.16.86.255", broadcasts)
        self.assertIn("172.16.86.70", probes)
        self.assertIn("100.64.0.12", probes)
        self.assertIn("100.64.0.70", probes)
        self.assertNotIn("100.64.0.8", probes)

    def test_tailscale_subnet_routes_become_discovery_targets(self):
        status = {
            "Peer": {
                "router": {
                    "Online": True,
                    "TailscaleIPs": ["100.64.0.12", "fd7a:115c:a1e0::c"],
                    "PrimaryRoutes": ["2.1.1.0/24", "0.0.0.0/0"],
                },
                "offline": {
                    "Online": False,
                    "TailscaleIPs": ["100.64.0.99"],
                },
            }
        }
        targets = _tailscale_targets(status)
        self.assertIn("100.64.0.12", targets)
        self.assertIn("2.1.1.70", targets)
        self.assertNotIn("100.64.0.99", targets)

    def test_dependency_checks_cover_runtime_features(self):
        results = dependency_checks()
        self.assertEqual({item.key for item in results}, {"python", "curses", "unicode", "network"})
        self.assertTrue(all(item.ready for item in results))

    def test_successful_setup_is_cached(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.dict(os.environ, {"XDG_CACHE_HOME": cache_dir}):
                self.assertFalse(_setup_cache_matches())
                _save_setup_cache()
                self.assertTrue(_setup_cache_matches())

    def test_custom_character_name_is_sanitized_and_persisted(self):
        with tempfile.TemporaryDirectory() as config_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": config_dir}):
                settings = PlayerSettings("custom", normalize_character_name("  Neon\nKnight  "))
                self.assertTrue(save_settings(settings))
                loaded = load_settings()
                self.assertEqual(loaded.character_name, "Neon Knight")
                self.assertEqual(loaded.name_source, "custom")


if __name__ == "__main__":
    unittest.main()
