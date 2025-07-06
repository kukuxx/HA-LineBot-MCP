"""The LINE Bot MCP integration."""
from __future__ import annotations

import logging
import asyncio
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry

from .mcp_core import http, MCPServerManager, SessionManager
from .services import LineBotServiceManager
from .line_api_client import LineApiClient
from .webhook import LineBotWebhookView
from .coordinator import (
    LineBotInfoCoordinator,
    LineBotQuotaCoordinator,
)
from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_SERVICE_NAME,
    CONF_TOKEN,
    CONF_SECRET,
    CONF_WEBHOOK_PATH,
    CONF_AGENT_ID,
    CONF_AUTO_REPLY,
    SERVICE_MANAGER,
    SESSION_MANAGER,
    SERVER_MANAGER,
    SHUTDOWN_EVENT,
    STOP_LISTENER,
    LINEBOT_INFO_COORDINATOR,
    LINEBOT_QUOTA_COORDINATOR,
    LINE_API_CLIENT,
)


_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """設置 LINE Bot MCP 組件"""
    @callback
    async def handle_shutdown(event):
        """處理終止事件"""
        _LOGGER.debug("Received shutdown event")
        session = hass.data[DOMAIN][SESSION_MANAGER]
        shutdown_event = hass.data[DOMAIN][SHUTDOWN_EVENT]
        shutdown_event.set()
        await asyncio.sleep(1)
        session.close()

    cancel = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_shutdown)
    hass.data.setdefault(DOMAIN, {})
    
    # 設定全域 LINE Bot 服務
    service_manager = LineBotServiceManager(hass)
    await service_manager.setup_services()

    hass.data[DOMAIN].update({
        SERVICE_MANAGER: service_manager,
        SESSION_MANAGER: SessionManager(),
        SERVER_MANAGER: MCPServerManager(hass),
        STOP_LISTENER: cancel,
        SHUTDOWN_EVENT: asyncio.Event(),
    })
    # 設定 MCP HTTP API
    http.async_register(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """設置 LINE Bot MCP 配置項目"""
    config_data = {
        CONF_TOKEN: entry.data[CONF_TOKEN],
        CONF_SECRET: entry.data[CONF_SECRET],
        CONF_WEBHOOK_PATH: entry.data[CONF_WEBHOOK_PATH],
        CONF_NAME: entry.data[CONF_NAME],
        CONF_SERVICE_NAME: entry.data[CONF_SERVICE_NAME],
        CONF_AGENT_ID: entry.options.get(CONF_AGENT_ID),
        CONF_AUTO_REPLY: entry.options.get(CONF_AUTO_REPLY),
    }

    # 建立 LINE API 客戶端
    config_data[LINE_API_CLIENT] = LineApiClient(hass, config_data[CONF_TOKEN])
    hass.data[DOMAIN][entry.entry_id] = config_data

    # 設定 webhook
    await _setup_webhook(hass, config_data, entry.entry_id)
    
    # 初始化協調器
    info_coordinator = LineBotInfoCoordinator(hass, entry)
    quota_coordinator = LineBotQuotaCoordinator(hass, entry)
    await info_coordinator.async_config_entry_first_refresh()
    await quota_coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id].update({
        LINEBOT_INFO_COORDINATOR: info_coordinator,
        LINEBOT_QUOTA_COORDINATOR: quota_coordinator,
    })

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """更新監聽器"""
    try:
        await hass.config_entries.async_reload(entry.entry_id)
    except Exception as e:
        _LOGGER.error(f"Update listener error: {e}")


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """重新載入配置項目"""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸載配置項目"""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        if not hass.config_entries.async_entries(DOMAIN):
            await hass.data[DOMAIN][SERVICE_MANAGER].remove_services()
            _LOGGER.debug("clearing task start")
            hass.data[DOMAIN][STOP_LISTENER]()
            session = hass.data[DOMAIN][SESSION_MANAGER]
            shutdown_event = hass.data[DOMAIN][SHUTDOWN_EVENT]
            shutdown_event.set()
            await asyncio.sleep(1)
            session.close()
            hass.data.pop(DOMAIN)

    return unload_ok


async def _setup_webhook(
    hass: HomeAssistant, 
    config_data: dict[str, Any],
    entry_id: str,
    ) -> None:
    """設置 webhook"""
    webhook_path = config_data.get(CONF_WEBHOOK_PATH)
    if not webhook_path:
        raise ValueError("Webhook path is not configured")

    def create_webhook_view():
        webhook_class = type(
            f"LineBotWebhookView_{entry_id}",
            (LineBotWebhookView,),
            {
                "name": f"{DOMAIN}_{entry_id}_webhook",
                "url": webhook_path,
            }
        )
        
        return webhook_class(
            config_data[CONF_NAME],
            config_data[CONF_SECRET],
            entry_id,
        )

    view = create_webhook_view()
    hass.http.register_view(view)

    _LOGGER.info(f"LINE Bot webhook registered at {webhook_path}")
