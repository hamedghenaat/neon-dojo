import unittest
import os
import tempfile
from unittest.mock import patch

from neon_dojo import (
    ATTACKS,
    GAME_PORT,
    SPRITE_WIDTH,
    Fighter,
    Game,
    Particle,
    _save_setup_cache,
    _setup_cache_matches,
    apply_game_data,
    bar,
    fighter_sprite,
    game_to_data,
    mirrored,
    parse_server_address,
    dependency_checks,
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
        self.assertEqual(game.banner, "CHAMPION: VOLT")

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


if __name__ == "__main__":
    unittest.main()
