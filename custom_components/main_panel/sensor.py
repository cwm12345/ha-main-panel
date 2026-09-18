# Written by Claude, guided by Chris.
"""Sensor platform for the Main Panel integration.

Event-driven, not polled: each sensor tracks one or more existing Shelly
Pro 3EM entities via async_track_state_change_event and recomputes its own
value whenever a source entity updates. There is nothing to poll -- the
source data is already live in HA's own state machine, published by the
native `shelly` integration. Formulas match templates.yaml's "Main Panel
*" sensors exactly (read directly from the live config), not guessed.
"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import (
    SRC_L1_APPARENT_POWER,
    SRC_L1_POWER_CORRECTED,
    SRC_L1_POWER_FACTOR,
    SRC_L2_APPARENT_POWER,
    SRC_L2_POWER_CORRECTED,
    SRC_L2_POWER_FACTOR,
    SRC_TEMPERATURE,
    SRC_TOTAL_POWER_CORRECTED,
)
from .entity import MainPanelEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            _PassthroughSensor(
                entry, "total_power", SRC_TOTAL_POWER_CORRECTED,
                SensorDeviceClass.POWER, UnitOfPower.WATT,
            ),
            _PassthroughSensor(
                entry, "phase_a_power", SRC_L1_POWER_CORRECTED,
                SensorDeviceClass.POWER, UnitOfPower.WATT,
            ),
            _PassthroughSensor(
                entry, "phase_b_power", SRC_L2_POWER_CORRECTED,
                SensorDeviceClass.POWER, UnitOfPower.WATT,
            ),
            _PassthroughSensor(
                entry, "phase_a_apparent_power", SRC_L1_APPARENT_POWER,
                SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE,
            ),
            _PassthroughSensor(
                entry, "phase_b_apparent_power", SRC_L2_APPARENT_POWER,
                SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE,
            ),
            _PassthroughSensor(
                entry, "phase_a_power_factor", SRC_L1_POWER_FACTOR,
                SensorDeviceClass.POWER_FACTOR, None,
            ),
            _PassthroughSensor(
                entry, "phase_b_power_factor", SRC_L2_POWER_FACTOR,
                SensorDeviceClass.POWER_FACTOR, None,
            ),
            _PassthroughSensor(
                entry, "temperature", SRC_TEMPERATURE,
                SensorDeviceClass.TEMPERATURE, UnitOfTemperature.FAHRENHEIT,
            ),
            TotalApparentPowerSensor(entry),
            TotalPowerFactorSensor(entry),
            TotalEnergySensor(entry),
        ]
    )


def _float_state(hass: HomeAssistant, entity_id: str) -> float:
    state = hass.states.get(entity_id)
    if state is None:
        return 0.0
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return 0.0


class _ComputedSensor(MainPanelEntity, SensorEntity):
    """Base for sensors that track one or more source entities and
    recompute their value via `_compute` whenever any of them change."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry: ConfigEntry, key: str, sources: list[str]
    ) -> None:
        super().__init__(entry)
        self._sources = sources
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._recompute()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sources, self._handle_source_change
            )
        )

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        # @callback tells HA this sync function is safe to run directly on
        # the event loop. Without it, HA's dispatcher may invoke it from a
        # worker thread instead -- confirmed live 2026-09-18: HA's own
        # thread-safety checker flagged async_write_ha_state() being called
        # off the event loop from this exact method, right after deploy.
        self._recompute()
        self.async_write_ha_state()

    def _recompute(self) -> None:
        self._attr_native_value = self._compute()

    def _compute(self) -> float:
        raise NotImplementedError


class _PassthroughSensor(_ComputedSensor):
    """Mirrors one source entity's numeric state, with corrected unit/device_class."""

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        source: str,
        device_class: SensorDeviceClass,
        unit: str,
    ) -> None:
        super().__init__(entry, key, [source])
        self._source = source
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

    def _compute(self) -> float:
        return _float_state(self.hass, self._source)


class TotalApparentPowerSensor(_ComputedSensor):
    """Sum of both phases' apparent power."""

    _attr_device_class = SensorDeviceClass.APPARENT_POWER
    _attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(
            entry,
            "total_apparent_power",
            [SRC_L1_APPARENT_POWER, SRC_L2_APPARENT_POWER],
        )

    def _compute(self) -> float:
        return _float_state(self.hass, SRC_L1_APPARENT_POWER) + _float_state(
            self.hass, SRC_L2_APPARENT_POWER
        )


class TotalPowerFactorSensor(_ComputedSensor):
    """Power-weighted average of both phases' power factor.

    Matches templates.yaml exactly: (l1_w*l1_pf + l2_w*l2_pf) / (l1_w+l2_w),
    using the *corrected* real-power values (not apparent power) as weights,
    or 0 if both phases read zero power.
    """

    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = None

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(
            entry,
            "total_power_factor",
            [
                SRC_L1_POWER_CORRECTED,
                SRC_L2_POWER_CORRECTED,
                SRC_L1_POWER_FACTOR,
                SRC_L2_POWER_FACTOR,
            ],
        )

    def _compute(self) -> float:
        l1_w = _float_state(self.hass, SRC_L1_POWER_CORRECTED)
        l2_w = _float_state(self.hass, SRC_L2_POWER_CORRECTED)
        l1_pf = _float_state(self.hass, SRC_L1_POWER_FACTOR)
        l2_pf = _float_state(self.hass, SRC_L2_POWER_FACTOR)
        total_w = l1_w + l2_w
        if total_w <= 0:
            return 0.0
        return (l1_w * l1_pf + l2_w * l2_pf) / total_w


# Seed value for a brand-new install of this entity only -- 0.0 by default.
# If you're migrating from an existing `platform: integration` YAML energy
# sensor and want the running total to carry over instead of restarting at
# zero, set this to that sensor's last known state before first setup.
# Every restart after the first uses RestoreEntity's own last-state
# instead of this constant.
_INITIAL_SEED_KWH = 0.0


class TotalEnergySensor(MainPanelEntity, SensorEntity, RestoreEntity):
    """Trapezoidal (Riemann-sum) integration of total_power over time,
    in kWh -- moved 2026-09-19 from a standalone `platform: integration`
    YAML sensor (which couldn't attach to a device, same core-platform
    limitation as templates.yaml) into a real device-owned entity here.
    Reimplements the same method HA's built-in `integration:` platform
    uses (average of consecutive readings * elapsed time), since that
    platform isn't designed to be instantiated by another integration.

    RestoreEntity persists the running total across restarts -- without
    it, every HA restart would silently zero out the house's cumulative
    energy total, corrupting the Energy Dashboard's long-term numbers.
    No energy is estimated for the downtime itself (same behavior as
    HA's own built-in sensor): the first update after a restart just
    establishes a new (power, time) baseline without adding an increment.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_translation_key = "total_energy"
        self._attr_unique_id = f"{entry.entry_id}_total_energy"
        self._total_kwh = 0.0
        self._last_power_w: float | None = None
        self._last_time = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._total_kwh = float(last_state.state)
            except (TypeError, ValueError):
                self._total_kwh = _INITIAL_SEED_KWH
        else:
            self._total_kwh = _INITIAL_SEED_KWH
        self._attr_native_value = self._total_kwh
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [SRC_TOTAL_POWER_CORRECTED], self._handle_power_change
            )
        )

    @callback
    def _handle_power_change(self, event: Event[EventStateChangedData]) -> None:
        now = dt_util.utcnow()
        power_w = _float_state(self.hass, SRC_TOTAL_POWER_CORRECTED)

        if self._last_power_w is not None and self._last_time is not None:
            dt_hours = (now - self._last_time).total_seconds() / 3600
            avg_power_w = (self._last_power_w + power_w) / 2
            self._total_kwh += (avg_power_w * dt_hours) / 1000
            self._attr_native_value = self._total_kwh
            self.async_write_ha_state()

        self._last_power_w = power_w
        self._last_time = now
