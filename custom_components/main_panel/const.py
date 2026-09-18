# Written by Claude, guided by Chris.
"""Constants for the Main Panel integration.

Unlike every other integration built this session, this one talks to no
external device at all -- the real data already comes from the native
`shelly` integration (Shelly Pro 3EM, a real config_entry with its own
device). The gap this fills: core HA's `template:` platform can't declare
a `device:` block (confirmed earlier this session -- no such option
exists), so the existing hand-written "Main Panel X" template sensors in
templates.yaml sit outside any device, ungrouped, duplicating the raw
Shelly entities with corrected units/names. This integration re-publishes
those same corrected values as entities owned by a real device, using
HA's state-change-tracking helpers to react to the underlying Shelly
entities rather than polling anything -- there's nothing to poll, the
source data is already live in HA's own state machine.

Source entity_ids and formulas match templates.yaml's "Main Panel *"
sensors exactly (read directly from the live config 2026-09-18), not
guessed.
"""
from __future__ import annotations

DOMAIN = "main_panel"

MANUFACTURER = "Shelly (re-published)"
MODEL = "Main Panel Metering (Shelly Pro 3EM)"

# Fixed unique_id for the single config entry -- there is only one main
# panel, no host/credentials to ask for, so the config flow just confirms
# the source entities exist rather than collecting any input.
UNIQUE_ID = "main_panel"

# Source entity_ids updated 2026-09-19 by Claude, guided by Chris -- the
# underlying Shelly Pro 3EM device's raw MAC-address-prefixed entity_ids
# were renamed to clean sensor.main_panel_meter_* names (same cleanup
# already done for the boiler/HP1/HP2/main_panel's own entities), so these
# constants were updated to match. See roadmap.md Goal 9.
SRC_L1_POWER_CORRECTED = "sensor.shelly_l1_power_corrected"
SRC_L2_POWER_CORRECTED = "sensor.shelly_l2_power_corrected"
SRC_TOTAL_POWER_CORRECTED = "sensor.shelly_total_power_corrected"
SRC_L1_APPARENT_POWER = "sensor.main_panel_meter_l1_apparent_power"
SRC_L2_APPARENT_POWER = "sensor.main_panel_meter_l2_apparent_power"
SRC_L1_POWER_FACTOR = "sensor.main_panel_meter_l1_power_factor"
SRC_L2_POWER_FACTOR = "sensor.main_panel_meter_l2_power_factor"
SRC_TEMPERATURE = "sensor.main_panel_meter_temperature"

# All source entities that must exist for the config flow to succeed.
ALL_SOURCES = [
    SRC_L1_POWER_CORRECTED,
    SRC_L2_POWER_CORRECTED,
    SRC_TOTAL_POWER_CORRECTED,
    SRC_L1_APPARENT_POWER,
    SRC_L2_APPARENT_POWER,
    SRC_L1_POWER_FACTOR,
    SRC_L2_POWER_FACTOR,
    SRC_TEMPERATURE,
]
