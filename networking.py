#!/usr/bin/env python3
"""Network discovery, transport, and game-state synchronization for NEON DOJO."""

from __future__ import annotations

import ipaddress
import json
import random
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable


GAME_PORT = 48765
DISCOVERY_PORT = GAME_PORT
PROTOCOL_VERSION = 3
MAX_NAME_LENGTH = 16


def normalize_player_name(value: object, fallback: str = "PLAYER") -> str:
    """Return a short, single-line name safe for display and transport."""
    if not isinstance(value, str):
        return fallback
    printable = "".join(character if character.isprintable() else " " for character in value)
    compact = " ".join(printable.split())
    return compact[:MAX_NAME_LENGTH] or fallback


def network_ready() -> tuple[bool, str]:
    """Check whether this runtime can create the TCP and UDP sockets we use."""
    udp_probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tcp_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        udp_probe.bind(("127.0.0.1", 0))
        tcp_probe.bind(("127.0.0.1", 0))
        return True, "TCP/UDP networking available"
    except OSError as error:
        return False, f"Network socket unavailable: {error}"
    finally:
        udp_probe.close()
        tcp_probe.close()


@dataclass(frozen=True)
class IPv4Interface:
    name: str
    address: str
    prefix_length: int
    broadcast: str


def ipv4_interfaces() -> list[IPv4Interface]:
    """Return active, non-container IPv4 interfaces without extra packages."""
    interfaces: list[IPv4Interface] = []
    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "address", "show", "up"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        records = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        records = []

    ignored_prefixes = ("br-", "docker", "veth", "virbr")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("ifname", ""))
            if name == "lo" or name.startswith(ignored_prefixes):
                continue
            for address_data in record.get("addr_info", []):
                if not isinstance(address_data, dict) or address_data.get("family") != "inet":
                    continue
                address = str(address_data.get("local", ""))
                try:
                    prefix_length = int(address_data.get("prefixlen", 24))
                    network = ipaddress.IPv4Network(f"{address}/{prefix_length}", strict=False)
                except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
                    continue
                broadcast = str(address_data.get("broadcast") or network.broadcast_address)
                interfaces.append(IPv4Interface(name, address, prefix_length, broadcast))

    if interfaces:
        return interfaces

    # Portable fallback for systems without Linux's `ip` command.
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            if info[4][0] != "127.0.0.1"
        }
    except OSError:
        addresses = set()
    for address in sorted(addresses):
        try:
            network = ipaddress.IPv4Network(f"{address}/24", strict=False)
        except ipaddress.AddressValueError:
            continue
        interfaces.append(IPv4Interface("network", address, 24, str(network.broadcast_address)))
    return interfaces


def _tailscale_targets(data: object) -> list[str]:
    """Expand online peers and bounded subnet routes from Tailscale status."""
    peers = data.get("Peer", {}) if isinstance(data, dict) else {}
    if not isinstance(peers, dict):
        return []
    addresses: set[str] = set()
    for peer in peers.values():
        if not isinstance(peer, dict) or peer.get("Online") is False:
            continue
        for address in peer.get("TailscaleIPs", []):
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if isinstance(parsed, ipaddress.IPv4Address):
                addresses.add(str(parsed))
        for route in peer.get("PrimaryRoutes", []):
            try:
                network = ipaddress.ip_network(route, strict=False)
            except ValueError:
                continue
            if not isinstance(network, ipaddress.IPv4Network) or network.num_addresses > 256:
                continue
            addresses.update(str(address) for address in network.hosts())
    return sorted(addresses, key=ipaddress.IPv4Address)


def tailscale_peer_addresses() -> list[str]:
    """Read peer and subnet-route targets from the optional Tailscale CLI."""
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    return _tailscale_targets(data)


def discovery_broadcast_addresses(
    interfaces: list[IPv4Interface] | None = None,
) -> list[str]:
    interfaces = ipv4_interfaces() if interfaces is None else interfaces
    return list(dict.fromkeys(["255.255.255.255", "127.0.0.1", *(item.broadcast for item in interfaces)]))


def discovery_probe_addresses(
    interfaces: list[IPv4Interface] | None = None,
    tailscale_peers: list[str] | None = None,
) -> list[str]:
    """Build LAN broadcasts and bounded unicast probes for routed overlays."""
    interfaces = ipv4_interfaces() if interfaces is None else interfaces
    tailscale_peers = tailscale_peer_addresses() if tailscale_peers is None else tailscale_peers
    targets = discovery_broadcast_addresses(interfaces)
    targets.extend(tailscale_peers)
    for interface in interfaces:
        try:
            # Scan at most one /24 per interface to keep discovery bounded on
            # large corporate, VPN, and container networks.
            prefix_length = max(24, interface.prefix_length)
            network = ipaddress.IPv4Network(
                f"{interface.address}/{prefix_length}",
                strict=False,
            )
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            continue
        targets.extend(str(address) for address in network.hosts())

    # Tailscale is layer 3 and does not carry broadcasts. This project's
    # tailnet uses 100.64.0.0/24, so probe that bounded range with unicast.
    targets.extend(str(address) for address in ipaddress.IPv4Network("100.64.0.0/24").hosts())
    local_addresses = {item.address for item in interfaces}
    return [address for address in dict.fromkeys(targets) if address not in local_addresses]


def _fighter_data(fighter: Any) -> dict[str, object]:
    return {
        "name": fighter.name,
        "x": fighter.x,
        "color": fighter.color,
        "facing": fighter.facing,
        "health": fighter.health,
        "meter": fighter.meter,
        "wins": fighter.wins,
        "jump_y": fighter.jump_y,
        "velocity_y": fighter.velocity_y,
        "action": fighter.action,
        "action_time": fighter.action_time,
        "action_hit": fighter.action_hit,
        "hitstun": fighter.hitstun,
        "block_time": fighter.block_time,
        "flash_time": fighter.flash_time,
        "combo": fighter.combo,
        "combo_time": fighter.combo_time,
    }


def game_to_data(game: Any) -> dict[str, object]:
    """Create the small authoritative snapshot sent by a host."""
    return {
        "state": game.state,
        "round_number": game.round_number,
        "round_time": game.round_time,
        "state_time": game.state_time,
        "banner": game.banner,
        "message": game.message,
        "shake": game.shake,
        "freeze": game.freeze,
        "round_winner": game.round_winner,
        "story_phase": game.story_phase,
        "player": _fighter_data(game.player),
        "enemy": _fighter_data(game.enemy),
        "particles": [p.__dict__ for p in game.particles[-32:]],
    }


def apply_game_data(
    game: Any,
    data: object,
    fighter_type: type[Any],
    particle_type: type[Any],
) -> bool:
    """Apply a validated-enough network snapshot without trusting extra keys."""
    if not isinstance(data, dict):
        return False
    try:
        state = str(data["state"])
        if state not in {"intro", "fight", "finisher", "round_over", "wedding", "match_over", "paused"}:
            return False
        player_data = data["player"]
        enemy_data = data["enemy"]
        if not isinstance(player_data, dict) or not isinstance(enemy_data, dict):
            return False
        player = fighter_type(**{key: player_data[key] for key in fighter_type.__dataclass_fields__})
        enemy = fighter_type(**{key: enemy_data[key] for key in fighter_type.__dataclass_fields__})
        particles_raw = data.get("particles", [])
        particles = [particle_type(**item) for item in particles_raw if isinstance(item, dict)]
        game.state = state
        game.round_number = int(data["round_number"])
        game.round_time = float(data["round_time"])
        game.state_time = float(data["state_time"])
        game.banner = str(data["banner"])
        game.message = str(data["message"])
        game.shake = float(data["shake"])
        game.freeze = float(data["freeze"])
        round_winner = int(data["round_winner"])
        if round_winner not in (-1, 0, 1):
            return False
        game.round_winner = round_winner
        game.story_phase = max(0, min(2, int(data["story_phase"])))
        game.player = player
        game.enemy = enemy
        game.particles = particles[:32]
    except (KeyError, TypeError, ValueError):
        return False
    return True


def local_ip_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


def local_server_addresses() -> str:
    addresses = list(dict.fromkeys(item.address for item in ipv4_interfaces()))
    if not addresses:
        addresses = [local_ip_address()]
    return " / ".join(f"{address}:{GAME_PORT}" for address in addresses)


def parse_server_address(value: str) -> tuple[str, int]:
    value = value.strip()
    if not value:
        raise ValueError("server address is empty")
    host = value
    port = GAME_PORT
    if value.count(":") == 1:
        host, raw_port = value.rsplit(":", 1)
        if raw_port:
            port = int(raw_port)
    if not (1 <= port <= 65535):
        raise ValueError("port must be between 1 and 65535")
    return socket.gethostbyname(host), port


class NetworkSession:
    """UDP discovery with a reliable TCP gameplay connection.

    Both roles listen on the gameplay port. Usually the joining player connects
    to the host. On asymmetric networks the host can instead connect outward to
    the waiting player with ``invite_player``.
    """

    def __init__(
        self,
        role: str,
        player_name: str = "PLAYER",
        *,
        state_encoder: Callable[[Any], dict[str, object]] = game_to_data,
        state_applier: Callable[[Any, object], bool] | None = None,
        name_normalizer: Callable[[object], str] = normalize_player_name,
    ) -> None:
        if role not in {"host", "client"}:
            raise ValueError("network role must be 'host' or 'client'")
        if role == "client" and state_applier is None:
            raise ValueError("joining clients require a state_applier callback")
        self.role = role
        self.player_name = name_normalizer(player_name)
        self.state_encoder = state_encoder
        self.state_applier = state_applier
        self.name_normalizer = name_normalizer
        self.peer: tuple[str, int] | None = None
        self.last_send = 0.0
        self.last_seen = time.monotonic()
        self.session_id = f"{random.getrandbits(48):012x}"
        self.connected = False
        self.connection: socket.socket | None = None
        self.connection_lost = False
        self.receive_buffer = bytearray()
        self.send_buffer = bytearray()
        self.discovery_targets: list[str] = []
        self.discovery_broadcasts = discovery_broadcast_addresses()
        self.discovery_cursor = 0
        self.last_discovery_cycle = time.monotonic()

        self.discovery = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.discovery.bind(("0.0.0.0", DISCOVERY_PORT))
        self.discovery.setblocking(False)
        if role == "client":
            self.discovery_targets = discovery_probe_addresses()

        self.listener: socket.socket | None = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.listener.bind(("0.0.0.0", GAME_PORT))
            self.listener.listen(2)
            self.listener.setblocking(False)
        except OSError:
            self.listener.close()
            self.listener = None
            if role == "host":
                self.discovery.close()
                raise

    def _send_discovery(self, payload: dict[str, object], address: tuple[str, int]) -> None:
        try:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.discovery.sendto(encoded, address)
        except (OSError, TypeError, ValueError):
            pass

    def _announcement(self) -> dict[str, object]:
        return {
            "v": PROTOCOL_VERSION,
            "t": "announce",
            "port": GAME_PORT,
            "id": self.session_id,
        }

    def _send_discovery_probes(self, now: float) -> None:
        if self.role != "client" or self.connection is not None:
            return
        if self.discovery_cursor >= len(self.discovery_targets):
            if now - self.last_discovery_cycle < 2.0:
                return
            self.discovery_cursor = 0
            self.last_discovery_cycle = now
        probe = {"v": PROTOCOL_VERSION, "t": "discover"}
        stop = min(len(self.discovery_targets), self.discovery_cursor + 32)
        for address in self.discovery_targets[self.discovery_cursor:stop]:
            self._send_discovery(probe, (address, DISCOVERY_PORT))
        self.discovery_cursor = stop

    def _queue(self, payload: dict[str, object]) -> None:
        if self.connection is None:
            return
        try:
            packet = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        except (TypeError, ValueError):
            return
        if len(self.send_buffer) > 262_144 and payload.get("t") == "state":
            self.send_buffer.clear()
        self.send_buffer.extend(packet)
        self._flush()

    def _flush(self) -> None:
        if self.connection is None or not self.send_buffer:
            return
        try:
            sent = self.connection.send(self.send_buffer)
            del self.send_buffer[:sent]
        except BlockingIOError:
            pass
        except OSError:
            self.connection_lost = True
            self._drop_connection()

    def _set_connection(self, connection: socket.socket, address: tuple[str, int]) -> None:
        connection.setblocking(False)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.connection = connection
        self.peer = address
        self.receive_buffer.clear()
        self.send_buffer.clear()
        self.connected = False
        self.last_seen = time.monotonic()
        self.last_send = 0.0

    def _connect(self, address: tuple[str, int]) -> None:
        if self.connection is not None:
            self._drop_connection()
        self.connection_lost = False
        connection = socket.create_connection(address, timeout=1.5)
        self._set_connection(connection, address)

    def connect_direct(self, value: str) -> str:
        if self.role != "client":
            raise ValueError("only a joining player can connect to a server")
        address = parse_server_address(value)
        self._connect(address)
        self._queue({"v": PROTOCOL_VERSION, "t": "join", "name": self.player_name})
        return f"Connecting to {address[0]}:{address[1]}"

    def invite_player(self, value: str) -> str:
        if self.role != "host":
            raise ValueError("only a host can invite a waiting player")
        address = parse_server_address(value)
        self._connect(address)
        return f"Inviting player at {address[0]}:{address[1]}"

    def send_command(self, command: str) -> None:
        if self.role == "client" and self.connection:
            self._queue({"v": PROTOCOL_VERSION, "t": "input", "key": command})

    def _accept_connections(self, events: list[str]) -> None:
        if self.listener is None:
            return
        while True:
            try:
                connection, address = self.listener.accept()
            except BlockingIOError:
                break
            except OSError:
                break
            if self.connection is not None:
                try:
                    connection.sendall(json.dumps({"v": PROTOCOL_VERSION, "t": "busy"}).encode() + b"\n")
                except OSError:
                    pass
                connection.close()
                continue
            self._set_connection(connection, address)
            if self.role == "client":
                self._queue({"v": PROTOCOL_VERSION, "t": "join", "name": self.player_name})
                events.append("found")

    def _poll_discovery(self, events: list[str]) -> None:
        while True:
            try:
                packet, address = self.discovery.recvfrom(8192)
            except BlockingIOError:
                break
            except OSError:
                break
            try:
                data = json.loads(packet.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or data.get("v") != PROTOCOL_VERSION:
                continue
            kind = data.get("t")
            if kind == "discover" and self.role == "host" and self.connection is None:
                self._send_discovery(self._announcement(), address)
                continue
            if kind != "announce" or self.role != "client" or self.connection is not None:
                continue
            try:
                port = int(data.get("port", GAME_PORT))
            except (TypeError, ValueError):
                continue
            if not (1 <= port <= 65535):
                continue
            try:
                self._connect((address[0], port))
            except OSError:
                continue
            self._queue({"v": PROTOCOL_VERSION, "t": "join", "name": self.player_name})
            events.append("found")
            break

    def _poll_stream(self, game: Any, events: list[str]) -> None:
        if self.connection is None:
            return
        while True:
            try:
                packet = self.connection.recv(65536)
            except BlockingIOError:
                break
            except OSError:
                packet = b""
            if not packet:
                events.append("left")
                self._drop_connection()
                return
            self.receive_buffer.extend(packet)
            if len(self.receive_buffer) > 1_048_576:
                events.append("left")
                self._drop_connection()
                return
        while b"\n" in self.receive_buffer:
            raw, _, remainder = self.receive_buffer.partition(b"\n")
            self.receive_buffer = bytearray(remainder)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or data.get("v") != PROTOCOL_VERSION:
                continue
            self.last_seen = time.monotonic()
            kind = data.get("t")
            if self.role == "host":
                if kind == "join" and not self.connected:
                    game.enemy.name = self.name_normalizer(data.get("name", "PLAYER"))
                    self.connected = True
                    events.append("joined")
                elif kind == "input" and isinstance(data.get("key"), str):
                    events.append(f"input:{data['key']}")
                elif kind == "leave":
                    events.append("left")
                    self._drop_connection()
                    return
            else:
                if kind == "state" and self.state_applier and self.state_applier(game, data.get("game")):
                    was_connected = self.connected
                    self.connected = True
                    if not was_connected:
                        events.append("connected")
                elif kind == "busy":
                    events.append("busy")
                    self._drop_connection()
                    return
                elif kind == "leave":
                    events.append("left")
                    self._drop_connection()
                    return

    def poll(self, game: Any) -> list[str]:
        events: list[str] = []
        if self.connection_lost:
            events.append("left")
            self.connection_lost = False
        self._accept_connections(events)
        self._poll_discovery(events)
        self._poll_stream(game, events)
        self._flush()
        return events

    def tick(self, game: Any) -> list[str]:
        now = time.monotonic()
        events: list[str] = []
        if self.role == "host":
            if self.connection is None and now - self.last_send >= 0.75:
                announcement = self._announcement()
                for address in self.discovery_broadcasts:
                    self._send_discovery(announcement, (address, DISCOVERY_PORT))
                self.last_send = now
            elif self.connected and now - self.last_send >= 1 / 20:
                self._queue({"v": PROTOCOL_VERSION, "t": "state", "game": self.state_encoder(game)})
                self.last_send = now
        else:
            self._send_discovery_probes(now)
            if self.connection and now - self.last_send >= 0.5:
                self._queue({"v": PROTOCOL_VERSION, "t": "ping"})
                self.last_send = now
        self._flush()
        if self.connection and now - self.last_seen > 7.0:
            events.append("timeout")
        return events

    def _drop_connection(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            except OSError:
                pass
        self.connection = None
        self.peer = None
        self.connected = False
        self.receive_buffer.clear()
        self.send_buffer.clear()

    def close(self) -> None:
        if self.connection:
            self._queue({"v": PROTOCOL_VERSION, "t": "leave"})
            self._flush()
        self._drop_connection()
        for sock in (self.listener, self.discovery):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def reset_peer(self) -> None:
        self._drop_connection()
        self.last_seen = time.monotonic()
        self.last_send = 0.0
