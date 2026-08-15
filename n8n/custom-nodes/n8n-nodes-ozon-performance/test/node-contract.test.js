"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const credentialSource = fs.readFileSync(path.join(root, "credentials", "OzonPerformanceOAuth2Api.credentials.js"), "utf8");
const nodeSource = fs.readFileSync(path.join(root, "nodes", "OzonPerformance", "OzonPerformance.node.js"), "utf8");

test("credential keeps only Client ID and Client Secret in n8n credential storage", () => {
	assert.match(credentialSource, /name: "clientId"/);
	assert.match(credentialSource, /name: "clientSecret"/);
	assert.match(credentialSource, /password: true/);
	assert.doesNotMatch(credentialSource, /access_token/);
});

test("node attaches a Bearer token and exposes only the read-only campaign endpoint", () => {
	assert.match(nodeSource, /Authorization: `Bearer \$\{accessToken\}`/);
	assert.match(nodeSource, /method: "GET"/);
	assert.match(nodeSource, /\/api\/client\/campaign/);
	assert.doesNotMatch(nodeSource, /method: "POST"/);
	assert.doesNotMatch(nodeSource, /method: "PUT"/);
	assert.doesNotMatch(nodeSource, /method: "PATCH"/);
	assert.doesNotMatch(nodeSource, /method: "DELETE"/);
});

test("package declares an n8n credential and node without workflow serialization", () => {
	const packageDefinition = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
	assert.deepEqual(packageDefinition.n8n.credentials, ["credentials/OzonPerformanceOAuth2Api.credentials.js"]);
	assert.deepEqual(packageDefinition.n8n.nodes, ["nodes/OzonPerformance/OzonPerformance.node.js"]);
});
