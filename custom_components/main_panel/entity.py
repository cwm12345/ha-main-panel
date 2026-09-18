# Written by Claude, guided by Chris.
"""Shared entity base for the Main Panel integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, MANUFACTURER, MODEL


class MainPanelEntity(Entity):
    """Base class -- every entity shares the same device_info."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Main Panel",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
