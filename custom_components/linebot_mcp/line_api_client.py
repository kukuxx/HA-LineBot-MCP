"""LINE Messaging API Client using Home Assistant aiohttp client."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    LINE_API_BASE_URL,
    LINE_API_TIMEOUT,
    LINE_API_REPLY_ENDPOINT,
    LINE_API_PUSH_ENDPOINT,
    LINE_API_MULTICAST_ENDPOINT,
    LINE_API_BROADCAST_ENDPOINT,
    LINE_API_NARROWCAST_ENDPOINT,
    LINE_API_BOT_INFO_ENDPOINT,
    LINE_API_QUOTA_ENDPOINT,
    LINE_API_QUOTA_CONSUMPTION_ENDPOINT,
    LINE_API_PROFILE_ENDPOINT,
    CONTENT_TYPE_JSON,
    HTTP_USER_AGENT,
    QUOTE_TOKEN_SUPPORTED_TYPES
)


_LOGGER = logging.getLogger(__name__)


@dataclass
class LineApiResponse:
    """LINE API 回應資料類別."""

    status_code: int
    headers: Dict[str, str]
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """檢查請求是否成功"""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """檢查是否有錯誤"""
        return self.status_code >= 400 or self.error is not None

    @property
    def request_id(self) -> Optional[str]:
        """取得請求 ID"""
        return self.headers.get('x-line-request-id')

    @property
    def rate_limit_remaining(self) -> Optional[int]:
        """取得剩餘請求次數"""
        remaining = self.headers.get('x-line-rate-limit-remaining')
        return int(remaining) if remaining else None


class LineApiError(Exception):
    """LINE API 錯誤."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class LineApiClient:
    """LINE Messaging API 客戶端."""
    
    def __init__(self, hass: HomeAssistant, access_token: str):
        """初始化 LINE API 客戶端."""
        self.hass = hass
        self.access_token = access_token
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def session(self) -> aiohttp.ClientSession:
        """取得 aiohttp session."""
        if self._session is None:
            self._session = async_get_clientsession(self.hass, verify_ssl=False)
        return self._session
    
    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """取得請求標頭."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": CONTENT_TYPE_JSON,
            "User-Agent": HTTP_USER_AGENT,
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        additional_headers: Optional[Dict[str, str]] = None,
    ) -> LineApiResponse:
        """發送 HTTP 請求到 LINE API."""
        url = f"{LINE_API_BASE_URL}{endpoint}"
        headers = self._get_headers(additional_headers)
        
        try:
            timeout = aiohttp.ClientTimeout(total=LINE_API_TIMEOUT)
            
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params,
                timeout=timeout,
            ) as response:
                response_headers = dict(response.headers)
                response_text = await response.text()
                
                # 記錄請求資訊
                request_id = response_headers.get('x-line-request-id', 'N/A')
                _LOGGER.debug(f"LINE API {method} {endpoint} - Status: {response.status}, Request ID: {request_id}")
                
                # 處理回應
                if response.status >= 400:
                    error_data = None
                    try:
                        if response_text:
                            error_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        pass
                    
                    error_message = f"LINE API error: {response.status}"
                    if error_data and "message" in error_data:
                        error_message += f" - {error_data['message']}"
                    
                    _LOGGER.error(f"{error_message}, Response: {response_text}")
                    raise LineApiError(
                        error_message, response.status, error_data
                    )
                
                # 解析成功回應
                response_data = None
                if response_text:
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        _LOGGER.warning(f"Failed to parse LINE API response as JSON: {e}")
                
                return LineApiResponse(
                    status_code=response.status,
                    headers=response_headers,
                    data=response_data,
                )
                
        except asyncio.TimeoutError as e:
            error_message = f"LINE API request timeout: {method} {endpoint}"
            _LOGGER.error(f"{error_message}")
            raise LineApiError(error_message) from e
        except aiohttp.ClientError as e:
            error_message = f"LINE API client error: {method} {endpoint} - {e}"
            _LOGGER.error(f"{error_message}")
            raise LineApiError(error_message) from e
        except Exception as e:
            error_message = f"Unexpected error in LINE API request: {method} {endpoint} - {e}"
            _LOGGER.error(f"{error_message}")
            raise LineApiError(error_message) from e
    
    async def get_bot_info(self) -> LineApiResponse:
        """取得 Bot 資訊"""
        return await self._make_request("GET", LINE_API_BOT_INFO_ENDPOINT)

    async def get_message_quota(self) -> LineApiResponse:
        """取得訊息配額."""
        return await self._make_request("GET", LINE_API_QUOTA_ENDPOINT)

    async def get_message_quota_consumption(self) -> LineApiResponse:
        """取得訊息配額使用情況."""
        return await self._make_request("GET", LINE_API_QUOTA_CONSUMPTION_ENDPOINT)

    async def get_profile(self, user_id: str) -> LineApiResponse:
        """取得用戶資料."""
        endpoint = f"{LINE_API_PROFILE_ENDPOINT}/{user_id}"
        return await self._make_request("GET", endpoint)

    async def reply_message(
        self,
        reply_token: str,
        messages: List[Dict[str, Any]],
        notification_disabled: bool = False,
    ) -> LineApiResponse:
        """回覆訊息."""
        data = {
            "replyToken": reply_token,
            "messages": messages,
            "notificationDisabled": notification_disabled,
        }

        return await self._make_request(
            "POST",
            LINE_API_REPLY_ENDPOINT,
            data=data
        )

    async def push_message(
        self,
        to: str,
        messages: List[Dict[str, Any]],
        notification_disabled: bool = False,
        custom_aggregation_units: Optional[str] = None,
        retry_key: Optional[str] = None,
    ) -> LineApiResponse:
        """推送訊息."""
        data = {
            "to": to,
            "messages": messages,
            "notificationDisabled": notification_disabled,
        }

        if custom_aggregation_units:
            data["customAggregationUnits"] = custom_aggregation_units

        additional_headers = {}
        if retry_key:
            additional_headers["X-Line-Retry-Key"] = retry_key

        return await self._make_request(
            "POST",
            LINE_API_PUSH_ENDPOINT,
            data=data,
            additional_headers=additional_headers
        )

    async def multicast(
        self,
        to: List[str],
        messages: List[Dict[str, Any]],
        notification_disabled: bool = False,
        custom_aggregation_units: Optional[str] = None,
        retry_key: Optional[str] = None,
    ) -> LineApiResponse:
        """群發訊息."""
        data = {
            "to": to,
            "messages": messages,
            "notificationDisabled": notification_disabled,
        }

        if custom_aggregation_units:
            data["customAggregationUnits"] = custom_aggregation_units

        additional_headers = {}
        if retry_key:
            additional_headers["X-Line-Retry-Key"] = retry_key

        return await self._make_request(
            "POST",
            LINE_API_MULTICAST_ENDPOINT,
            data=data,
            additional_headers=additional_headers
        )

    async def broadcast(
        self,
        messages: List[Dict[str, Any]],
        notification_disabled: bool = False,
        custom_aggregation_units: Optional[str] = None,
        retry_key: Optional[str] = None,
    ) -> LineApiResponse:
        """廣播訊息."""
        data = {
            "messages": messages,
            "notificationDisabled": notification_disabled,
        }

        if custom_aggregation_units:
            data["customAggregationUnits"] = custom_aggregation_units

        additional_headers = {}
        if retry_key:
            additional_headers["X-Line-Retry-Key"] = retry_key

        return await self._make_request(
            "POST",
            LINE_API_BROADCAST_ENDPOINT,
            data=data,
            additional_headers=additional_headers
        )

    async def narrowcast(
        self,
        messages: List[Dict[str, Any]],
        recipient: Optional[Dict[str, Any]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        limit: Optional[Dict[str, Any]] = None,
        notification_disabled: bool = False,
        retry_key: Optional[str] = None,
    ) -> LineApiResponse:
        """發送 narrowcast 訊息."""
        data = {
            "messages": messages,
            "notificationDisabled": notification_disabled,
        }

        if recipient:
            data["recipient"] = recipient

        if filter_dict:
            data["filter"] = filter_dict

        if limit:
            data["limit"] = limit

        additional_headers = {}
        if retry_key:
            additional_headers["X-Line-Retry-Key"] = retry_key

        return await self._make_request(
            "POST",
            LINE_API_NARROWCAST_ENDPOINT,
            data=data,
            additional_headers=additional_headers
        )


def create_text_message(text: str, quote_token: Optional[str] = None) -> Dict[str, Any]:
    """創建文字訊息."""
    message = {
        "type": "text",
        "text": text,
    }

    if quote_token:
        message["quoteToken"] = quote_token

    return message


def create_text_v2_message(
    text: str,
    quote_token: Optional[str] = None,
    mentions: Optional[List[Dict[str, Any]]] = None,
    emojis: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """創建文字訊息 v2（支援 mentions 和 emojis）."""
    message = {
        "type": "textV2",
        "text": text,
    }

    if quote_token:
        message["quoteToken"] = quote_token

    if mentions:
        message["mentions"] = mentions

    if emojis:
        message["emojis"] = emojis

    return message


def create_location_message(
    address: str,
    latitude: float,
    longitude: float,
    title: str = None,
) -> Dict[str, Any]:
    """創建位置訊息."""
    return {
        "type": "location",
        "title": address if title is None else title,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
    }


def create_sticker_message(
    package_id: str,
    sticker_id: str,
    quote_token: Optional[str] = None
) -> Dict[str, Any]:
    """創建貼圖訊息."""
    message = {
        "type": "sticker",
        "packageId": package_id,
        "stickerId": sticker_id,
    }

    if quote_token:
        message["quoteToken"] = quote_token

    return message


def create_image_message(
    original_content_url: str,
    preview_image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """創建圖片訊息."""
    return {
        "type": "image",
        "originalContentUrl": original_content_url,
        "previewImageUrl": preview_image_url or original_content_url,
    }


def create_video_message(
    original_content_url: str,
    preview_image_url: str,
) -> Dict[str, Any]:
    """創建影片訊息."""
    if not preview_image_url:
        raise ValueError("Video message requires preview_image_url")

    return {
        "type": "video",
        "originalContentUrl": original_content_url,
        "previewImageUrl": preview_image_url,
    }


def create_audio_message(
    original_content_url: str,
    duration: int,
) -> Dict[str, Any]:
    """創建音訊訊息."""
    return {
        "type": "audio",
        "originalContentUrl": original_content_url,
        "duration": duration,
    }


def create_flex_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """建立 Flex 訊息."""
    try:
        flex_content = json.loads(data["message"])
        return {
            "type": "flex",
            "altText": data.get("alt_text", "Flex Message"),
            "contents": flex_content
        }
    except (json.JSONDecodeError, Exception) as e:
        _LOGGER.error(f"Error parsing flex message: {e}")
        return create_text_message(data["message"])


def create_imagemap_message(
    base_url: str,
    alt_text: str,
    base_size: Dict[str, int],
    actions: List[Dict[str, Any]],
    video: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """創建 Imagemap 訊息."""
    message = {
        "type": "imagemap",
        "baseUrl": base_url,
        "altText": alt_text,
        "baseSize": base_size,
        "actions": actions
    }

    if video:
        message["video"] = video

    return message


def _create_template_message(
    alt_text: str,
    template: Dict[str, Any]
) -> Dict[str, Any]:
    """創建 Template 訊息."""
    return {
        "type": "template",
        "altText": alt_text,
        "template": template
    }


def create_buttons_template(
    text: str,
    actions: List[Dict[str, Any]],
    thumbnail_image_url: Optional[str] = None,
    image_aspect_ratio: Optional[str] = None,
    image_size: Optional[str] = None,
    image_background_color: Optional[str] = None,
    title: Optional[str] = None,
    default_action: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """創建 Buttons Template."""
    template = {
        "type": "buttons",
        "text": text,
        "actions": actions
    }

    if thumbnail_image_url:
        template["thumbnailImageUrl"] = thumbnail_image_url
    if image_aspect_ratio:
        template["imageAspectRatio"] = image_aspect_ratio
    if image_size:
        template["imageSize"] = image_size
    if image_background_color:
        template["imageBackgroundColor"] = image_background_color
    if title:
        template["title"] = title
    if default_action:
        template["defaultAction"] = default_action

    return template


def create_confirm_template(
    text: str,
    actions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """創建 Confirm Template."""
    if len(actions) != 2:
        raise ValueError("Confirm template requires exactly 2 actions")

    return {
        "type": "confirm",
        "text": text,
        "actions": actions
    }


def create_carousel_template(
    columns: List[Dict[str, Any]],
    image_aspect_ratio: Optional[str] = None,
    image_size: Optional[str] = None
) -> Dict[str, Any]:
    """創建 Carousel Template."""
    template = {
        "type": "carousel",
        "columns": columns
    }

    if image_aspect_ratio:
        template["imageAspectRatio"] = image_aspect_ratio
    if image_size:
        template["imageSize"] = image_size

    return template


def create_image_carousel_template(
    columns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """創建 Image Carousel Template."""
    return {
        "type": "image_carousel",
        "columns": columns
    }


def handle_template_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """創建 Template 訊息的靜態方法."""
    template_type = data.get("template_type", "buttons")
    alt_text = data.get("alt_text", "Template Message")

    if template_type == "buttons":
        template = create_buttons_template(
            text=data["message"],
            actions=data["actions"],
            thumbnail_image_url=data.get("image_url"),
            title=data.get("title")
        )
    elif template_type == "confirm":
        template = create_confirm_template(
            text=data["message"],
            actions=data["actions"]
        )
    elif template_type == "carousel":
        template = create_carousel_template(
            columns=data["columns"]
        )
    elif template_type == "image_carousel":
        template = create_image_carousel_template(
            columns=data["columns"]
        )
    else:
        raise ValueError(f"Unsupported template type: {template_type}")

    return _create_template_message(alt_text, template)