"""LINE Bot sensor platform."""
from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_SERVICE_NAME,
    CONF_SECRET,
    LINEBOT_INFO_COORDINATOR,
    LINEBOT_QUOTA_COORDINATOR,
    EVENT_MESSAGE_RECEIVED,
    ATTR_USER_ID,
    ATTR_GROUP_ID,
    ATTR_ROOM_ID,
    ATTR_MESSAGE_ID,
    ATTR_MESSAGE_TYPE,
    ATTR_REPLY_TOKEN,
    ATTR_TIMESTAMP,
    ATTR_SOURCE_TYPE,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """設定 LINE Bot 感測器."""
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    
    sensors = [
        LineBotMessageSensor(hass, config_data),
        LineBotInfoSensor(config_data, config_data[LINEBOT_INFO_COORDINATOR]),
        LineBotQuotaSensor(config_data, config_data[LINEBOT_QUOTA_COORDINATOR]),
    ]

    async_add_entities(sensors)


class LineBotBaseSensor(SensorEntity):
    """LINE Bot 基礎感測器."""

    def __init__(self, config_data: dict[str, Any], name_suffix: str, unique_id: str) -> None:
        """初始化感測器."""
        self.config_data = config_data
        self._attr_name = f"LINEBot {config_data[CONF_NAME]} {name_suffix}"
        self._attr_unique_id = f"{DOMAIN}_{config_data[CONF_SERVICE_NAME]}_{unique_id}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
    @property
    def has_entity_name(self):
        return False

    @property
    def device_info(self) -> dict[str, Any]:
        """回傳裝置資訊."""
        return {
            "identifiers": {(DOMAIN, self.config_data[CONF_SECRET])},
            "name": self.config_data[CONF_NAME],
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }


class LineBotInfoSensor(CoordinatorEntity, LineBotBaseSensor):
    """LINE Bot 資訊感測器."""

    def __init__(self, config_data: dict[str, Any], coordinator) -> None:
        """初始化 Bot 資訊感測器."""
        CoordinatorEntity.__init__(self, coordinator)
        LineBotBaseSensor.__init__(self, config_data, "Bot Info", "bot_info")
        self._attr_icon = "mdi:robot-outline"

    @property
    def available(self) -> bool:
        return True if self.coordinator.data else False

    @property
    def native_value(self) -> str:
        """回傳感測器狀態."""
        return "connected" if self.coordinator.data else "error"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """回傳額外屬性."""
        if not self.coordinator.data:
            return {
                "error": "Bot info unavailable",
            }

        # 過濾 None 值
        attrs = {k: v for k, v in self.coordinator.data.items() if v is not None}
        
        return attrs


class LineBotQuotaSensor(CoordinatorEntity, LineBotBaseSensor):
    """LINE Bot 配額感測器."""

    def __init__(self, config_data: dict[str, Any], quota_coordinator) -> None:
        """初始化配額感測器."""
        CoordinatorEntity.__init__(self, quota_coordinator)
        LineBotBaseSensor.__init__(self, config_data, "Message Quota", "message_quota")
        self._attr_icon = "mdi:message-text-outline"

    @property
    def available(self) -> bool:
        return True if self.coordinator.data else False

    @property
    def native_value(self) -> int | None:
        """回傳感測器狀態（剩餘配額）."""
        quota_data = self.coordinator.data
        if not quota_data:
            return None
        return quota_data.get("type")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """回傳額外屬性."""
        attrs = {}
        quota_data = self.coordinator.data
        if not quota_data:
            return attrs

        attrs.update({
            "total_quota": (
                quota_data.get("value")
                if quota_data.get("type") == "limited"
                else "unlimited"
            ),
            "used_quota": quota_data.get("total_usage", 0),
        })

        return attrs


class LineBotMessageSensor(LineBotBaseSensor):
    """LINE Bot 訊息感測器."""

    def __init__(self, hass: HomeAssistant, config_data: dict[str, Any]) -> None:
        """初始化感測器."""
        super().__init__(config_data, "Message Event", "message_event")
        self.hass = hass
        self._attr_icon = "mdi:message-text"
        self._attr_should_poll = False
        
        self._state = "unknown"
        self._attributes: dict[str, Any] = {}
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        """當感測器被加入 Home Assistant 時."""
        @callback
        def handle_message_event(event) -> None:
            """處理訊息事件."""
            event_data = event.data
            message_type = event_data.get(ATTR_MESSAGE_TYPE)
            self._state = message_type or "unknown"
            
            self._attributes = {
                ATTR_SOURCE_TYPE: event_data.get(ATTR_SOURCE_TYPE),
                ATTR_USER_ID: event_data.get(ATTR_USER_ID),
                ATTR_GROUP_ID: event_data.get(ATTR_GROUP_ID),
                ATTR_ROOM_ID: event_data.get(ATTR_ROOM_ID),
                ATTR_REPLY_TOKEN: event_data.get(ATTR_REPLY_TOKEN),
                ATTR_MESSAGE_TYPE: message_type,
                ATTR_MESSAGE_ID: event_data.get(ATTR_MESSAGE_ID),
                ATTR_TIMESTAMP: event_data.get(ATTR_TIMESTAMP),       
            }
            
            self.async_write_ha_state()
        
        # 註冊事件監聽器
        self._remove_listener = self.hass.bus.async_listen(
            EVENT_MESSAGE_RECEIVED.format(self.config_data[CONF_NAME]), 
            handle_message_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """當感測器即將從 Home Assistant 移除時."""
        if self._remove_listener:
            self._remove_listener()

    @property
    def native_value(self) -> str:
        """回傳感測器狀態."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """回傳額外屬性."""
        return self._attributes
