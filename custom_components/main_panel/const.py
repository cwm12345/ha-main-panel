# Written by Claude, guided by Chris.
"""Constants for the Main Panel integration.

Unlike a typical integration, this one talks to no external device at all -- the real data already comes from the native
`shelly` integration (Shelly Pro 3EM, a real config_entry with its own
device). The gap this fills: core HA's `template:` platform can't declare
a `device:` block, so the existing hand-written "Main Panel X" template sensors in
templates.yaml sit outside any device, ungrouped, duplicating the raw
Shelly entities with corrected units/names. This integration re-publishes
those same corrected values as entities owned by a real device, using
HA's state-change-tracking helpers to react to the underlying Shelly
entities rather than polling anything -- there's nothing to poll, the
source data is already live in HA's own state machine.

The formulas match the "Main Panel *" template sensors this replaced.
"""
from __future__ import annotations

DOMAIN = "main_panel"

MANUFACTURER = "Shelly (re-published)"
MODEL = "Main Panel Metering (Shelly Pro 3EM)"

# Fixed unique_id for the single config entry -- there is only one main
# panel, no host/credentials to ask for, so the config flow just confirms
# the source entities exist rather than collecting any input.
UNIQUE_ID = "main_panel"

# Source entity_ids: the Shelly Pro 3EM's own per-phase entities, renamed in
# HA to sensor.main_panel_meter_*. Point these at your own meter's entities.
#
# Raw per-phase real power, straight from the Shelly. The CT clamps on this
# meter read low by a fixed ratio, so the power sensors multiply by
# CT_CLAMP_CORRECTION_FACTOR. Set it to 1 if your clamps are configured
# correctly (or work out your own ratio against a known load).
SRC_L1_POWER_RAW = "sensor.main_panel_meter_l1_power"
SRC_L2_POWER_RAW = "sensor.main_panel_meter_l2_power"
CT_CLAMP_CORRECTION_FACTOR = 12
SRC_L1_APPARENT_POWER = "sensor.main_panel_meter_l1_apparent_power"
SRC_L2_APPARENT_POWER = "sensor.main_panel_meter_l2_apparent_power"
SRC_L1_POWER_FACTOR = "sensor.main_panel_meter_l1_power_factor"
SRC_L2_POWER_FACTOR = "sensor.main_panel_meter_l2_power_factor"
SRC_TEMPERATURE = "sensor.main_panel_meter_temperature"

# The Shelly's own hardware energy counters (disabled by default in the
# shelly integration; enable them). Total energy sums these rather than
# integrating power over time, so there's no estimation error. They're also
# exposed per phase.
SRC_L1_ENERGY = "sensor.main_panel_meter_l1_energy"
SRC_L2_ENERGY = "sensor.main_panel_meter_l2_energy"

# All source entities that must exist for the config flow to succeed.
ALL_SOURCES = [
    SRC_L1_POWER_RAW,
    SRC_L2_POWER_RAW,
    SRC_L1_APPARENT_POWER,
    SRC_L2_APPARENT_POWER,
    SRC_L1_POWER_FACTOR,
    SRC_L2_POWER_FACTOR,
    SRC_TEMPERATURE,
    SRC_L1_ENERGY,
    SRC_L2_ENERGY,
]
