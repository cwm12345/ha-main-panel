# Main Panel for Home Assistant

A `config_entry`-owned Home Assistant custom integration that re-publishes
corrected/renamed readings from a Shelly Pro 3EM main-panel energy meter
as entities owned by a real HA device — no polling, no external protocol,
no credentials. It exists to solve one specific gap: core HA's
`template:` platform can't declare a `device:` block, so hand-written
template sensors that wrap a Shelly device's raw entities end up sitting
ungrouped, outside any device card, duplicating the raw entities they're
correcting.

## Status

This is a working reference implementation, pulled from my own running
Home Assistant deployment and published as-is. **I am not maintaining
this as an ongoing package** — no commitment to triage issues, accept
PRs, or track future Home Assistant API changes. It's also the most
deployment-specific of the integrations I'm publishing (see "Adapting
this to your setup" below) — treat it as a pattern to copy more than a
drop-in install. If it's useful, great; if you hit something that doesn't
work for you, you're welcome to open an issue, but I can't promise a
response.

If you're a more serious maintainer, this one's less likely core material
than the sibling repos — it's a deployment-specific wrapper, not a
third-party-hardware integration — but the "wrap ungrouped template
sensors in a real device" pattern might still be worth lifting. Public
domain (Unlicense), take whatever's useful.

## Why this exists

If your main-panel metering already comes from a real, already-integrated
device (a Shelly Pro 3EM in my case, native `shelly` integration, its own
config entry, its own device), and you've built `template:` sensors to
correct units/names/formulas on top of it, those corrected sensors have
no way to join the underlying device's device card — HA's `template:`
platform has no `device:` option. This integration re-publishes the same
corrected values as entities owned by a real "Main Panel" device,
reacting to the underlying source entities via
`async_track_state_change_event` rather than polling anything (there's
nothing to poll — the source data is already live in HA's own state
machine).

## What it does

One config entry (there's only one main panel), one device, 13 sensors:
total/phase-A/phase-B power (W), phase-A/phase-B/total apparent power
(VA), phase-A/phase-B/total power factor (unitless 0–1), temperature
(°F), phase-A/phase-B energy (kWh), and total energy (kWh,
`total_increasing`).

- **Power** is the Shelly's raw per-phase reading times
  `CT_CLAMP_CORRECTION_FACTOR` (12 here: this meter's CT clamps read low by a
  fixed ratio). Use 1 if yours are set up correctly.
- **Energy** comes from the Shelly's own hardware energy counters, which the
  `shelly` integration disables by default; enable them. Total energy sums
  the two phases, and uses `RestoreEntity` so the running total carries
  across restarts. (Earlier versions estimated energy by integrating power
  over time; the hardware counters are more accurate.)

Formulas and source entity_ids are in `const.py`.

## Adapting this to your setup

**This integration is not plug-and-play** — `const.py` hardcodes the
source `entity_id`s it reads from (`sensor.main_panel_meter_l1_power`,
etc.), matching my own Shelly Pro 3EM entity naming. To use this, you'll
need to edit `const.py`'s `SRC_*` constants to point at your own
equivalent source entities, set `CT_CLAMP_CORRECTION_FACTOR` (1 if your
clamps read correctly), enable the Shelly's energy entities, and adjust
the formulas in `sensor.py` if your source data shapes differently. It's published as a working pattern
for "wrap ungrouped template-style sensors in a real device," not as a
generic main-panel integration for arbitrary hardware.

## Installation

**With HACS:**

1. In Home Assistant, open **HACS**, then the **⋮** menu (top right) →
   **Custom repositories**.
2. Repository: `https://github.com/cwm12345/ha-main-panel`, type:
   **Integration**. Click **Add**.
3. Search HACS for **Main Panel**, open it and click **Download**.
4. Restart Home Assistant.

**Manual:** copy `custom_components/main_panel/` into your HA config's
`custom_components/` directory → restart HA.

Then edit `const.py`'s source entity_ids for your own setup (see above)
before adding the integration via Settings → Devices & Services → Add
Integration → "Main Panel". The config flow just confirms the source
entities exist — there's no host/credentials to enter.

## Files

- `const.py` — the source entity_ids and formulas. Read and adapt this
  first.
- `manifest.json`, `config_flow.py`, `__init__.py`, `entity.py` —
  integration scaffolding. No `coordinator.py` — nothing to poll.
- `sensor.py` — the entities themselves, event-driven via
  `async_track_state_change_event`.
- `strings.json` / `translations/en.json` — config flow + entity text.

## What's not handled

If the source entities are ever renamed or removed (e.g. the underlying
integration is reconfigured), these sensors go unavailable silently
(`hass.states.get()` returns `None`, treated as `0.0`) rather than
raising a visible error. There's no "source entity missing" diagnostic.

## Validation

All files pass `py_compile` / JSON validation, every module imports
cleanly against a real installed `homeassistant` package, and the config
flow self-registers correctly. No mock-backend functional test — there's
no protocol client to mock, just arithmetic on `hass.states`. Deployed
and running against real hardware since September 2026.
