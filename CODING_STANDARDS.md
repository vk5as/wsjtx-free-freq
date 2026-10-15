# Coding standards

Rules for review. Anything a tool can check is enforced by `scripts/check.py` and pre-commit, so these are the judgement calls.

## Domain

- Names, tests and UI text use `GLOSSARY.md` terms (audio offset, slot, occupancy, free location, clearance, gap and the rest), not the synonyms it lists under _Avoid_.
- Nothing sets the Tx audio offset (ADR 0001). Set Rx only ever sends Configure with Rx DF.

## Engine

- State stays bounded over a session that runs for days. Anything kept per decode, per cycle or per instance needs a rule that prunes it.
- Time is counted on the instance's own timeline (cycles unwrapped across UTC midnight). A slot the operator transmits in, and so never decodes, still ages.
- A snapshot only claims what the engine can vouch for. In an unsupported mode, or with no Status yet, it shows no free locations rather than FT8-shaped guesses.

## GUI

- Offer only the actions that would work: no Set Rx, button or band map click, for an instance that is unsupported or disconnected.
- Report a failure to the operator where they are looking: the header's connection state for network problems, and the dialog for invalid settings. A failure is never silent.
- One user action applies everything it can. If one part fails, apply the rest and say which part was kept back.
- Signal handlers coalesce bursts: one refresh per batch of datagrams, not one per datagram.
