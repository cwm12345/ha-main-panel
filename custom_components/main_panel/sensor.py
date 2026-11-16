# Written by Claude, guided by Chris.
"""Sensor platform for the Main Panel integration.

Event-driven, not polled: each sensor tracks one or more existing Shelly
Pro 3EM entities via async_track_state_change_event and recomputes its own
value whenever a source entity updates. There is nothing to poll -- the
source data is already live in HA's own state machine, published by the
native `shelly` integration. The formulas match the "Main Panel *" template
sensors this replaced.
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

from .const import (
    CT_CLAMP_CORRECTION_FACTOR,
    SRC_L1_APPARENT_POWER,
    SRC_L1_ENERGY,
    SRC_L1_POWER_FACTOR,
    SRC_L1_POWER_RAW,
    SRC_L2_APPARENT_POWER,
    SRC_L2_ENERGY,
    SRC_L2_POWER_FACTOR,
    SRC_L2_POWER_RAW,
    SRC_TEMPERATURE,
)
from .entity import MainPanelEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            TotalPowerSensor(entry),
            PhaseAPowerSensor(entry),
            PhaseBPowerSensor(entry),
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
            _PassthroughSensor(
                entry, "phase_a_energy", SRC_L1_ENERGY,
                SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            _PassthroughSensor(
                entry, "phase_b_energy", SRC_L2_ENERGY,
                SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR,
                state_class=SensorStateClass.TOTAL_INCREASING,
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
        # @callback marks this as safe to run on the event loop. Without it,
        # HA may call it from a worker thread, and async_write_ha_state()
        # then trips HA's thread-safety check.
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
        state_class: SensorStateClass = SensorStateClass.MEASUREMENT,
    ) -> None:
        super().__init__(entry, key, [source])
        self._source = source
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        # Override the base class's MEASUREMENT default -- required for
        # cumulative sources like the phase energy counters, which need
        # TOTAL_INCREASING so long-term statistics sum instead of average.
        self._attr_state_class = state_class

    def _compute(self) -> float:
        return _float_state(self.hass, self._source)


class _CorrectedPowerSensor(_ComputedSensor):
    """Applies CT_CLAMP_CORRECTION_FACTOR (see const.py) to one or both raw
    Shelly phase power readings."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT


class TotalPowerSensor(_CorrectedPowerSensor):
    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "total_power", [SRC_L1_POWER_RAW, SRC_L2_POWER_RAW])

    def _compute(self) -> float:
        raw = _float_state(self.hass, SRC_L1_POWER_RAW) + _float_state(self.hass, SRC_L2_POWER_RAW)
        return raw * CT_CLAMP_CORRECTION_FACTOR


class PhaseAPowerSensor(_CorrectedPowerSensor):
    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "phase_a_power", [SRC_L1_POWER_RAW])

    def _compute(self) -> float:
        return _float_state(self.hass, SRC_L1_POWER_RAW) * CT_CLAMP_CORRECTION_FACTOR


class PhaseBPowerSensor(_CorrectedPowerSensor):
    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "phase_b_power", [SRC_L2_POWER_RAW])

    def _compute(self) -> float:
        return _float_state(self.hass, SRC_L2_POWER_RAW) * CT_CLAMP_CORRECTION_FACTOR


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
    using real-power values as weights, or 0 if both phases read zero
    power. Uses raw (uncorrected) power as the weight, not the ×12
    CT-clamp-corrected value: multiplying both weights by the same
    constant factor doesn't change a weighted-average ratio, so the raw
    values give the identical result without the dependency.
    """

    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = None

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(
            entry,
            "total_power_factor",
            [
                SRC_L1_POWER_RAW,
                SRC_L2_POWER_RAW,
                SRC_L1_POWER_FACTOR,
                SRC_L2_POWER_FACTOR,
            ],
        )

    def _compute(self) -> float:
        l1_w = _float_state(self.hass, SRC_L1_POWER_RAW)
        l2_w = _float_state(self.hass, SRC_L2_POWER_RAW)
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
    """Sum of the Shelly meter's own per-phase energy counters (L1 + L2),
    plus an offset fixed at startup so the total continues from its last
    value.

    Earlier versions integrated total power over time (a Riemann-sum
    estimate). The meter's hardware counters are more accurate, so this
    sums them instead. RestoreEntity supplies the last total at startup;
    the offset is the difference between it and the current counter sum,
    so switching methods, or a restart, neither adds nor loses energy.
    Nothing is estimated for downtime.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_translation_key = "total_energy"
        self._attr_unique_id = f"{entry.entry_id}_total_energy"
        self._offset_kwh = 0.0

    def _phase_sum_kwh(self) -> float:
        return _float_state(self.hass, SRC_L1_ENERGY) + _float_state(self.hass, SRC_L2_ENERGY)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        prior_total = _INITIAL_SEED_KWH
        if last_state is not None:
            try:
                prior_total = float(last_state.state)
            except (TypeError, ValueError):
                prior_total = _INITIAL_SEED_KWH
        self._offset_kwh = prior_total - self._phase_sum_kwh()
        self._attr_native_value = prior_total
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [SRC_L1_ENERGY, SRC_L2_ENERGY], self._handle_source_change
            )
        )

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        self._attr_native_value = self._phase_sum_kwh() + self._offset_kwh
        self.async_write_ha_state()
