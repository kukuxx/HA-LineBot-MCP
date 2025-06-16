"""Model Context Protocol sessions."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from anyio.streams.memory import MemoryObjectSendStream
from mcp import types

from homeassistant.util import ulid as ulid_util


_LOGGER = logging.getLogger(__name__)


@dataclass
class Session:
    """A session for the Model Context Protocol."""

    read_stream_writer: MemoryObjectSendStream[types.JSONRPCMessage | Exception]
    
    def close(self) -> None:
        """關閉會話"""
        try:
            self.read_stream_writer.close()
        except Exception as e:
            _LOGGER.warning(f"Error closing session stream: {e}")


class SessionManager:
    """管理 MCP 傳輸層的 SSE 會話"""

    def __init__(self) -> None:
        """初始化 SSE 服務器傳輸"""
        self._sessions: dict[str, Session] = {}

    @asynccontextmanager
    async def create(self, session: Session) -> AsyncGenerator[str, None]:
        """創建新會話 ID 的上下文管理器"""
        session_id = ulid_util.ulid_now()
        _LOGGER.debug(f"Creating session: {session_id}")
        self._sessions[session_id] = session
        try:
            yield session_id
        finally:
            _LOGGER.debug(f"Closing session: {session_id}")
            session = self._sessions.pop(session_id, None)
            if session:
                session.close()

    def get(self, session_id: str) -> Session | None:
        """獲取現有會話"""
        session = self._sessions.get(session_id)
        return session

    def get_active_session_count(self) -> int:
        """獲取活躍會話數量"""
        return len(self._sessions)

    def close(self) -> None:
        """關閉所有開放的會話"""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
        _LOGGER.debug("All sessions closed")
