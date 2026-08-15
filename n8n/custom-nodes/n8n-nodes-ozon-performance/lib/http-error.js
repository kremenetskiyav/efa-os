"use strict";

const SENSITIVE_ERROR_KEYS = new Set([
	"access_token",
	"authorization",
	"client_id",
	"client_secret",
	"password",
	"token",
]);

function redactErrorBody(value) {
	if (Array.isArray(value)) {
		return value.map(redactErrorBody);
	}
	if (value && typeof value === "object") {
		return Object.fromEntries(
			Object.entries(value).map(([key, entry]) => [
				key,
				SENSITIVE_ERROR_KEYS.has(key.toLowerCase()) ? "[REDACTED]" : redactErrorBody(entry),
			]),
		);
	}
	if (typeof value === "string") {
		return value
			.replace(/(Bearer\s+)[^\s"']+/gi, "$1[REDACTED]")
			.replace(/("?(?:access_token|authorization|client_id|client_secret|password|token)"?\s*[:=]\s*")[^"]*/gi, "$1[REDACTED]")
			.slice(0, 2_000);
	}
	return value;
}

function formatOzonHttpError(error) {
	const status = error?.response?.status;
	const body = redactErrorBody(error?.response?.data);
	const suffix = body === undefined ? "" : `: ${JSON.stringify(body)}`;
	return `Ozon Performance API request failed${status ? ` (HTTP ${status})` : ""}${suffix}`;
}

module.exports = { formatOzonHttpError, redactErrorBody };
