[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

[contributors-shield]: https://img.shields.io/github/contributors/kukuxx/HA-LineBot-MCP.svg?style=for-the-badge
[contributors-url]: https://github.com/kukuxx/HA-LineBot-MCP-Card/graphs/contributors

[forks-shield]: https://img.shields.io/github/forks/kukuxx/HA-LineBot-MCP.svg?style=for-the-badge
[forks-url]: https://github.com/kukuxx/HA-LineBot-MCP/network/members

[stars-shield]: https://img.shields.io/github/stars/kukuxx/HA-LineBot-MCP.svg?style=for-the-badge
[stars-url]: https://github.com/kukuxx/HA-LineBot-MCP/stargazers

[issues-shield]: https://img.shields.io/github/issues/kukuxx/HA-LineBot-MCP.svg?style=for-the-badge
[issues-url]: https://github.com/kukuxx/HA-LineBot-MCP/issues

[license-shield]: https://img.shields.io/github/license/kukuxx/HA-LineBot-MCP.svg?style=for-the-badge
[license-url]: https://github.com/kukuxx/HA-LineBot-MCP/blob/main/LICENSE

# LINE Bot MCP Integration for Home Assistant

- [English](/README.md) | [繁體中文](/README-zh-TW.md)

A custom integration for Home Assistant that integrates LINE Bot with the Model Context Protocol (MCP).

## 🌟 Features

- 🤖 **Full LINE Bot Support** — Receive and send various LINE message types.
- 🧠 **MCP Server** — Let AI assistants (Claude, ChatGPT) control your LINE Bot directly.
- 🏠 **Home Assistant Native Integration** — Offers services and sensors.
- 📱 **Rich Message Types** — Text, image, video, audio, location, sticker, Flex, and more.
- 🔄 **Smart Auto Reply** — Integrates conversation agents for intelligent replies.
- 📊 **Real-Time Monitoring** — Track bot status and quota usage.

## 📋 Requirements

- Home Assistant 2025.5.0 or later
- A LINE Developers account

## 🚀 Getting Started

### 1. Install the Integration

**Using HACS (recommended):**

1. Add the custom repository in HACS:  
   [![HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kukuxx&repository=HA-LineBot-MCP&category=Integration)
2. Search for and install **"LINE Bot MCP"**
3. Restart Home Assistant

### 2. Set Up the LINE Bot

1. Go to [LINE Developers Console](https://developers.line.biz/)
2. Create a **Messaging API Channel**
3. Copy your **Channel Access Token** and **Channel Secret**

### 3. Configure the Integration

1. In Home Assistant, add the "LINE Bot MCP" integration
2. Provide your Bot ID, Channel Access Token, and Channel Secret
3. Copy the generated **Webhook URL** into LINE Developers Console

## 🎯 Usage

### Home Assistant Services

```yaml
# Send a text message
service: linebot_mcp.linebot_push_message
data:
  name: "@linebot"
  to: "U1234567890abcdef1234567890abcdef"
  messages:
    - type: "text"
      text: "Hello from Home Assistant!"

# Reply to a message
service: linebot_mcp.linebot_reply_message
data:
  name: "@linebot"
  reply_token: "{{ trigger.event.data.reply_token }}"
  messages:
    - type: "text"
      text: "Got your message!"
````

### Example Automation

```yaml
automation:
  - alias: "LINE Bot Auto Reply"
    trigger:
      platform: event
      event_type: linebot_mcp_@linebot_message_received
    action:
      service: linebot_mcp.linebot_reply_message
      data:
        name: "@linebot"
        reply_token: "{{ trigger.event.data.reply_token }}"
        messages:
          - type: "text"
            text: "Hello! This is the Home Assistant LINE Bot"
```

### MCP Tools

Available tools for AI assistants:

* `send_message` — Send a message
* `reply_message` — Reply to a message
* `get_bot_info` — Retrieve bot information
* `get_quota_info` — Get usage quota

**MCP SSE Endpoint:**

```
http://your-ha-url:8123/api/linebot_mcp/sse
```

## 📱 Supported Message Types

| Type     | Description               | Example                             |
| -------- | ------------------------- | ----------------------------------- |
| text     | Plain text message        | `{"type": "text", "text": "Hello"}` |
| textV2   | Text with mentions/emojis | Includes `mentions` and `emojis`    |
| image    | Image message             | Requires image and preview URLs     |
| video    | Video message             | Requires video and preview URLs     |
| audio    | Audio message             | Requires audio URL and duration     |
| location | Location message          | Includes coordinates and address    |
| sticker  | Sticker message           | Requires package ID and sticker ID  |
| flex     | Flex message              | Custom layout design                |
| imagemap | Imagemap message          | Image map with actions              |
| template | Template message          | Buttons and text layout             |

## 🔧 Advanced Settings

### Options

* **Agent ID** — Specify which conversation agent to use (default: `conversation.google_generative_ai`)
* **Auto Reply** — Enable or disable automatic responses

### Events

This integration emits the following events:

* `linebot_mcp_{bot_name}_message_received` — When a message is received
* `linebot_mcp_{bot_name}_postback` — When a postback is received

Events include the user ID, message content, reply token, and other metadata.

## 🐛 Troubleshooting

### Common Issues

**Webhook not receiving messages:**

* Check the webhook URL configuration
* Ensure Home Assistant is accessible from the internet
* Verify the Channel Secret

**MCP connection failed:**

* Check your network connection
* Check Home Assistant logs

**Failed to send messages:**

* Verify Channel Access Token
* Ensure message format is correct
* Confirm the recipient's user ID

### Debug Logging

```yaml
logger:
  default: warning
  logs:
    linebot_mcp: debug
```

## 📚 Resources
- [LINE Messaging API Documentation](https://developers.line.biz/en/docs/messaging-api/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)

## 🙏 Acknowledgements

The MCP server part was developed with reference to [homeassistant-mcp-server](https://github.com/home-assistant/core/tree/dev/homeassistant/components/mcp_server).
