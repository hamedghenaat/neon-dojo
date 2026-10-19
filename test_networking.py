import unittest

from neon_dojo import Fighter, Game, Particle
from networking import (
    DISCOVERY_PORT,
    GAME_PORT,
    IPv4Interface,
    _tailscale_targets,
    apply_game_data,
    discovery_broadcast_addresses,
    discovery_probe_addresses,
    game_to_data,
    parse_server_address,
)


class NetworkingTests(unittest.TestCase):
    def test_network_snapshot_round_trip(self):
        game = Game(Fighter("P1", 20, 2), Fighter("CPU", 27, 3, facing=-1), state="finisher")
        game.player.meter = 72
        game.round_winner = 1
        game.story_phase = 2
        game.particles = [Particle(1, 2, 3, 4, 0.5, "*", 4)]
        clone = Game(Fighter("A", 0, 1), Fighter("B", 0, 1))
        self.assertTrue(apply_game_data(clone, game_to_data(game), Fighter, Particle))
        self.assertEqual(clone.player.meter, 72)
        self.assertEqual(clone.state, "finisher")
        self.assertEqual(clone.round_winner, 1)
        self.assertEqual(clone.story_phase, 2)
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


if __name__ == "__main__":
    unittest.main()
