"use strict";

const TOKEN_URL = "https://api-performance.ozon.ru/api/client/token";
const REFRESH_SKEW_MS = 30_000;
const tokenCache = new Map();

function validateTokenResponse(response) {
	if (!response || typeof response.access_token !== "string" || response.access_token.length === 0) {
		throw new Error("Ozon Performance token response does not contain access_token");
	}
	if (response.token_type !== "Bearer") {
		throw new Error("Ozon Performance token response has unsupported token_type");
	}
	if (!Number.isFinite(response.expires_in) || response.expires_in <= 0) {
		throw new Error("Ozon Performance token response has invalid expires_in");
	}
}

async function getAccessToken({ clientId, clientSecret, request, now = Date.now }) {
	const cached = tokenCache.get(clientId);
	const currentTime = now();
	if (cached && cached.expiresAt > currentTime + REFRESH_SKEW_MS) {
		return cached.accessToken;
	}

	const response = await request({
		method: "POST",
		url: TOKEN_URL,
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
		},
		body: {
			grant_type: "client_credentials",
			client_id: clientId,
			client_secret: clientSecret,
		},
		json: true,
	});

	validateTokenResponse(response);
	tokenCache.set(clientId, {
		accessToken: response.access_token,
		expiresAt: currentTime + response.expires_in * 1000,
	});
	return response.access_token;
}

function clearTokenCache() {
	tokenCache.clear();
}

module.exports = { TOKEN_URL, getAccessToken, clearTokenCache };
