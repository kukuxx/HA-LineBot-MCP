"""LINE Bot SSE　MCP."""
from __future__ import annotations

import logging

import anyio
from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound
from aiohttp_sse import sse_response
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from mcp import types

from .server import MCPServerManager
from .session import Session

from ..const import (
    DOMAIN, 
    SESSION_MANAGER, 
    SERVER_MANAGER,
    SHUTDOWN_EVENT,
)


_LOGGER = logging.getLogger(__name__)
SSE_API = f"/linebotmcp/sse"
MESSAGES_API = f"/linebotmcp/messages/{{session_id}}"


@callback
def async_register(hass: HomeAssistant) -> None:
    """註冊 HTTP API"""
    hass.http.register_view(LineBotMCPSSEView())
    hass.http.register_view(LineBotMCPMessagesView())


def get_manager(hass: HomeAssistant):
    """獲取 LINE Bot MCP manager"""
    session_manager = hass.data[DOMAIN][SESSION_MANAGER]
    shutdown_event = hass.data[DOMAIN][SHUTDOWN_EVENT]

    if not session_manager or not shutdown_event:
        raise HTTPNotFound(text="LINE Bot MCP server is not configured")
    return session_manager, shutdown_event


async def get_server(hass: HomeAssistant):
    """獲取 LINE Bot MCP server"""
    server_manager = hass.data[DOMAIN][SERVER_MANAGER]
    return await server_manager.get_server()


class LineBotMCPSSEView(HomeAssistantView):
    """LINE Bot MCP SSE 端點"""

    name = f"{DOMAIN}:sse"
    url = SSE_API
    requires_auth = True

    async def get(self, request: web.Request):
        """處理 LINE Bot MCP 的 SSE 訊息"""
        # _LOGGER.warning("headers received: %s", dict(request.headers))
        hass = request.app[KEY_HASS]
        
        try:
            session_manager, shutdown_event = get_manager(hass)
            server = await get_server(hass)  
            options = await hass.async_add_executor_job(
                server.create_initialization_options  # Reads package for version info
            )

            read_stream_writer, read_stream_reader = anyio.create_memory_object_stream(0)
            write_stream_writer, write_stream_reader = anyio.create_memory_object_stream(0)

            async with (
                sse_response(request) as response,
                session_manager.create(Session(read_stream_writer)) as session_id,
            ):
                session_uri = MESSAGES_API.format(session_id=session_id)
                _LOGGER.debug(f"Sending SSE endpoint: {session_uri}")
                await response.send(session_uri, event="endpoint")

                async def sse_reader() -> None:
                    """轉發 MCP 服務器回應給客戶端"""
                    try:
                        async for message in write_stream_reader:
                            _LOGGER.debug(f"Sending SSE message: {message}")
                            try:
                                with anyio.fail_after(5):
                                    await response.send(
                                        message.model_dump_json(by_alias=True, exclude_none=True),
                                        event="message",
                                    )
                            except TimeoutError:
                                _LOGGER.warning("Timeout sending SSE message")
                    
                    except anyio.get_cancelled_exc_class():
                        _LOGGER.debug("SSE reader cancelled")
                        raise
                    except Exception as e:
                        _LOGGER.debug(f"SSE reader error: {e}")
                
                async def server_runner() -> None:
                    """運行 MCP 伺服器"""
                    try:
                        await server.run(read_stream_reader, write_stream_writer, options)
                    except anyio.get_cancelled_exc_class():
                        _LOGGER.debug("Server runner cancelled")
                        raise
                    except Exception as e:
                        _LOGGER.debug(f"Server runner error: {e}")
  
                try:
                    async with anyio.create_task_group() as tg:
                        tg.start_soon(sse_reader)
                        tg.start_soon(server_runner)
                        await shutdown_event.wait()
                        tg.cancel_scope.cancel()
                        await response.send(
                            '{"type": "close", "reason": "server_shutdown"}',
                            event="close"
                        )
                        _LOGGER.debug("Sent close event")
                        
                except* Exception as exc_group:
                    for exc in exc_group.exceptions:
                        _LOGGER.error(f"Task error in session {session_id}: {type(exc).__name__}: {exc}")
                finally:
                    await write_stream_writer.aclose()
                    _LOGGER.debug(f"SSE connection for {session_id} is done.")
                
        except Exception as e:
            _LOGGER.error(f"Error handling SSE request: {e}")
            raise HTTPBadRequest(text="Could not handle SSE request") from e
    

class LineBotMCPMessagesView(HomeAssistantView):
    """LINE Bot MCP 訊息端點"""

    name = f"{DOMAIN}:messages"
    url = MESSAGES_API
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        session_id: str,
    ):
        """處理 LINE Bot MCP 的傳入訊息"""
        hass = request.app[KEY_HASS]
        session_manager, _ = get_manager(hass)

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
