"use strict";

const { NodeConnectionTypes } = require("n8n-workflow");
const { getAccessToken } = require("../../lib/token-manager");
const { formatOzonHttpError } = require("../../lib/http-error");

const CAMPAIGNS_URL = "https://api-performance.ozon.ru/api/client/campaign";
const CAMPAIGN_PRODUCTS_URL = (campaignId) =>
	`https://api-performance.ozon.ru/api/client/campaign/${campaignId}/v2/products`;
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
					options: [
						{ name: "Get Campaigns", value: "getCampaigns" },
						{ name: "Get Campaign Products", value: "getCampaignProducts" },
					],
					default: "getCampaigns",
					noDataExpression: true,
				},
				{
					displayName: "Campaign ID",
					name: "campaignId",
					type: "string",
					default: "",
					required: true,
					displayOptions: { show: { operation: ["getCampaignProducts"] } },
				},
				{
					displayName: "Page",
					name: "page",
					type: "number",
					default: 1,
					required: true,
					typeOptions: { minValue: 1 },
					displayOptions: { show: { operation: ["getCampaignProducts"] } },
				},
				{
					displayName: "Page Size",
					name: "pageSize",
					type: "number",
					default: 50,
					required: true,
					typeOptions: { minValue: 1, maxValue: 50 },
					displayOptions: { show: { operation: ["getCampaignProducts"] } },
				},
			],
		};
	}

	async execute() {
		const operation = this.getNodeParameter("operation", 0);
		const credentials = await this.getCredentials("ozonPerformanceOAuth2Api");
		const accessToken = await getAccessToken({
			clientId: credentials.clientId,
			clientSecret: credentials.clientSecret,
			request: (options) => this.helpers.httpRequest(options),
		});

		const request = {
			method: "GET",
			url: CAMPAIGNS_URL,
			headers: {
				Accept: "application/json",
				Authorization: `Bearer ${accessToken}`,
			},
			json: true,
		};

		if (operation === "getCampaignProducts") {
			const campaignId = this.getNodeParameter("campaignId", 0).trim();
			if (!/^\d+$/.test(campaignId)) {
				throw new Error("Campaign ID must be a positive integer");
			}
			request.url = CAMPAIGN_PRODUCTS_URL(campaignId);
			request.qs = {
				page: this.getNodeParameter("page", 0),
				pageSize: this.getNodeParameter("pageSize", 0),
			};
		}

		let response;
		try {
			response = await this.helpers.httpRequest(request);
		} catch (error) {
			throw new Error(formatOzonHttpError(error));
		}

		return [this.helpers.returnJsonArray(response)];
	}
}

module.exports = { OzonPerformance };
