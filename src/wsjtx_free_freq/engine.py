"""The engine: turns WSJT-X datagrams into a read-only snapshot. No sockets, no Qt."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from wsjtx_free_freq.codec import Clear, Close, Decode, Status, decode, encode_configure

DAY_MS = 86_400_000
FREE_STEP_HZ = 5
MAX_FREE_LOCATIONS = 10
MAX_WINDOW_CYCLES = 100  # largest occupancy window a user may set; persistence bounds to this
_HISTORY_CYCLES = 2 * MAX_WINDOW_CYCLES  # a decode this many cycles behind the latest can never be in any window


@dataclass(frozen=True)
class _ModeSpec:
    """What the engine needs to know about one WSJT-X mode."""

    symbol: str  # mode symbol in Decode messages
    cycle_ms: int  # fixed T/R period; Status's whole-second T/R period would truncate FT4's 7.5 s, so it is ignored
    signal_width_hz: int


_FT8 = _ModeSpec(symbol="~", cycle_ms=15_000, signal_width_hz=50)
MODES: Mapping[str, _ModeSpec] = MappingProxyType({"FT8": _FT8, "FT4": _ModeSpec("+", 7_500, 83)})
WIDEST_SIGNAL_HZ = max(spec.signal_width_hz for spec in MODES.values())


def _mode_of(status: Status | None) -> _ModeSpec | None:
    """Look up the mode Status names, FT8 before any Status; None for a mode this engine does not know."""
    name = status.mode if status is not None and status.mode is not None else "FT8"
    return MODES.get(name)


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
    """A free audio offset, ranked by its age-weighted clearance; gap_hz is the physical distance shown on its button."""

    rank: int
    offset_hz: int
    clearance_hz: int
    gap_hz: int


@dataclass(frozen=True)
class SlotView:
    """Occupancy and free locations for one slot of one instance."""

    occupied: tuple[Occupied, ...]
    free: tuple[FreeLocation, ...]
    decode_count: int


EMPTY_SLOT = SlotView(occupied=(), free=(), decode_count=0)


@dataclass(frozen=True)
class InstanceView:
    """One WSJT-X instance as the snapshot shows it."""

    id: str
    connected: bool
    dial_hz: int | None
    mode: str | None
    supported: bool  # False for a mode outside MODES; the slots then hold nothing to show
    signal_width_hz: int | None  # None when unsupported
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


@dataclass(frozen=True)
class _Heard:
    """An FT8 decode as the occupancy needs it: its cycle number, audio offset and SNR."""

    cycle: int
    offset_hz: int
    snr_db: int


class _Instance:
    def __init__(self, msg_id: str) -> None:
        self.id = msg_id
        self.sender: tuple[str, int] = ("", 0)
        self.schema = 0
        self.last_seen = 0.0
        self.closed = False
        self.status: Status | None = None
        self.heard: list[_Heard] = []
        self.latest_cycle: int | None = None
        self.seen: set[tuple[int, int, str]] = set()  # unwrapped time_ms, delta_hz, message of each held decode


def _slot_views(
    heard: list[_Heard], latest: int, settings: Settings, tx_hz: int | None, width_hz: int
) -> Mapping[Slot, SlotView]:
    views: dict[Slot, SlotView] = {}
    for slot in Slot:
        in_slot = [h for h in heard if _slot_of(h.cycle) is slot]
        views[slot] = _slot_view(in_slot, _current_cycle(slot, latest), settings, tx_hz, width_hz)
    return MappingProxyType(views)


def _current_cycle(slot: Slot, latest: int) -> int:
    """Return the newest cycle of `slot` that has begun by `latest`: `latest` itself, or the one before it for the other slot."""
    return latest if _slot_of(latest) is slot else latest - 1


def _unwrap(cycle_of_day: int, latest: int | None, cycles_per_day: int) -> int:
    """Put a time-of-day cycle on the timeline nearest the latest seen, so a decode after midnight follows one before it."""
    if latest is None:
        return cycle_of_day
    days = (latest - cycle_of_day + cycles_per_day // 2) // cycles_per_day
    return cycle_of_day + days * cycles_per_day


def _slot_of(cycle: int) -> Slot:
    return Slot.FIRST if cycle % 2 == 0 else Slot.SECOND


def _guard_hz(snr_db: int, settings: Settings) -> int:
    strong = settings.strong_enabled and snr_db >= settings.strong_snr_db
    return settings.guard_hz + (settings.strong_extra_hz if strong else 0)


def _slot_view(heard: list[_Heard], current: int, settings: Settings, tx_hz: int | None, width_hz: int) -> SlotView:
    if not heard:
        return SlotView(occupied=(), free=_free_locations((), settings, tx_hz, width_hz), decode_count=0)
    occupied = tuple(
        Occupied(
            offset_hz=h.offset_hz,
            snr_db=h.snr_db,
            age_cycles=age,
            blocked_low_hz=h.offset_hz - _guard_hz(h.snr_db, settings),
            blocked_high_hz=h.offset_hz + width_hz + _guard_hz(h.snr_db, settings),
        )
        # a slot's cycles are two apart, so its age in cycles is half the gap from the slot's current cycle
        for h in heard
        if (age := (current - h.cycle) // 2) < settings.window_cycles
    )
    return SlotView(
        occupied=occupied, free=_free_locations(occupied, settings, tx_hz, width_hz), decode_count=len(occupied)
    )


def _free_locations(
    occupied: tuple[Occupied, ...], settings: Settings, tx_hz: int | None, width_hz: int
) -> tuple[FreeLocation, ...]:
    span = settings.search_high_hz - settings.search_low_hz
    offsets = range(settings.search_low_hz, settings.search_high_hz - width_hz + 1, FREE_STEP_HZ)
    scored: list[tuple[int, int, int]] = []
    for offset in offsets:
        # gap is how far the candidate's span sits from each blocked range; overlap means no gap
        gaps = [max(o.blocked_low_hz - (offset + width_hz), offset - o.blocked_high_hz) for o in occupied]
        if any(gap <= 0 for gap in gaps):
            continue
        clearance = min((gap * (1 + o.age_cycles) for gap, o in zip(gaps, occupied, strict=True)), default=span)
        gap = min(gaps, default=span)
        scored.append((clearance, gap, offset))
    # ties go to the candidate nearest Tx; with Tx unknown they fall back to the lower offset
    scored.sort(key=lambda item: (-item[0], 0 if tx_hz is None else abs(item[2] - tx_hz), item[2]))
    spacing_hz = settings.min_spacing_widths * width_hz
    chosen: list[tuple[int, int, int]] = []
    for clearance, gap, offset in scored:
        if clearance < settings.min_clearance_hz:
            continue
        if any(abs(offset - other) < spacing_hz for _, _, other in chosen):
            continue
        chosen.append((clearance, gap, offset))
        if len(chosen) == MAX_FREE_LOCATIONS:
            break
    return tuple(
        FreeLocation(rank=rank, offset_hz=offset, clearance_hz=clearance, gap_hz=gap)
        for rank, (clearance, gap, offset) in enumerate(chosen, start=1)
    )


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
        """Feed one datagram. Anything that is not a Heartbeat, Status, Decode or Close is ignored; Clear is ignored too."""
        message = decode(datagram)
        if message is None or isinstance(message, Clear):
            return
        instance = self._instances.get(message.id)
        if instance is None:
            if isinstance(message, Close):
                return  # never heard from it, so there is nothing to disconnect
            instance = _Instance(message.id)
            self._instances[message.id] = instance
        instance.sender = sender
        instance.schema = message.schema
        instance.last_seen = now
        instance.closed = isinstance(message, Close)
        if isinstance(message, Status):
            previous = instance.status
            if previous is not None and (previous.dial_hz, previous.mode) != (message.dial_hz, message.mode):
                instance.heard.clear()  # a new dial frequency or mode invalidates all occupancy
                instance.seen.clear()
            instance.status = message
        mode = _mode_of(instance.status)
        if (
            isinstance(message, Decode)
            and mode is not None
            and message.mode == mode.symbol
            and not message.off_air
            and message.time_ms < DAY_MS
        ):
            cycle_ms = mode.cycle_ms
            cycle = _unwrap(message.time_ms // cycle_ms, instance.latest_cycle, DAY_MS // cycle_ms)
            before = instance.latest_cycle
            latest = cycle if before is None else max(before, cycle)
            instance.latest_cycle = latest
            floor = latest - _HISTORY_CYCLES
            if latest != before:
                # forget what has aged past any window; only a newer cycle can do that, so prune only then
                instance.heard = [h for h in instance.heard if h.cycle >= floor]
                instance.seen = {k for k in instance.seen if k[0] >= floor * cycle_ms}
            if cycle >= floor:
                key = (cycle * cycle_ms + message.time_ms % cycle_ms, message.delta_hz, message.message)
                if key not in instance.seen:
                    instance.seen.add(key)
                    instance.heard.append(_Heard(cycle, message.delta_hz, message.snr_db))

    def snapshot(self, now: float) -> Snapshot:
        """Return the state of every instance as of time `now`."""
        return Snapshot(instances=tuple(self._view(inst, now) for inst in self._instances.values()))

    def set_rx(self, instance_id: str, offset_hz: int) -> Outgoing:
        """Build the Configure that moves an instance's Rx audio offset. Never touches Tx."""
        if offset_hz < 0:
            msg = "Rx offset must not be negative"
            raise ValueError(msg)
        inst = self._instances.get(instance_id)
        if inst is None:
            msg = f"unknown WSJT-X instance {instance_id!r}"
            raise UnknownInstanceError(msg)
        fast_mode = inst.status is not None and inst.status.fast_mode is True
        payload = encode_configure(inst.schema, inst.id, rx_df=offset_hz, fast_mode=fast_mode)
        return Outgoing(payload=payload, address=inst.sender)

    def _view(self, inst: _Instance, now: float) -> InstanceView:
        status = inst.status
        mode = _mode_of(status)
        if mode is None:  # unsupported mode: no width to compute free locations with, so claim none
            slots: Mapping[Slot, SlotView] = MappingProxyType(dict.fromkeys(Slot, EMPTY_SLOT))
        else:
            slots = _slot_views(
                inst.heard,
                inst.latest_cycle or 0,  # heard is empty until a cycle is known, so this 0 is never read
                self._settings,
                None if status is None else status.tx_df,
                mode.signal_width_hz,
            )
        return InstanceView(
            id=inst.id,
            connected=not inst.closed and now - inst.last_seen <= self._settings.heartbeat_timeout_s,
            dial_hz=None if status is None else status.dial_hz,
            mode=None if status is None else status.mode,
            supported=mode is not None,
            signal_width_hz=None if mode is None else mode.signal_width_hz,
            rx_hz=None if status is None else status.rx_df,
            tx_hz=None if status is None else status.tx_df,
            slots=slots,
        )
