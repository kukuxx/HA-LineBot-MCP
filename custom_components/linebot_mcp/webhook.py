"""LINE Bot Webhook handler for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import json
import re

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    PostbackEvent,
)

from .line_api_client import (
    create_text_message,
    create_image_message,
    create_location_message,
)
from .const import (
    DOMAIN,
    CONF_AGENT_ID,
    CONF_AUTO_REPLY,
    LINE_API_CLIENT,
    EVENT_MESSAGE_RECEIVED,
    EVENT_POSTBACK,
    ATTR_USER_ID,
    ATTR_GROUP_ID,
    ATTR_ROOM_ID,
    ATTR_MESSAGE_ID,
    ATTR_MESSAGE_TYPE,
    ATTR_MESSAGE_TEXT,
    ATTR_REPLY_TOKEN,
    ATTR_TIMESTAMP,
    ATTR_SOURCE_TYPE,
    LINE_SIGNATURE,
    ERROR_INVALID_SIGNATURE,
    ERROR_INTERNAL_SERVER,
)

_LOGGER = logging.getLogger(__name__)


class LineBotWebhookView(HomeAssistantView):
    """處理 LINE Bot webhook 請求的視圖."""

    url = None
    name = None
    requires_auth = False

    def __init__(self, 
        botname: str,
        channel_secret: str, 
        entry_id: str, 
    ):
        """初始化 webhook 視圖."""
        self.hass = None
        self.entry_id = entry_id
        self.botname = botname
        self.channel_secret = channel_secret
        self._config_entry = None
        self._agent_id = None
        self._auto_reply = None 
        self._client = None

        # 初始化 webhook parser
        self.parser = WebhookParser(self.channel_secret)

        _LOGGER.debug(f"Webhook view initialized for path: {self.url}")

    async def post(self, request: web.Request) -> web.Response:
        """處理 POST 請求"""
        try:
            self.hass = request.app[KEY_HASS]

            if self._config_entry is None:
                self._config_entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if self._client is None:
                self._client = self.hass.data[DOMAIN][self.entry_id][LINE_API_CLIENT]

            self._agent_id = self.hass.data[DOMAIN][self.entry_id][CONF_AGENT_ID]
            self._auto_reply = self.hass.data[DOMAIN][self.entry_id][CONF_AUTO_REPLY]
            

            # 取得簽名和請求內容
            signature = request.headers[LINE_SIGNATURE]
            body = await request.text()

            _LOGGER.debug(f"Received webhook request with signature: {signature}")
            _LOGGER.debug(f"Request body: {body}")

            # 驗證簽名並解析事件
            try:
                events = self.parser.parse(body, signature)
            except InvalidSignatureError:
                _LOGGER.error("Invalid signature from webhook")
                return web.Response(status=400, text=ERROR_INVALID_SIGNATURE)
            
            def _create_task(event):
                if isinstance(event, MessageEvent):
                    return self._config_entry.async_create_task(
                        self.hass,
                        self._handle_message_event(event),
                        f"{self.botname}: MessageEvent"
                    )
                elif isinstance(event, PostbackEvent):
                    return self._config_entry.async_create_task(
                        self.hass,
                        self._handle_postback_event(event),
                        f"{self.botname}: PostbackEvent"
                    )
                else:
                    return self._config_entry.async_create_task(
                        self.hass,
                        self._handle_default(event),
                        f"{self.botname}: DefaultEvent"
                    )
            
            tasks = [_create_task(event) for event in events]

            return web.Response(status=200, text="OK")

        except Exception as e:
            _LOGGER.error(f"Error handling webhook: {e}")
            return web.Response(status=500, text=ERROR_INTERNAL_SERVER)

    async def _handle_message_event(self, event: MessageEvent, *args) -> None:
        """處理訊息事件."""
        # 取得基本資訊
        source = event.source
        message = event.message

        # 準備事件資料
        event_data = {
            ATTR_SOURCE_TYPE: source.type,
            ATTR_USER_ID: getattr(source, "user_id", None),
            ATTR_GROUP_ID: getattr(source, "group_id", None),
            ATTR_ROOM_ID: getattr(source, "room_id", None),
            "entry_id": self.entry_id,
            ATTR_MESSAGE_ID: message.id,
            ATTR_REPLY_TOKEN: event.reply_token,
            ATTR_TIMESTAMP: event.timestamp,
        }
        
        # 根據訊息類型處理
        if message.type == "text":
            event_data[ATTR_MESSAGE_TYPE] = "text"
            event_data[ATTR_MESSAGE_TEXT] = message.text
            if self._auto_reply:
                # 調用 conversation 服務進行自動回覆
                response = await self.hass.services.async_call(
                    "conversation",
                    "process",
                    {
                        "language": "zh-TW",
                        "agent_id": self._agent_id,
                        "text": event_data.get(ATTR_MESSAGE_TEXT),
                        "conversation_id": event_data[ATTR_USER_ID] if event_data[ATTR_USER_ID] else "",
                    },
                    blocking=True,
                    return_response=True,
                )
                if response:
                    _LOGGER.info(f"{response}")

                    speech = response["response"]["speech"]["plain"]["speech"]
                    data = self.extract_json_or_text(speech)
                    msg = []
                    if "text" in data and "address" in data and "latitude" in data and "longitude" in data:
                        msg.append(create_text_message(data["text"]))
                        msg.append(create_location_message(data["address"], data["latitude"], data["longitude"]))
                    elif "image_url" in data and "text" in data:
                        msg.append(create_text_message(data["text"]))
                        msg.append(create_image_message(data["image_url"]))
                    elif "text" in data:
                        msg.append(create_text_message(data["text"]))
                    else:
                        msg.append(create_text_message("I'm sorry, I don't understand."))

                    await self._client.reply_message(event_data[ATTR_REPLY_TOKEN], msg)
                    
                _LOGGER.info(f"Auto reply triggered for user {event_data.get(ATTR_USER_ID)}")
                
        elif message.type == "image":
            event_data[ATTR_MESSAGE_TYPE] = "image"
        elif message.type == "video":
            event_data[ATTR_MESSAGE_TYPE] = "video"
        elif message.type == "audio":
            event_data[ATTR_MESSAGE_TYPE] = "audio"
        elif message.type == "file":
            event_data[ATTR_MESSAGE_TYPE] = "file"
            event_data["file_name"] = message.file_name
            event_data["file_size"] = message.file_size
        elif message.type == "location":
            event_data[ATTR_MESSAGE_TYPE] = "location"
            event_data["title"] = message.title
            event_data["address"] = message.address
            event_data["latitude"] = message.latitude
            event_data["longitude"] = message.longitude
        elif message.type == "sticker":
            event_data[ATTR_MESSAGE_TYPE] = "sticker"
            event_data["package_id"] = message.package_id
            event_data["sticker_id"] = message.sticker_id
        
        # 觸發 Home Assistant 事件
        self.hass.bus.async_fire(EVENT_MESSAGE_RECEIVED.format(self.botname), event_data)

        message_display = event_data.get(
            ATTR_MESSAGE_TEXT,
            f"[{event_data[ATTR_MESSAGE_TYPE]}]"
        )
        _LOGGER.info(
            f"Received message from user {event_data.get(ATTR_USER_ID)}: {message_display}"
        )

    async def _handle_postback_event(self, event: PostbackEvent) -> None:
        """處理回傳事件"""
        user_id = getattr(event.source, "user_id", None)

        event_data = {
            ATTR_USER_ID: user_id,
            ATTR_REPLY_TOKEN: event.reply_token,
            ATTR_TIMESTAMP: event.timestamp,
            "postback_data": event.postback.data,
        }

        # 如果有 params，也加入事件資料
        if event.postback.params is not None:
            event_data["postback_params"] = event.postback.params

        self.hass.bus.async_fire(EVENT_POSTBACK.format(self.botname), event_data)
        _LOGGER.info(
            f"Received postback from user {user_id or 'unknown'}: {event_data['postback_data']}"
        )

    def _handle_default(self, event):
        """處理預設事件"""
        _LOGGER.debug(f"Received default event: {event}")
    
    def extract_json_or_text(self, response_speech: str) -> dict:
        """
        嘗試從 LLM 回傳的 speech 中解析出 JSON 格式內容，
        如果沒有，就當成純文字包裝成 {"text": "..."}。
        """
        try:
            # 嘗試使用正規表達式抓出第一個 JSON block
            match = re.search(r'({.*})', response_speech)
            if match:
                json_str = match.group(1)
                result = json.loads(json_str)

                if isinstance(result, dict) and "text" in result:
                    return result
        except json.JSONDecodeError:
            pass

        # 若抓不到 JSON，就把整段內容包裝成 text
        return {"text": response_speech.strip()}