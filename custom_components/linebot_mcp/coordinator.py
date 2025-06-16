"""LINE Bot 數據更新協調器."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_WEBHOOK_PATH,
    LINE_API_CLIENT,
)
from .line_api_client import LineApiClient, LineApiError

_LOGGER = logging.getLogger(__name__)


class BaseBotCoordinator(DataUpdateCoordinator):
    """LINE Bot 基礎協調器."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        name_suffix: str,
        update_interval: timedelta,
    ) -> None:
        """初始化協調器."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.data[CONF_NAME]}_{name_suffix}",
            update_interval=update_interval,
        )
        self.hass = hass
        self.config_entry = config_entry
    
    @property
    def config_data(self) -> dict[str, Any]:
        """取得配置資料."""
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    @property
    def line_api_client(self) -> LineApiClient:
        """取得 LINE API 客戶端."""
        return self.config_data[LINE_API_CLIENT]

    @property
    def is_available(self) -> bool:
        """檢查協調器是否可用"""
        return self.last_update_success and self.data is not None

    @property
    def has_data(self) -> bool:
        """檢查是否有數據"""
        return self.data is not None

    def _handle_api_error(self, err: Exception) -> None:
        """處理 API 錯誤."""
        if isinstance(err, LineApiError):
            if err.status_code == 401:
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        raise UpdateFailed(f"{err}") from err


class LineBotInfoCoordinator(BaseBotCoordinator):
    """LINE Bot 資訊更新協調器."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """初始化協調器."""
        super().__init__(
            hass,
            config_entry,
            "Bot Info",
            timedelta(minutes=10),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """從 LINE API 獲取 Bot 資訊."""
        try:
            response = await self.line_api_client.get_bot_info()
            bot_info = response.data

            return {
                "user_id": bot_info.get("userId"),
                "basic_id": bot_info.get("basicId"),
                "premium_id": bot_info.get("premiumId"),
                "display_name": bot_info.get("displayName"),
                "picture_url": bot_info.get("pictureUrl"),
                "chat_mode": bot_info.get("chatMode"),
                "mark_as_read_mode": bot_info.get("markAsReadMode"),
                "webhook_endpoint": self.config_data.get(CONF_WEBHOOK_PATH),
            }

        except Exception as err:
            self._handle_api_error(err)


class LineBotQuotaCoordinator(BaseBotCoordinator):
    """LINE Bot 配額更新協調器."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """初始化協調器."""
        super().__init__(
            hass,
            config_entry,
            "Message Quota",
            timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """從 LINE API 獲取訊息配額資訊."""
        try:
            quota_task = self.line_api_client.get_message_quota()
            consumption_task = self.line_api_client.get_message_quota_consumption()

            quota_response, consumption_response = await asyncio.gather(
                quota_task, consumption_task
            )

            quota_info = quota_response.data
            consumption_info = consumption_response.data

            return {
                "type": quota_info.get("type"),
                "value": quota_info.get("value"),
                "total_usage": consumption_info.get("totalUsage"),
            }

        except Exception as err:
            self._handle_api_error(err)