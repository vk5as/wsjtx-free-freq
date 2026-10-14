# Setting a free location moves Rx only

The WSJT-X UDP protocol has no inbound message that sets the Tx audio offset; `Configure` (type 15) can only set Rx DF. So "Set" sends `Configure` with the chosen Rx DF and the UI tells the operator to press "Tx ← Rx" (or untick "Hold Tx Freq") in WSJT-X. We deliberately do not fake keystrokes or mouse clicks into WSJT-X to move Tx: it is fragile, platform-specific, and could key the transmitter unexpectedly.
