"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { TOKEN_URL, clearTokenCache, getAccessToken } = require("../lib/token-manager");

test.beforeEach(() => clearTokenCache());

test("uses the required JSON client-credentials token contract", async () => {
	let requestOptions;
	const token = await getAccessToken({
		clientId: "test-client",
		clientSecret: "test-secret",
		request: async (options) => {
			requestOptions = options;
			return { access_token: "token", token_type: "Bearer", expires_in: 1800 };
		},
	});

	assert.equal(token, "token");
	assert.equal(requestOptions.method, "POST");
	assert.equal(requestOptions.url, TOKEN_URL);
	assert.deepEqual(requestOptions.headers, {
		Accept: "application/json",
		"Content-Type": "application/json",
	});
	assert.deepEqual(requestOptions.body, {
		grant_type: "client_credentials",
		client_id: "test-client",
		client_secret: "test-secret",
	});
	assert.equal(requestOptions.json, true);
});

test("reuses a valid token and refreshes it after expiry", async () => {
	let calls = 0;
	let currentTime = 1_000;
	const request = async () => {
		calls += 1;
		return { access_token: `token-${calls}`, token_type: "Bearer", expires_in: 60 };
	};
	const options = { clientId: "test-client", clientSecret: "test-secret", request, now: () => currentTime };

	assert.equal(await getAccessToken(options), "token-1");
	currentTime += 20_000;
	assert.equal(await getAccessToken(options), "token-1");
	currentTime += 15_000;
	assert.equal(await getAccessToken(options), "token-2");
	assert.equal(calls, 2);
});

test("rejects an invalid token response", async () => {
	await assert.rejects(
		getAccessToken({
			clientId: "test-client",
			clientSecret: "test-secret",
			request: async () => ({ access_token: "token", token_type: "Bearer" }),
		}),
		/invalid expires_in/,
	);
});
