"""Tests for the Lewisham Council sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lewisham_council.const import CONF_ADDRESS, CONF_UPRN, DOMAIN

from .conftest import MOCK_ADDRESS, MOCK_SCHEDULE, MOCK_UPRN


@pytest.fixture
async def loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a Lewisham Council config entry backed by MOCK_SCHEDULE."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_UPRN: MOCK_UPRN, CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_UPRN,
    )
    entry.add_to_hass(hass)

    mock_service = AsyncMock()
    mock_service.get_collection_schedule.return_value = MOCK_SCHEDULE

    with (
        patch(
            "custom_components.lewisham_council.get_async_client",
            return_value=MagicMock(),
        ),
        patch("custom_components.lewisham_council.LewishamClient"),
        patch(
            "custom_components.lewisham_council.LewishamService",
            return_value=mock_service,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _entity_id(hass: HomeAssistant, slug: str) -> str | None:
    """Look up the entity id for a sensor unique_id slug."""
    ent_reg = er.async_get(hass)
    return ent_reg.async_get_entity_id("sensor", DOMAIN, f"{MOCK_UPRN}_{slug}")


async def test_one_sensor_per_waste_stream(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """One sensor entity is created per CollectionEntry in the schedule."""
    for slug in ("food_waste", "recycling", "refuse"):
        assert _entity_id(hass, slug) is not None, f"Missing sensor for slug '{slug}'"


async def test_food_waste_native_value_is_next_collection(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The Food Waste sensor state is the ISO-formatted next collection date."""
    state = hass.states.get(_entity_id(hass, "food_waste"))
    assert state is not None
    assert state.state == "2026-07-07"


async def test_refuse_with_no_date_is_unknown(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A stream with next_collection=None reports an unknown state."""
    state = hass.states.get(_entity_id(hass, "refuse"))
    assert state is not None
    assert state.state == "unknown"


async def test_sensor_attributes_are_populated(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Sensor attributes include frequency, day, basis, source_url, and fetched_at."""
    state = hass.states.get(_entity_id(hass, "food_waste"))
    assert state is not None
    attrs = state.attributes
    assert attrs["frequency"] == "WEEKLY"
    assert attrs["day"] == "Monday"
    assert attrs["next_collection_basis"] == "published"
    assert "source_url" in attrs
    assert "fetched_at" in attrs


async def test_sensor_device_class_is_date(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Sensors are registered with the DATE device class."""
    state = hass.states.get(_entity_id(hass, "food_waste"))
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.DATE
