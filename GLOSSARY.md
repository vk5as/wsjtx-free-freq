# WSJT-X Free Frequency

Listens to WSJT-X decodes and recommends audio offsets that nobody else is transmitting on, separately for each slot.

## Language

**Audio offset**:
The position of a signal within the receiver passband, in Hz above the dial frequency (WSJT-X's Rx DF / Tx DF).
_Avoid_: Frequency, DF, tone

**Dial frequency**:
The radio's tuned frequency; changing it invalidates all occupancy.
_Avoid_: Band, VFO

**Decode**:
A single message WSJT-X decoded from a station, with its time, audio offset, SNR and mode.
_Avoid_: Spot, message

**Cycle**:
One T/R period of the current mode (15 s for FT8, 7.5 s for FT4).
_Avoid_: Period, interval, sequence

**Slot**:
Which alternating set of cycles a transmission falls in: **1st** (even, WSJT-X "Tx even/1st") or **2nd** (odd).
_Avoid_: Even/odd period, parity, sequence

**Occupancy**:
The audio offsets taken up by decoded stations in a given slot within the occupancy window.
_Avoid_: Activity, usage

**Occupancy window**:
The most recent N cycles of a slot whose decodes count toward occupancy, with older cycles counting less.
_Avoid_: History, lookback

**Signal width**:
The bandwidth a signal of a given mode occupies above its audio offset (about 50 Hz for FT8, 83 Hz for FT4).
_Avoid_: Bandwidth, span

**Guard band**:
Extra spacing kept clear on each side of an occupied signal; strong signals may get a wider guard band.
_Avoid_: Margin, buffer, padding

**Strong signal**:
A decode whose SNR is at or above the configured threshold, and so gets the extra guard band.
_Avoid_: Loud station, big signal

**Clearance**:
How far a free location is from the nearest occupancy in its slot, used to rank free locations.
_Avoid_: Distance, gap size, score

**Free location**:
An audio offset where a signal of the current mode fits without overlapping occupancy in that slot.
_Avoid_: Gap, hole, clear spot, free frequency
