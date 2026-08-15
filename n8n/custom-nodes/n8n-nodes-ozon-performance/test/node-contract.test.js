"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const credentialSource = fs.readFileSync(path.join(root, "credentials", "OzonPerformanceOAuth2Api.credentials.js"), "utf8");
const nodeSource = fs.readFileSync(path.join(root, "nodes", "OzonPerformance", "OzonPerformance.node.js"), "utf8");
const { formatOzonHttpError } = require(path.join(root, "lib", "http-error.js"));

test("credential keeps only Client ID and Client Secret in n8n credential storage", () => {
	assert.match(credentialSource, /name: "clientId"/);
	assert.match(credentialSource, /name: "clientSecret"/);
	assert.match(credentialSource, /password: true/);
	assert.doesNotMatch(credentialSource, /access_token/);
});

test("node attaches a Bearer token and exposes only the read-only campaign allowlist", () => {
	assert.match(nodeSource, /Authorization: `Bearer \$\{accessToken\}`/);
	assert.match(nodeSource, /method: "GET"/);
	assert.match(nodeSource, /\/api\/client\/campaign"/);
	assert.match(nodeSource, /\/api\/client\/campaign\/\$\{campaignId\}\/v2\/products/);
	assert.match(nodeSource, /pageSize/);
	assert.doesNotMatch(nodeSource, /method: "POST"/);
	assert.doesNotMatch(nodeSource, /method: "PUT"/);
	assert.doesNotMatch(nodeSource, /method: "PATCH"/);
	assert.doesNotMatch(nodeSource, /method: "DELETE"/);
});

test("campaign-products request accepts only numeric campaign IDs", () => {
	assert.match(nodeSource, /!\/\^\\d\+\$\/\.test\(campaignId\)/);
	assert.match(nodeSource, /Campaign ID must be a positive integer/);
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
	assert.deepEqual(packageDefinition.n8n.credentials, ["credentials/OzonPerformanceOAuth2Api.credentials.js"]);
	assert.deepEqual(packageDefinition.n8n.nodes, ["nodes/OzonPerformance/OzonPerformance.node.js"]);
});
