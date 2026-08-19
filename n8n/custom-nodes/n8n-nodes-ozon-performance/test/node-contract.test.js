"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const credentialSource = fs.readFileSync(path.join(root, "credentials", "OzonPerformanceOAuth2Api.credentials.js"), "utf8");
const telegramCredentialSource = fs.readFileSync(path.join(root, "credentials", "TelegramBotPathApi.credentials.js"), "utf8");
const nodeSource = fs.readFileSync(path.join(root, "nodes", "OzonPerformance", "OzonPerformance.node.js"), "utf8");
const { formatOzonHttpError } = require(path.join(root, "lib", "http-error.js"));
const { TelegramBotPathApi } = require(path.join(root, "credentials", "TelegramBotPathApi.credentials.js"));

test("credential keeps only Client ID and Client Secret in n8n credential storage", () => {
	assert.match(credentialSource, /name: "clientId"/);
	assert.match(credentialSource, /name: "clientSecret"/);
	assert.match(credentialSource, /password: true/);
	assert.doesNotMatch(credentialSource, /access_token/);
});

test("node attaches a Bearer token and exposes only the campaign/statistics read allowlist", () => {
	assert.match(nodeSource, /Authorization: `Bearer \$\{accessToken\}`/);
	assert.match(nodeSource, /method: "GET"/);
	assert.match(nodeSource, /request\.method = "POST"/);
	assert.match(nodeSource, /\/api\/client\/campaign"/);
	assert.match(nodeSource, /\/api\/client\/campaign\/\$\{campaignId\}\/v2\/products/);
	assert.match(nodeSource, /\/api\/client\/statistics\/json/);
	assert.match(nodeSource, /\/api\/client\/statistics\/\$\{reportUuid\}/);
	assert.match(nodeSource, /\/api\/client\/statistics\/report\?UUID=\$\{reportUuid\}/);
	assert.match(nodeSource, /campaigns: \[campaignId\]/);
	assert.match(nodeSource, /campaigns: requireCampaignIds/);
	assert.match(nodeSource, /groupBy: "DATE"/);
	assert.match(nodeSource, /pageSize/);
	assert.doesNotMatch(nodeSource, /method: "PUT"/);
	assert.doesNotMatch(nodeSource, /method: "PATCH"/);
	assert.doesNotMatch(nodeSource, /method: "DELETE"/);
});

test("daily CPC report deduplicates validated campaign IDs", () => {
	assert.match(nodeSource, /new Set\(values\.map/);
	assert.match(nodeSource, /requirePositiveInteger\(item, "Campaign ID"\)/);
});

test("campaign-products request accepts only numeric campaign IDs", () => {
	assert.match(nodeSource, /!\/\^\\d\+\$\/\.test\(normalized\)/);
	assert.match(nodeSource, /\$\{label\} must be a positive integer/);
});

test("HTTP errors expose Ozon status and body without credential material", () => {
	const message = formatOzonHttpError({
		response: {
			status: 400,
			data: {
				code: "INVALID_CAMPAIGN",
				message: "unsupported campaign type",
				access_token: "must-not-leak",
			},
		},
	});
	assert.match(message, /HTTP 400/);
	assert.match(message, /INVALID_CAMPAIGN/);
	assert.match(message, /unsupported campaign type/);
	assert.doesNotMatch(message, /must-not-leak/);
	assert.match(message, /\[REDACTED\]/);
});

test("package declares an n8n credential and node without workflow serialization", () => {
	const packageDefinition = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
	assert.deepEqual(packageDefinition.n8n.credentials, [
		"credentials/OzonPerformanceOAuth2Api.credentials.js",
		"credentials/TelegramBotPathApi.credentials.js",
	]);
	assert.deepEqual(packageDefinition.n8n.nodes, ["nodes/OzonPerformance/OzonPerformance.node.js"]);
});

test("Telegram Bot Path credential stores one encrypted token field and exposes predefined authentication", () => {
	assert.match(telegramCredentialSource, /name: "botToken"/);
	assert.match(telegramCredentialSource, /password: true/);
	assert.match(telegramCredentialSource, /this\.authenticate = async/);
	assert.doesNotMatch(telegramCredentialSource, /baseUrl|host|path.*name:/i);
});

test("Telegram Bot Path authentication fixes POST target and preserves a plain-text body", async () => {
	const credential = new TelegramBotPathApi();
	const body = { chat_id: "123", text: "ACTION_REQUIRED · FBS-UF004B-4118344-V0.1" };
	const authenticated = await credential.authenticate(
		{ botToken: "123456:secret_token" },
		{ method: "GET", url: "https://attacker.invalid/steal", body },
	);

	assert.equal(authenticated.method, "POST");
	assert.equal(authenticated.url, "https://api.telegram.org/bot123456:secret_token/sendMessage");
	assert.deepEqual(authenticated.body, body);
	assert.equal(Object.hasOwn(authenticated.body, "parse_mode"), false);
});

test("Telegram Bot Path authentication rejects invalid tokens and parse_mode", async () => {
	const credential = new TelegramBotPathApi();
	await assert.rejects(
		credential.authenticate({ botToken: "not-a-token" }, { url: "https://api.telegram.org/sendMessage" }),
		/credential is invalid/,
	);
	await assert.rejects(
		credential.authenticate(
			{ botToken: "123456:secret_token" },
			{ url: "https://api.telegram.org/sendMessage", body: { chat_id: "123", text: "x", parse_mode: "HTML" } },
		),
		/forbids parse_mode/,
	);
});
