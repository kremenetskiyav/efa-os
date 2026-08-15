"use strict";

const { NodeConnectionTypes } = require("n8n-workflow");
const { getAccessToken } = require("../../lib/token-manager");

const CAMPAIGNS_URL = "https://api-performance.ozon.ru/api/client/campaign";

class OzonPerformance {
	constructor() {
		this.description = {
			displayName: "Ozon Performance API",
			name: "ozonPerformance",
			group: ["transform"],
			version: 1,
			description: "Read campaign data from Ozon Performance API",
			defaults: { name: "Ozon Performance API" },
			inputs: [NodeConnectionTypes.Main],
			outputs: [NodeConnectionTypes.Main],
			credentials: [{ name: "ozonPerformanceOAuth2Api", required: true }],
			properties: [
				{
					displayName: "Operation",
					name: "operation",
					type: "options",
					options: [{ name: "Get Campaigns", value: "getCampaigns" }],
					default: "getCampaigns",
					noDataExpression: true,
				},
			],
		};
	}

	async execute() {
		const credentials = await this.getCredentials("ozonPerformanceOAuth2Api");
		const accessToken = await getAccessToken({
			clientId: credentials.clientId,
			clientSecret: credentials.clientSecret,
			request: (options) => this.helpers.httpRequest(options),
		});

		const response = await this.helpers.httpRequest({
			method: "GET",
			url: CAMPAIGNS_URL,
			headers: {
				Accept: "application/json",
				Authorization: `Bearer ${accessToken}`,
			},
			json: true,
		});

		return [this.helpers.returnJsonArray(response)];
	}
}

module.exports = { OzonPerformance };
