"""LINE Bot SSE　MCP."""
from __future__ import annotations

import logging
from weakref import WeakValueDictionary

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound
from aiohttp_sse import sse_response
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from mcp import types

from ..const import DOMAIN, SESSION_MANAGER
from .server import create_server
from .session import Session


_LOGGER = logging.getLogger(__name__)

# 使用弱引用快取已創建的 server 實例
_SERVER_CACHE: WeakValueDictionary[str, object] = WeakValueDictionary()


@callback
def async_register(hass: HomeAssistant, entry_id: str, sername: str) -> None:
    """註冊 HTTP API"""
    sse_view, message_view = create_mcp_view(entry_id, sername)
        
    hass.http.register_view(sse_view)
    hass.http.register_view(message_view)

def create_mcp_view(entry_id: str, sername: str):
    sse_class = type(
        f"MCPSSEView_{entry_id}",
        (LineBotMCPSSEView,),
        {
            "name": f"{DOMAIN}_{sername}:sse",
            "url": f"/{DOMAIN}-{sername}/sse",
        }
    )
    
    message_class = type(
        f"MCPMessagesView_{entry_id}",
        (LineBotMCPMessagesView,),
        {
            "name": f"{DOMAIN}_{sername}:messages",
            "url": f"/{DOMAIN}-{sername}/messages/{{session_id}}",
        }
    )

    return sse_class(entry_id, sername), message_class(entry_id)



def get_session_manager(hass: HomeAssistant, entry_id: str):
    """獲取啟用的 LINE Bot MCP 配置項目"""
    manager = hass.data[DOMAIN][entry_id][SESSION_MANAGER]
    if not manager:
        raise HTTPNotFound(text="LINE Bot MCP server is not configured")
    return manager


class LineBotMCPSSEView(HomeAssistantView):
    """LINE Bot MCP SSE 端點"""

    name = None
    url = None

    def __init__(self, entry_id: str, sername: str):
        self.entry_id = entry_id
        self.sername = sername

    async def get(self, request: web.Request) -> web.StreamResponse:
        """處理 LINE Bot MCP 的 SSE 訊息"""
        hass = request.app[KEY_HASS]
        session_manager = get_session_manager(hass, self.entry_id)

        if (cache_key := self.entry_id) not in _SERVER_CACHE:
            server = await create_server(hass, self.sername)
            _SERVER_CACHE[cache_key] = server
        else:
            server = _SERVER_CACHE[cache_key]
       
        options = await hass.async_add_executor_job(
            server.create_initialization_options  # Reads package for version info
        )

        read_stream: MemoryObjectReceiveStream[types.JSONRPCMessage | Exception]
        read_stream_writer: MemoryObjectSendStream[types.JSONRPCMessage | Exception]
        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)

        write_stream: MemoryObjectSendStream[types.JSONRPCMessage]
        write_stream_reader: MemoryObjectReceiveStream[types.JSONRPCMessage]
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async with (
            sse_response(request) as response,
            session_manager.create(Session(read_stream_writer)) as session_id,
        ):
            session_uri = f"/{DOMAIN}-{self.sername}/messages/{session_id}"
            _LOGGER.debug(f"Sending SSE endpoint: {session_uri}")
            await response.send(session_uri, event="endpoint")

            async def sse_reader() -> None:
                """轉發 MCP 服務器回應給客戶端"""
                async for message in write_stream_reader:
                    _LOGGER.debug(f"Sending SSE message: {message}")
                    await response.send(
                        message.model_dump_json(by_alias=True, exclude_none=True),
                        event="message",
                    )

            async with anyio.create_task_group() as tg:
                tg.start_soon(sse_reader)
                await server.run(read_stream, write_stream, options)
                return response


class LineBotMCPMessagesView(HomeAssistantView):
    """LINE Bot MCP 訊息端點"""

    name = None
    url = None

    def __init__(self, entry_id: str):
        self.entry_id = entry_id

    async def post(
        self,
        request: web.Request,
        session_id: str,
    ) -> web.Response:
        """處理 LINE Bot MCP 的傳入訊息"""
        hass = request.app[KEY_HASS]
        session_manager = get_session_manager(hass, self.entry_id)

        if (session := session_manager.get(session_id)) is None:
            _LOGGER.info(f"Could not find session ID: '{session_id}'")
            raise HTTPNotFound(text=f"Could not find session ID '{session_id}'")
        
        try:
            json_data = await request.json()
            message = types.JSONRPCMessage.model_validate(json_data)
            _LOGGER.debug(f"Received client message: {message}")

            await session.read_stream_writer.send(message)
            return web.Response(status=200)
        except ValueError as err:
            _LOGGER.info(f"Failed to parse message: {err}")
            raise HTTPBadRequest(text="Could not parse message") from err
        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")
            raise HTTPBadRequest(text="Could not handle message") from e
