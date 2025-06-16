"""Config flow for LINE Bot integration."""
from __future__ import annotations

import re
import secrets
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant.core import callback
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    BooleanSelector,
    BooleanSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_SERVICE_NAME,
    CONF_TOKEN,
    CONF_SECRET,
    CONF_WEBHOOK_PATH,
    CONF_AUTO_REPLY,
    CONF_AGENT_ID,   
)


TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))


class LINEBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LINE Bot Webhook."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LINEBotOptionsFlowHandler()

    @property
    def current_entry_names(self) -> set[str]:
        """取得當前所有條目的名稱"""
        return {
            entry.data.get(CONF_NAME) 
            for entry in self._async_current_entries()
        }

    @property
    def current_tokens(self) -> set[str]:
        """取得當前所有條目的 Token"""
        return {
            entry.data.get(CONF_TOKEN) 
            for entry in self._async_current_entries()
        }
        
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # 驗證輸入
            errors = self._validate_input(user_input)
            
            if not errors:
                # 檢查是否已經存在相同的設定
                await self.async_set_unique_id(user_input[CONF_TOKEN])
                self._abort_if_unique_id_configured()
                # 設定 webhook 路徑
                webhook_secret = secrets.token_urlsafe(32)
                user_input[CONF_WEBHOOK_PATH] = f"/linebot/webhook/{webhook_secret}"
                # 設定服務名稱
                service_name = user_input[CONF_NAME].strip().replace("@", "")
                user_input[CONF_SERVICE_NAME] = service_name
                
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )
                
        STEP_USER_DATA_SCHEMA = vol.Schema({
            vol.Required(CONF_NAME, default="@linebot"): TEXT_SELECTOR,
            vol.Required(CONF_TOKEN): TEXT_SELECTOR,
            vol.Required(CONF_SECRET): TEXT_SELECTOR,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _validate_input(self, user_input: Dict[str, Any]) -> Dict[str, str]:
        errors = {}
        
        # 驗證 LINE Bot 名稱
        if not user_input.get(CONF_NAME):
            errors[CONF_NAME] = "required"
        elif user_input[CONF_NAME] in self.current_entry_names:
            errors[CONF_NAME] = "invalid_name"
        elif not re.fullmatch(r"@[a-z0-9]+", user_input[CONF_NAME]):
            errors[CONF_NAME] = "invalid_name"

        
        # 驗證 Channel Access Token
        if not user_input.get(CONF_TOKEN):
            errors[CONF_TOKEN] = "required"
        elif len(user_input[CONF_TOKEN]) < 50:
            errors[CONF_TOKEN] = "invalid_token"

        # 驗證 Channel Secret
        if not user_input.get(CONF_SECRET):
            errors[CONF_SECRET] = "required"
        elif len(user_input[CONF_SECRET]) != 32:
            errors[CONF_SECRET] = "invalid_secret"

        return errors


class LINEBotOptionsFlowHandler(config_entries.OptionsFlow):
    """處理選項變更."""

    BOOLEAN_SELECTOR = BooleanSelector(BooleanSelectorConfig())

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ):
        """管理選項."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        old_options = self.config_entry.options

        options_schema = vol.Schema({
            vol.Optional(CONF_AGENT_ID, 
                default=old_options.get(
                    CONF_AGENT_ID, 
                    "conversation.google_generative_ai")
            ): TEXT_SELECTOR,
            vol.Optional(CONF_AUTO_REPLY, 
            default=old_options.get(CONF_AUTO_REPLY, False)): self.BOOLEAN_SELECTOR,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )