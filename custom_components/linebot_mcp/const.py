"""Constants for the LINE Bot MCP integration."""
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

# 基本常數
DOMAIN = "linebot_mcp"
SERVICE_NOTIFY = "notify"
SERVICE_MANAGER = "service_manager"
SESSION_MANAGER = "session_manager"
SERVER_MANAGER = "server_manager"
STOP_LISTENER = "stop_listener"
SHUTDOWN_EVENT = "shutdown"

# 全域服務名稱
SERVICE_REPLY_MESSAGE = "linebot_reply_message"
SERVICE_PUSH_MESSAGE = "linebot_push_message"
SERVICE_TEXT_CONTENT = "create_text_content"
SERVICE_TEXT_V2_CONTENT = "create_text_v2_content"
SERVICE_IMAGE_CONTENT = "create_image_content"
SERVICE_VIDEO_CONTENT = "create_video_content"
SERVICE_AUDIO_CONTENT = "create_audio_content"
SERVICE_LOCATION_CONTENT = "create_location_content"
SERVICE_STICKER_CONTENT = "create_sticker_content"
SERVICE_FLEX_CONTENT = "create_flex_content"
SERVICE_IMAGEMAP_CONTENT = "create_imagemap_content"
SERVICE_TEMPLATE_CONTENT = "create_template_content"


# 配置常數
CONF_NAME = "name"
CONF_SERVICE_NAME = "service_name"
CONF_TOKEN = "channel_access_token"
CONF_SECRET = "channel_secret"
CONF_WEBHOOK_PATH = "webhook_path"
CONF_AGENT_ID = "agent_id"
CONF_AUTO_REPLY = "auto_reply"

# LINE Bot
LINE_API_CLIENT = "line_api_client"
LINEBOT_INFO_COORDINATOR = "linebot_info_coordinator"
LINEBOT_QUOTA_COORDINATOR = "linebot_quota_coordinator"
DEVICE_MANUFACTURER = "LINE Corporation"
DEVICE_MODEL = "LINE Bot with MCP"

# 事件類型
EVENT_MESSAGE_RECEIVED = f"linebot_{{}}_message_received"
EVENT_POSTBACK = f"linebot_{{}}_postback"

# LINE API 相關常數
LINE_API_BASE_URL = "https://api.line.me"
LINE_API_TIMEOUT = 30

# LINE API 端點
LINE_API_REPLY_ENDPOINT = "/v2/bot/message/reply"
LINE_API_PUSH_ENDPOINT = "/v2/bot/message/push"
LINE_API_MULTICAST_ENDPOINT = "/v2/bot/message/multicast"
LINE_API_BROADCAST_ENDPOINT = "/v2/bot/message/broadcast"
LINE_API_NARROWCAST_ENDPOINT = "/v2/bot/message/narrowcast"
LINE_API_BOT_INFO_ENDPOINT = "/v2/bot/info"
LINE_API_QUOTA_ENDPOINT = "/v2/bot/message/quota"
LINE_API_QUOTA_CONSUMPTION_ENDPOINT = "/v2/bot/message/quota/consumption"
LINE_API_PROFILE_ENDPOINT = "/v2/bot/profile"

# HTTP 標頭常數
LINE_SIGNATURE = "X-Line-Signature"
CONTENT_TYPE_JSON = "application/json"
HTTP_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) HomeAssistant"
)

# 訊息類型列表
MESSAGE_TYPE_LIST = [
    "text",
    "textV2",
    "image",
    "video",
    "audio",
    "file",
    "location",
    "sticker",
    "flex",
    "imagemap",
    "template",
]

# 支援 Quote Token 的訊息類型
QUOTE_TOKEN_SUPPORTED_TYPES = [
    "text",
    "textV2",
    "sticker",
]

# 屬性名稱
ATTR_USER_ID = "user_id"
ATTR_GROUP_ID = "group_id"
ATTR_ROOM_ID = "room_id"
ATTR_MESSAGE_ID = "message_id"
ATTR_MESSAGE_TYPE = "message_type"
ATTR_MESSAGE_TEXT = "message_text"
ATTR_REPLY_TOKEN = "reply_token"
ATTR_TIMESTAMP = "timestamp"
ATTR_SOURCE_TYPE = "source_type"

# MCP 事件
EVENT_MCP_SERVER_STARTED = f"linebot_mcp_server_started"
EVENT_MCP_SERVER_STOPPED = f"linebot_mcp_server_stopped"
EVENT_MCP_SERVER_ERROR = f"linebot_mcp_server_error"
EVENT_MCP_TOOL_CALLED = f"linebot_mcp_tool_called"

# MCP 工具名稱常數
MCP_TOOL_PUSH_MESSAGE = f"push_message"
MCP_TOOL_REPLY_MESSAGE = f"reply_message"
MCP_TOOL_GET_QUOTA_INFO = f"get_quota"

# 錯誤訊息常數
ERROR_INVALID_SIGNATURE = "Invalid signature"
ERROR_INTERNAL_SERVER = "Internal server error"


# 預先定義服務架構
_BASE_MESSAGE_FIELDS = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required("messages"): vol.All(
        cv.ensure_list,[vol.Schema(
            {vol.Required("type"): vol.In(MESSAGE_TYPE_LIST),}
        )]
    ),
    vol.Optional("notification_disabled", default=False): cv.boolean,
}

REPLY_MESSAGE_SCHEMA = vol.Schema({
    **_BASE_MESSAGE_FIELDS,
    vol.Required(ATTR_REPLY_TOKEN): cv.string,
})

PUSH_MESSAGE_SCHEMA = vol.Schema({
    **_BASE_MESSAGE_FIELDS,
    vol.Required("to"): cv.string,
    vol.Optional("retry_key"): cv.string,
})

CREATE_TEXT_SCHEMA = vol.Schema({
    vol.Required("text"): cv.string,
})
CREATE_TEXT_V2_SCHEMA = vol.Schema({
    vol.Required("text"): cv.string,
    vol.Optional("mentions"): vol.All(cv.ensure_list, [dict]),
    vol.Optional("emojis"): vol.All(cv.ensure_list, [dict]),
})
CREATE_IMAGE_SCHEMA = vol.Schema({
    vol.Required("image_url"): cv.string,
    vol.Required("preview_image_url"): cv.string,
})
CREATE_VIDEO_SCHEMA = vol.Schema({
    vol.Required("video_url"): cv.string,
    vol.Required("preview_image_url"): cv.string,
})
CREATE_AUDIO_SCHEMA = vol.Schema({
    vol.Required("audio_url"): cv.string,
    vol.Optional("duration"): cv.positive_int,
})
CREATE_LOCATION_SCHEMA = vol.Schema({
    vol.Optional("title"): cv.string,
    vol.Required("address"): cv.string,
    vol.Required("latitude"): cv.latitude,
    vol.Required("longitude"): cv.longitude,
})
CREATE_STICKER_SCHEMA = vol.Schema({
    vol.Required("package_id"): cv.string,
    vol.Required("sticker_id"): cv.string,
})
CREATE_FLEX_SCHEMA = vol.Schema({
    vol.Required("alt_text"): cv.string,
    vol.Required("contents"): dict,
})
CREATE_IMAGEMAP_SCHEMA = vol.Schema({
    vol.Required("base_url"): cv.string,
    vol.Required("base_size"): dict,
    vol.Required("imagemap_actions"): vol.All(cv.ensure_list, [dict]),
    vol.Optional("video"): dict,
})
CREATE_TEMPLATE_SCHEMA = vol.Schema({
    vol.Required("template_type"): vol.In([
        "buttons", "confirm", "carousel", "image_carousel"
    ]),
    vol.Required("text"): cv.string,
    vol.Required("actions"): vol.All(cv.ensure_list, [dict]),
    vol.Optional("columns"): vol.All(cv.ensure_list, [dict]),
    vol.Optional("thumbnail_image_url"): cv.string,
    vol.Optional("image_aspect_ratio"): cv.string,
    vol.Optional("image_size"): cv.string,
    vol.Optional("image_background_color"): cv.string,
    vol.Optional("title"): cv.string,
    vol.Optional("default_action"): dict,
})

# 服務描述
REPLY_MESSAGE_DESCRIBE = {
    "name": "Reply LINE message",
    "description": "Reply to a LINE message",
    "fields": {
        "name": {
            "description": "LINE Bot ID",
            "example": "@linebot",
            "required": True,
            "selector": {
                "text": ""
            }
        },
        "reply token": {
            "description": "Reply token from LINE webhook event",
            "example": "nHuyWiB7yP5Zw52FIkcQobQuGDXCTA",
            "required": True,
            "selector": {
                "text": ""
            }
        },
        "messages": {
            "description": "Array of message objects to send",
            "example": '[{"type": "text", "text": "Hello World!"}]',
            "required": True,
            "selector": {
                "object": {}
            }
        },
        "notification disabled": {
            "description": "Disable push notification for this message",
            "example": False,
            "required": False,
            "selector": {
                "boolean": False
            }
        },
    },
}
PUSH_MESSAGE_DESCRIBE = {
    "name": "Push LINE message",
    "description": "Send push message to LINE users",
    "fields": {
        "name": {
            "description": "LINE Bot ID",
            "example": "@linebot",
            "required": True,
            "selector": {
                "text": ""
            }
        },
        "to": {
            "description": "User ID, group ID, or room ID to send message to",
            "example": "U1234567890abcdef1234567890abcdef",
            "required": True,
            "selector": {
                "text": ""
            }
        },
        "messages": {
            "description": "Array of message objects to send",
            "example": '[{"type": "text", "text": "Hello World!"}]',
            "required": True,
            "selector": {
                "object": {}
            }
        },
        "retry key": {
            "description": "Retry key for idempotency (UUID format recommended)",
            "example": "550e8400-e29b-41d4-a716-446655440000",
            "required": False,
            "selector": {
                "text": ""
            }
        },
        "notification disabled": {
            "description": "Disable push notification for this message",
            "example": False,
            "required": False,
            "selector": {
                "boolean": False
            }
        },
    },
}