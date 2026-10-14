"""The engine: turns WSJT-X datagrams into a read-only snapshot. No sockets, no Qt."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from wsjtx_free_freq.codec import Status, decode, encode_configure


class Slot(Enum):
    """Alternating set of cycles: FIRST is even cycles, SECOND is odd."""

    FIRST = "1st"
    SECOND = "2nd"


@dataclass(frozen=True)
class Settings:
    """Every setting the engine reads, with the spec's defaults."""

    search_low_hz: int = 200
    search_high_hz: int = 2800
    guard_hz: int = 10
    window_cycles: int = 4
    min_spacing_widths: float = 2.0
    min_clearance_hz: int = 10
    strong_enabled: bool = False
    strong_snr_db: int = 10
    strong_extra_hz: int = 20
    heartbeat_timeout_s: float = 45.0


@dataclass(frozen=True)
class Occupied:
    """A decode in the occupancy window and the audio range it blocks."""

    offset_hz: int
    snr_db: int
    age_cycles: int
    blocked_low_hz: int
    blocked_high_hz: int


@dataclass(frozen=True)
class FreeLocation:
    """A free audio offset, ranked by its clearance from occupancy."""

    rank: int
    offset_hz: int
    clearance_hz: int


@dataclass(frozen=True)
class SlotView:
    """Occupancy and free locations for one slot of one instance."""

    occupied: tuple[Occupied, ...]
    free: tuple[FreeLocation, ...]
    decode_count: int


@dataclass(frozen=True)
class InstanceView:
    """One WSJT-X instance as the snapshot shows it."""

    id: str
    connected: bool
    dial_hz: int | None
    mode: str | None
    rx_hz: int | None
    tx_hz: int | None
    slots: Mapping[Slot, SlotView]


@dataclass(frozen=True)
class Outgoing:
    """A datagram to send to one WSJT-X instance, and the address it goes to."""

    payload: bytes
    address: tuple[str, int]


@dataclass(frozen=True)
class Snapshot:
    """Every known instance, in the order each was first heard."""

    instances: tuple[InstanceView, ...]


class UnknownInstanceError(LookupError):
    """No WSJT-X instance with that id has been heard."""


class _Instance:
    def __init__(self, msg_id: str) -> None:
        self.id = msg_id
        self.sender: tuple[str, int] = ("", 0)
        self.schema = 0
        self.last_seen = 0.0
        self.status: Status | None = None


def _empty_slots() -> Mapping[Slot, SlotView]:
    return MappingProxyType({slot: SlotView(occupied=(), free=(), decode_count=0) for slot in Slot})


DEFAULT_SETTINGS = Settings()


class Engine:
    """Receives WSJT-X datagrams and reports what each instance is doing."""

    def __init__(self, settings: Settings = DEFAULT_SETTINGS) -> None:
        self._settings = settings
        self._instances: dict[str, _Instance] = {}

    @property
    def settings(self) -> Settings:
        """Current settings; replacing them takes effect on the next snapshot."""
        return self._settings

    @settings.setter
    def settings(self, value: Settings) -> None:
        self._settings = value

    def receive(self, datagram: bytes, sender: tuple[str, int], now: float) -> None:
        """Feed one datagram. Anything that is not a Heartbeat or Status is ignored."""
        message = decode(datagram)
        if message is None:
            return
        instance = self._instances.get(message.id)
        if instance is None:
            instance = _Instance(message.id)
            self._instances[message.id] = instance
        instance.sender = sender
        instance.schema = message.schema
        instance.last_seen = now
        if isinstance(message, Status):
            instance.status = message

    def snapshot(self, now: float) -> Snapshot:
        """Return the state of every instance as of time `now`."""
        return Snapshot(instances=tuple(self._view(inst, now) for inst in self._instances.values()))

    def set_rx(self, instance_id: str, offset_hz: int) -> Outgoing:
        """Build the Configure that moves an instance's Rx audio offset. Never touches Tx."""
        inst = self._instances.get(instance_id)
        if inst is None:
            msg = f"unknown WSJT-X instance {instance_id!r}"
            raise UnknownInstanceError(msg)
        fast_mode = inst.status is not None and inst.status.fast_mode is True
        payload = encode_configure(inst.schema, inst.id, rx_df=offset_hz, fast_mode=fast_mode)
        return Outgoing(payload=payload, address=inst.sender)

    def _view(self, inst: _Instance, now: float) -> InstanceView:
        status = inst.status
        return InstanceView(
            id=inst.id,
            connected=now - inst.last_seen <= self._settings.heartbeat_timeout_s,
            dial_hz=None if status is None else status.dial_hz,
            mode=None if status is None else status.mode,
            rx_hz=None if status is None else status.rx_df,
            tx_hz=None if status is None else status.tx_df,
            slots=_empty_slots(),
        )
