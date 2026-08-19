"use strict";

const TELEGRAM_SEND_MESSAGE_URL_PREFIX = "https://api.telegram.org/bot";
const TELEGRAM_SEND_MESSAGE_PATH = "/sendMessage";
const TELEGRAM_BOT_TOKEN_PATTERN = /^\d+:[A-Za-z0-9_-]+$/;

class TelegramBotPathApi {
	constructor() {
		this.name = "telegramBotPathApi";
		this.displayName = "Telegram Bot Path API";
		this.documentationUrl = "telegram";
		this.properties = [
			{
				displayName: "Bot Token",
				name: "botToken",
				type: "string",
				typeOptions: { password: true },
				default: "",
				required: true,
			},
		];
		this.authenticate = async (credentials, requestOptions) => {
			const botToken = String(credentials.botToken ?? "").trim();
			if (!TELEGRAM_BOT_TOKEN_PATTERN.test(botToken)) {
				throw new Error("Telegram Bot Path API credential is invalid");
			}
			if (requestOptions.body && typeof requestOptions.body === "object" && "parse_mode" in requestOptions.body) {
				throw new Error("Telegram Bot Path API plain-text transport forbids parse_mode");
			}

			return {
				...requestOptions,
				method: "POST",
				url: `${TELEGRAM_SEND_MESSAGE_URL_PREFIX}${botToken}${TELEGRAM_SEND_MESSAGE_PATH}`,
			};
		};
	}
}

module.exports = { TelegramBotPathApi };
