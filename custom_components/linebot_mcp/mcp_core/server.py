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
    MCP_TOOL_PUSH_MESSAGE,
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
        "description": "LINE message: text, image, or location",
        "oneOf": [
            {
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["text"],
                        "description": "Text message"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message content",
                        "maxLength": 5000
                    }
                },
                "required": ["type", "text"]
            },
            {
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["image"],
                        "description": "Image message"
                    },
                    "originalContentUrl": {
                        "type": "string",
                        "format": "uri",
                        "description": "HTTPS URL of original image (JPEG/PNG, max 10MB)",
                        "maxLength": 2000
                    },
                    "previewImageUrl": {
                        "type": "string",
                        "format": "uri",
                        "description": "HTTPS URL of preview image (max 1MB)",
                        "maxLength": 2000
                    }
                },
                "required": ["type", "originalContentUrl", "previewImageUrl"]
            },
            {
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["location"],
                        "description": "Location message"
                    },
                    "title": {
                        "type": "string",
                        "description": "Location title/label"
                    },
                    "address": {
                        "type": "string",
                        "description": "Full address"
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude coordinate"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude coordinate"
                    }
                },
                "required": ["type", "address", "latitude", "longitude"]
            }
        ]
    }




class LineBotMCP:
    """LINE Bot MCP 服務器"""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """初始化 LINE Bot MCP 服務器"""
        self.hass = hass
        self._api_client = None
        self._send_toolname = MCP_TOOL_PUSH_MESSAGE
        self._reply_toolname = MCP_TOOL_REPLY_MESSAGE
        self._quota_toolname = MCP_TOOL_GET_QUOTA_INFO

    @property
    def _get_tool_definitions(self) -> list[types.Tool]:
        """獲取工具定義"""
        return [
            types.Tool(
                name=self._send_toolname,
                description="Send messages to LINE user/group. Supports text, image, location messages (max 5 per request)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "botID": {
                            "type": "string",
                            "description": "Line Bot ID"
                        },
                        "to": {
                            "type": "string",
                            "description": "User ID (starts with U), Group ID (starts with C), or Room ID (starts with R)",
                            "pattern": "^[UCR][0-9a-f]{32}$"
                        },
                        "messages": {
                            "type": "array",
                            "description": "Array of messages to send",
                            "items": _get_line_message_schema(),
                            "minItems": 1,
                            "maxItems": 5    
                        }
                    },
                    "required": ["botID", "to", "messages"]
                }
            ),
            types.Tool(
                name=self._reply_toolname,
                description="Reply to LINE message within 30s (max 5 messages)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "botID": {
                            "type": "string",
                            "description": "Line Bot ID"
                        },
                        "reply_token": {
                            "type": "string",
                            "description": "Reply token from webhook (30s validity)"
                        },
                        "messages": {
                            "type": "array",
                            "items": _get_line_message_schema(),
                            "minItems": 1,
                            "maxItems": 5    
                        }
                    },
                    "required": ["botID", "reply_token", "messages"]
                }
            ),
            types.Tool(
                name=self._quota_toolname,
                description="Get LINE Bot monthly message quota usage information",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "botID": {
                            "type": "string",
                            "description": "Line Bot ID"
                        }
                    },
                    "required": ["botID"]
                }
            )
        ]

    def _get_api_client(self, botname):
        """獲取 LINE API 客戶端"""
        try:
            if self._api_client is None:
                service_manager = self.hass.data[DOMAIN][SERVICE_MANAGER]
                self._api_client = service_manager.get_bot_client
            
            if not botname:
                raise HomeAssistantError("Invalid bot ID")

            return self._api_client[botname]
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
        botname = arguments["botID"]
        client = self._get_api_client(botname)
        api_data = {
            "to": arguments["to"],
            "messages": arguments["messages"],
        }

        await client.push_message(**api_data)

        message_count = len(arguments["messages"])
        self._fire_tool_event(self._send_toolname, {
            "botname": botname,
            "to": arguments["to"],
            "message_count": message_count,
            "success": True
        })

        return [types.TextContent(
            type="text",
            text=f"{message_count} message(s) sent successfully to {arguments['to']} via {botname}"
        )]

    async def _handle_reply_message(self, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        """處理回覆訊息工具"""
        botname = arguments["botID"]
        client = self._get_api_client(botname)
        api_data = {
            "reply_token": arguments["reply_token"],
            "messages": arguments["messages"],
        }

        await client.reply_message(**api_data)

        message_count = len(arguments["messages"])
        self._fire_tool_event(self._reply_toolname, {
            "botname": botname,
            "reply_token": arguments["reply_token"],
            "message_count": message_count,
            "success": True
        })

        return [types.TextContent(
            type="text",
            text=f"{message_count} reply message(s) sent successfully via {botname}"
        )]

    async def _handle_get_quota_info(self, arguments: dict[str, Any]) -> Sequence[types.TextContent]:
        """處理獲取配額資訊工具"""
        botname = arguments["botID"]
        sensor = self.hass.states.get(f"sensor.linebot_{botname.replace("@", "").strip()}_message_quota")
        if sensor is None:
            return [types.TextContent(type="text", text=f"Quota information not available for '{botname}'")]

        quota_data = sensor.attributes
        info_text = (
            f"Total: {quota_data.get('total_quota', 'N/A')}\n"
            f"Usage: {quota_data.get("used_quota", 'N/A')}"
        )

        self._fire_tool_event(self._quota_toolname, {
            "botname": botname,
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


async def create_server(hass: HomeAssistant) -> Server:
    """創建新的 LINE Bot MCP 服務器"""
    server = Server[Any]("linebot_mcp")
    linebot_mcp = LineBotMCP(hass)

    @server.list_tools()  # type: ignore[no-untyped-call, misc]
    async def list_tools() -> list[types.Tool]:
        """列出可用的 LINE Bot 工具"""
        return linebot_mcp._get_tool_definitions

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def call_tool(tool_name: str, arguments: dict) -> Sequence[types.TextContent]:
        """處理工具調用"""
        return await linebot_mcp.call_tool(tool_name, arguments)

    return server
