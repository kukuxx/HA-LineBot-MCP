"""LINE Bot services."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.service import async_set_service_schema

from .line_api_client import (
    create_text_message,
    create_text_v2_message,
    create_image_message,
    create_video_message,
    create_location_message,
    create_audio_message,
    create_sticker_message,
    create_flex_message,
    create_imagemap_message,
    handle_template_message,
)
from .const import (
    DOMAIN,
    CONF_NAME,
    ATTR_REPLY_TOKEN,
    LINE_API_CLIENT,
    SERVICE_NOTIFY,
    SERVICE_REPLY_MESSAGE,
    SERVICE_PUSH_MESSAGE,
    SERVICE_TEXT_CONTENT,
    SERVICE_TEXT_V2_CONTENT,
    SERVICE_IMAGE_CONTENT,
    SERVICE_VIDEO_CONTENT,
    SERVICE_AUDIO_CONTENT,
    SERVICE_LOCATION_CONTENT,
    SERVICE_STICKER_CONTENT,
    SERVICE_FLEX_CONTENT,
    SERVICE_IMAGEMAP_CONTENT,
    SERVICE_TEMPLATE_CONTENT,
    REPLY_MESSAGE_SCHEMA,
    PUSH_MESSAGE_SCHEMA,
    CREATE_TEXT_SCHEMA,
    CREATE_TEXT_V2_SCHEMA,
    CREATE_IMAGE_SCHEMA,
    CREATE_VIDEO_SCHEMA,
    CREATE_AUDIO_SCHEMA,
    CREATE_LOCATION_SCHEMA,
    CREATE_STICKER_SCHEMA,
    CREATE_FLEX_SCHEMA,
    CREATE_IMAGEMAP_SCHEMA,
    CREATE_TEMPLATE_SCHEMA,
    REPLY_MESSAGE_DESCRIBE,
    PUSH_MESSAGE_DESCRIBE,
)


_LOGGER = logging.getLogger(__name__)

# 訊息建立器映射
MESSAGE_CREATORS = {
    "text": lambda data: create_text_message(
        text=data["message"],
    ),
    "textV2": lambda data: create_text_v2_message(
        text=data["message"],
        mentions=data.get("mentions"),
        emojis=data.get("emojis")
    ),
    "image": lambda data: create_image_message(
        original_content_url=data["image_url"],
        preview_image_url=data.get("preview_image_url", data["image_url"])
    ),
    "video": lambda data: create_video_message(
        original_content_url=data["video_url"],
        preview_image_url=data.get("preview_image_url", data["video_url"])
    ),
    "audio": lambda data: create_audio_message(
        original_content_url=data["audio_url"],
        duration=data.get("duration", 1000)
    ),
    "location": lambda data: create_location_message(
        title=data.get("title"),
        address=data.get("address", ""),
        latitude=data["latitude"],
        longitude=data["longitude"]
    ),
    "sticker": lambda data: create_sticker_message(
        package_id=data["package_id"],
        sticker_id=data["sticker_id"],
    ),
    "flex": lambda data: create_flex_message(data),
    "imagemap": lambda data: create_imagemap_message(
        base_url=data["base_url"],
        alt_text=data.get("alt_text", "Imagemap"),
        base_size=data["base_size"],
        actions=data["imagemap_actions"],
        video=data.get("video")
    ),
    "template": lambda data: handle_template_message(data),
}


class LineBotServiceManager:
    """LINE Bot 服務管理器."""

    def __init__(self, hass: HomeAssistant):
        """初始化服務管理器."""
        self.hass = hass
        self._clients: Dict[str, Any] = {}

    @property
    def service_registry(self) :
        """服務註冊映射."""
        notify = [
            (SERVICE_NOTIFY,SERVICE_REPLY_MESSAGE,self.reply_message,REPLY_MESSAGE_SCHEMA,REPLY_MESSAGE_DESCRIBE),
            (SERVICE_NOTIFY,SERVICE_PUSH_MESSAGE,self.push_message,PUSH_MESSAGE_SCHEMA,PUSH_MESSAGE_DESCRIBE),
        ]
        content = [
            (DOMAIN,SERVICE_TEXT_CONTENT,self.create_text_content,CREATE_TEXT_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_TEXT_V2_CONTENT,self.create_text_v2_content,CREATE_TEXT_V2_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_IMAGE_CONTENT,self.create_image_content,CREATE_IMAGE_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_VIDEO_CONTENT,self.create_video_content,CREATE_VIDEO_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_AUDIO_CONTENT,self.create_audio_content,CREATE_AUDIO_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_LOCATION_CONTENT,self.create_location_content,CREATE_LOCATION_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_STICKER_CONTENT,self.create_sticker_content,CREATE_STICKER_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_FLEX_CONTENT,self.create_flex_content,CREATE_FLEX_SCHEMA,SupportsResponse.ONLY),
            (DOMAIN,SERVICE_IMAGEMAP_CONTENT,self.create_imagemap_content,CREATE_IMAGEMAP_SCHEMA,SupportsResponse.ONLY),
            (
                DOMAIN,
                SERVICE_TEMPLATE_CONTENT,
                self.create_template_content,
                CREATE_TEMPLATE_SCHEMA,
                SupportsResponse.ONLY
            ),
        ]
        return notify, content
    
    @property
    def get_bot_client(self) -> Dict[str, Any]:
        """取得所有 Bot 的 LINE API 客戶端."""
        domain_data = self.hass.data.get(DOMAIN, {})

        return {
            entry_data[CONF_NAME]: entry_data[LINE_API_CLIENT]
            for _, entry_data in domain_data.items()
            if (
                isinstance(entry_data, dict)
                and CONF_NAME in entry_data
                and LINE_API_CLIENT in entry_data
            )
        }
    
    @lru_cache(maxsize=10)
    def _get_client(self, name: str):
        """獲取 LINE API 客戶端."""
        if not name:
            raise ValueError("Invalid bot name")

        if not self._clients:
            self._clients = self.get_bot_client

        if name in self._clients:
            return self._clients[name]

        self._clients = self.get_bot_client
        api_client = self._clients.get(name)
        if not api_client:
            raise ValueError(f"LINE API client not found: {name}")

        return api_client

    async def _create_content_dict(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """根據資料建立訊息字典."""
        message_type = message_type
        creator = MESSAGE_CREATORS.get(message_type)
        return creator(data)

    async def _send_message_service(self, call: ServiceCall, is_reply: bool = True) -> None:
        """通用訊息發送服務處理器."""
        try:
            bot_name = call.data[CONF_NAME]
            message_count = len(call.data["messages"])

            # 獲取 LINE API 客戶端
            line_api_client = self._get_client(bot_name)

            # 取得可選參數
            retry_key = call.data.get("retry_key")
            notification_disabled = call.data.get(
                "notification_disabled", False
            )

            if is_reply:
                await line_api_client.reply_message(
                    reply_token=call.data[ATTR_REPLY_TOKEN],
                    messages=call.data["messages"],
                    notification_disabled=notification_disabled
                )
                _LOGGER.info(
                    f"Reply {message_count} message(s) sent successfully for bot: {bot_name}"
                )
            else:
                await line_api_client.push_message(
                    to=call.data["to"],
                    messages=call.data["messages"],
                    notification_disabled=notification_disabled,
                    retry_key=retry_key
                )
                _LOGGER.info(
                    f"Push {message_count} message(s) sent successfully to "
                    f"{call.data['to']} for bot: {bot_name}"
                )

        except Exception as e:
            action = "reply" if is_reply else "push"
            _LOGGER.error(f"Error sending {action} message: {e}")

    # service callback
    async def reply_message(self, call: ServiceCall) -> None:
        """回覆訊息服務."""
        await self._send_message_service(call, is_reply=True)

    async def push_message(self, call: ServiceCall) -> None:
        """推送訊息服務."""
        await self._send_message_service(call, is_reply=False)
    
    async def create_text_content(self, call: ServiceCall) -> ServiceResponse:
        """建立文字訊息內容."""
        return await self._create_content_dict("text", call.data)

    async def create_text_v2_content(self, call: ServiceCall) -> ServiceResponse:
        """建立文字 V2 訊息內容."""
        return await self._create_content_dict("textV2", call.data)
    
    async def create_image_content(self, call: ServiceCall) -> ServiceResponse:
        """建立圖片訊息內容."""
        return await self._create_content_dict("image", call.data)
    
    async def create_video_content(self, call: ServiceCall) -> ServiceResponse:
        """建立影片訊息內容."""
        return await self._create_content_dict("video", call.data)
    
    async def create_audio_content(self, call: ServiceCall) -> ServiceResponse:
        """建立音訊訊息內容."""
        return await self._create_content_dict("audio", call.data)
    
    async def create_location_content(self, call: ServiceCall) -> ServiceResponse:
        """建立位置訊息內容."""
        return await self._create_content_dict("location", call.data)
    
    async def create_sticker_content(self, call: ServiceCall) -> ServiceResponse:
        """建立貼圖訊息內容."""
        return await self._create_content_dict("sticker", call.data)
    
    async def create_flex_content(self, call: ServiceCall) -> ServiceResponse:
        """建立 Flex 訊息內容."""
        return await self._create_content_dict("flex", call.data)
    
    async def create_imagemap_content(self, call: ServiceCall) -> ServiceResponse:
        """建立 imagemap 訊息內容."""
        return await self._create_content_dict("imagemap", call.data)
    
    async def create_template_content(self, call: ServiceCall) -> ServiceResponse:
        """建立 template 訊息內容."""
        return await self._create_content_dict("template", call.data)

    async def setup_services(self) -> None:
        """設定全域 LINE Bot 服務."""
        notify, content = self.service_registry
        
        for domain, service, handler, schema, describe in notify:
            self.hass.services.async_register(domain, service, handler, schema=schema)
            async_set_service_schema(self.hass, domain, service, describe)

        for domain, service, handler, schema, supports_response in content:
            self.hass.services.async_register(
                domain, service, handler, schema=schema, supports_response=supports_response
            )

        _LOGGER.info("LINE Bot services registered")

    async def remove_services(self) -> None:
        """移除全域 LINE Bot 服務"""
        domain_data = self.hass.data.get(DOMAIN, {})
        if any(isinstance(data, dict) for data in domain_data.values()):
            return

        notify, content = self.service_registry

        for domain, service, _, _ in notify:
            if self.hass.services.has_service(domain, service):
                self.hass.services.async_remove(domain, service)

        for domain, service, _, _, _ in content:
            if self.hass.services.has_service(domain, service):
                self.hass.services.async_remove(domain, service)

        _LOGGER.info("LINE Bot services removed")