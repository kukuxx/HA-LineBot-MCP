"""The LINE Bot MCP Server implementation."""
from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from mcp import types
from mcp.server import Server
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..const import (
    DOMAIN,
    SERVICE_MANAGER,
    MCP_TOOL_SEND_MESSAGE,
    MCP_TOOL_REPLY_MESSAGE,
    MCP_TOOL_GET_QUOTA_INFO,
    EVENT_MCP_TOOL_CALLED,
)


_LOGGER = logging.getLogger(__name__)


# LINE 訊息格式定義
def _get_line_message_schema() -> dict:
    """獲取 LINE 訊息格式的 JSON Schema"""
    return {
        "type": "object",
        "description": "LINE message object. Must be one of text, image, or location.",
        "oneOf": [
            {
                "properties": {
                    "type": {
                        "const": "text",
                        "description": "Indicates this message is a text message"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text message content (max 5000 characters)"
                    }
                },
                "required": ["type", "text"]
            },
            {
                "type": "object",
                "properties": {
                    "type": {
                        "const": "image",
                        "description": "Indicates this message is an image message"
                    },
                    "originalContentUrl": {
                        "type": "string",
                        "format": "uri",
                        "description": (
                            "Required. HTTPS URL of the original image (JPEG or PNG, max 10MB, max 2000 characters)."
                        ),
                        "maxLength": 2000
                    },
                    "previewImageUrl": {
                        "type": "string",
                        "format": "uri",
                        "description": (
                            "Required. HTTPS URL of the preview image (JPEG or PNG, max 1MB, max 2000 characters)."
                            "If omitted, originalContentUrl may be used as preview depending on device."
                        ),
                        "maxLength": 2000
                    }
                },
                "required": ["type", "originalContentUrl", "previewImageUrl"]
            },

            {
                "properties": {
                    "type": {
                        "const": "location",
                        "description": "Indicates this message is a location message"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the location, shown as a label above the address (e.g., 'My Home')"
                    },
                    "address": {
                        "type": "string",
                        "description": "Full address of the location to display in the message"
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of the location"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of the location"
                    }
                },
                "required": ["type", "address", "latitude", "longitude"]
            }
        ]
    }



class LineBotMCP:
    """LINE Bot MCP 服務器"""
    
    def __init__(self, hass: HomeAssistant, sername: str) -> None:
        """初始化 LINE Bot MCP 服務器"""
        self.hass = hass
        self._sername = sername
        self._botname = f"@{sername}"
        self._api_client = None
        self._send_toolname = MCP_TOOL_SEND_MESSAGE.format(sername)
        self._reply_toolname = MCP_TOOL_REPLY_MESSAGE.format(sername)
        self._quota_toolname = MCP_TOOL_GET_QUOTA_INFO.format(sername)

    @property
    def _get_tool_definitions(self) -> list[types.Tool]:
        """獲取工具定義"""
        return [
            types.Tool(
                name=self._send_toolname,
                description="Send messages to a LINE user or group. Supports multiple message types including text, image, video, audio, location, sticker, and flex messages. Maximum 5 messages per request.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "User ID (starts with 'U') or Group ID (starts with 'C') or Room ID (starts with 'R')",
                            "pattern": "^[UCR][0-9a-f]{32}$"
                        },
                        "messages": {
                            "type": "array",
                            "description": "An array of messages to send (max 5 messages). Each item must be one of text, image, location, etc.",
                            "items": _get_line_message_schema(),
                            "minItems": 1,
                            "maxItems": 5    
                        },
                    },
                    "required": ["to","messages"],
                    "additionalProperties": False
                },
            ),
            types.Tool(
                name=self._reply_toolname,
                description="Reply to a LINE message with multiple messages. Can only be used within 30 seconds of receiving the original message. Maximum 5 messages per reply.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reply_token": {
                            "type": "string",
                            "description": "Reply token received from webhook event (valid for 30 seconds)"
                        },
                        "messages": {
                            "type": "array",
                            "description": "An array of messages to send (max 5 messages). Each item must be one of text, image, location, etc.",
                            "items": _get_line_message_schema(),
                            "minItems": 1,
                            "maxItems": 5    
                        },
                    },
                    "required": ["reply_token","messages"],
                    "additionalProperties": False
                },
            ),
            types.Tool(
                name=self._quota_toolname,
                description="Get LINE Bot message quota information including quota type (limited/unlimited), total quota value, current usage, and usage percentage.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
        ]

    def _get_api_client(self):
        """獲取 LINE API 客戶端"""
        try:
            if self._api_client is None:
                service_manager = self.hass.data[DOMAIN][SERVICE_MANAGER]
                self._api_client = service_manager.get_bot_client[self._botname]
            
            return self._api_client
        except KeyError as e:
            raise HomeAssistantError(f"LINE API client not found: {e}") from e

    def _fire_tool_event(self, tool_name: str, data: dict[str, Any]) -> None:
        """觸發工具調用事件"""
        event_data = {
            "tool_name": tool_name,
            **data
        }
        self.hass.bus.async_fire(
            EVENT_MCP_TOOL_CALLED, 
            event_data
        )

    async def _handle_send_message(self, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        """處理發送訊息工具"""
        client = self._get_api_client()
        api_data = {
            "to": arguments["to"],
            "messages": arguments["messages"],
        }

        if "retry_key" in arguments:
            api_data["retry_key"] = arguments["retry_key"]

        await client.push_message(**api_data)

        message_count = len(arguments["messages"])
        self._fire_tool_event(self._send_toolname, {
            "to": arguments["to"],
            "message_count": message_count,
            "success": True
        })

        return [types.TextContent(
            type="text",
            text=f"{message_count} message(s) sent successfully to {arguments['to']} via {self._botname}"
        )]

    async def _handle_reply_message(self, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        """處理回覆訊息工具"""
        client = self._get_api_client()
        api_data = {
            "reply_token": arguments["reply_token"],
            "messages": arguments["messages"],
        }

        await client.reply_message(**api_data)

        message_count = len(arguments["messages"])
        self._fire_tool_event(self._reply_toolname, {
            "reply_token": arguments["reply_token"],
            "message_count": message_count,
            "success": True
        })

        return [types.TextContent(
            type="text",
            text=f"{message_count} reply message(s) sent successfully via {self._botname}"
        )]

    async def _handle_get_quota_info(self) -> Sequence[types.TextContent]:
        """處理獲取配額資訊工具"""
        sensor = self.hass.states.get(f"sensor.{DOMAIN}_{self._sername}_message_quota")
        if sensor is None:
            return [types.TextContent(type="text", text=f"Quota information not available for '{self._botname}'")]

        quota_data = sensor.attributes
        info_text = (
            f"Usage: {quota_data.get("used_quota", 'N/A')}\n"
        )

        self._fire_tool_event(self._quota_toolname, {
            "quota_info": quota_data,
            "success": True
        })

        return [types.TextContent(type="text", text=info_text)]
        
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        """處理工具調用"""
        _LOGGER.debug(f"Tool call {tool_name}: {arguments}")

        try:
            if tool_name == self._send_toolname:
                return await self._handle_send_message(arguments)
            elif tool_name == self._reply_toolname:
                return await self._handle_reply_message(arguments)
            elif tool_name == self._quota_toolname:
                return await self._handle_get_quota_info(arguments)
            else:
                raise HomeAssistantError(f"Unknown tool: {tool_name}")

        except Exception as e:
            _LOGGER.error(f"Error calling : {e}")
            self._fire_tool_event(tool_name, {
                "error": str(e),
                "success": False
            })
            raise HomeAssistantError(f"Error calling tool: {e}") from e


async def create_server(hass: HomeAssistant, sername: str) -> Server:
    """創建新的 LINE Bot MCP 服務器"""
    server = Server[Any](f"{DOMAIN}_{sername}")
    linebot_mcp = LineBotMCP(hass, sername)

    @server.list_tools()  # type: ignore[no-untyped-call, misc]
    async def list_tools() -> list[types.Tool]:
        """列出可用的 LINE Bot 工具"""
        return linebot_mcp._get_tool_definitions

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def call_tool(tool_name: str, arguments: dict) -> Sequence[types.TextContent]:
        """處理工具調用"""
        return await linebot_mcp.call_tool(tool_name, arguments)

    return server
