"use strict";

const { NodeConnectionTypes } = require("n8n-workflow");
const { getAccessToken } = require("../../lib/token-manager");
const { formatOzonHttpError } = require("../../lib/http-error");

const CAMPAIGNS_URL = "https://api-performance.ozon.ru/api/client/campaign";
const CAMPAIGN_PRODUCTS_URL = (campaignId) =>
	`https://api-performance.ozon.ru/api/client/campaign/${campaignId}/v2/products`;
const CAMPAIGN_STATISTICS_URL = "https://api-performance.ozon.ru/api/client/statistics/json";
const STATISTICS_REPORT_URL = (reportUuid) =>
	`https://api-performance.ozon.ru/api/client/statistics/${reportUuid}`;
const STATISTICS_REPORT_DATA_URL = (reportUuid) =>
	`https://api-performance.ozon.ru/api/client/statistics/report?UUID=${reportUuid}`;

function requirePositiveInteger(value, label) {
	const normalized = String(value).trim();
	if (!/^\d+$/.test(normalized)) {
		throw new Error(`${label} must be a positive integer`);
	}
	return normalized;
}

function requireDate(value, label) {
	const normalized = String(value).trim();
	if (!/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
		throw new Error(`${label} must use YYYY-MM-DD`);
	}
	return normalized;
}

function requireReportUuid(value) {
	const normalized = String(value).trim();
	if (!/^[0-9a-f-]{36}$/i.test(normalized)) {
		throw new Error("Report UUID must be a UUID");
	}
	return normalized;
}
function requireCampaignIds(value) {
	const values = Array.isArray(value) ? value : String(value).split(",");
	const ids = [...new Set(values.map((item) => requirePositiveInteger(item, "Campaign ID")))];
	if (ids.length === 0) throw new Error("At least one Campaign ID is required");
	return ids;
}
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
						{ name: "Generate Campaign Statistics Report", value: "generateCampaignStatisticsReport" },
						{ name: "Generate CPC Daily Statistics Report", value: "generateCpcDailyStatisticsReport" },
						{ name: "Get Campaign Statistics Report", value: "getCampaignStatisticsReport" },
						{ name: "Get Campaign Statistics Data", value: "getCampaignStatisticsData" },
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
					displayOptions: { show: { operation: ["getCampaignProducts", "generateCampaignStatisticsReport"] } },
				},
				{
					displayName: "Campaign IDs",
					name: "campaignIds",
					type: "string",
					default: "",
					required: true,
					displayOptions: { show: { operation: ["generateCpcDailyStatisticsReport"] } },
					description: "Comma-separated IDs from the current CPC/SKU campaign list",
				},
				{
					displayName: "Date From",
					name: "dateFrom",
					type: "string",
					default: "",
					required: true,
					displayOptions: { show: { operation: ["generateCampaignStatisticsReport", "generateCpcDailyStatisticsReport"] } },
					description: "YYYY-MM-DD, inclusive",
				},
				{
					displayName: "Date To",
					name: "dateTo",
					type: "string",
					default: "",
					required: true,
					displayOptions: { show: { operation: ["generateCampaignStatisticsReport", "generateCpcDailyStatisticsReport"] } },
					description: "YYYY-MM-DD, inclusive",
				},
				{
					displayName: "Report UUID",
					name: "reportUuid",
					type: "string",
					default: "",
					required: true,
					displayOptions: { show: { operation: ["getCampaignStatisticsReport", "getCampaignStatisticsData"] } },
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
			const campaignId = requirePositiveInteger(this.getNodeParameter("campaignId", 0), "Campaign ID");
			request.url = CAMPAIGN_PRODUCTS_URL(campaignId);
			request.qs = {
				page: this.getNodeParameter("page", 0),
				pageSize: this.getNodeParameter("pageSize", 0),
			};
		}
		if (operation === "generateCampaignStatisticsReport") {
			const campaignId = requirePositiveInteger(this.getNodeParameter("campaignId", 0), "Campaign ID");
			request.method = "POST";
			request.url = CAMPAIGN_STATISTICS_URL;
			request.headers["Content-Type"] = "application/json";
			request.body = {
				campaigns: [campaignId],
				dateFrom: requireDate(this.getNodeParameter("dateFrom", 0), "Date From"),
				dateTo: requireDate(this.getNodeParameter("dateTo", 0), "Date To"),
				groupBy: "DATE",
			};
		}
		if (operation === "generateCpcDailyStatisticsReport") {
			request.method = "POST";
			request.url = CAMPAIGN_STATISTICS_URL;
			request.headers["Content-Type"] = "application/json";
			request.body = {
				campaigns: requireCampaignIds(this.getNodeParameter("campaignIds", 0)),
				dateFrom: requireDate(this.getNodeParameter("dateFrom", 0), "Date From"),
				dateTo: requireDate(this.getNodeParameter("dateTo", 0), "Date To"),
				groupBy: "DATE",
			};
		}
		if (operation === "getCampaignStatisticsReport") {
			request.url = STATISTICS_REPORT_URL(requireReportUuid(this.getNodeParameter("reportUuid", 0)));
		}
		if (operation === "getCampaignStatisticsData") {
			request.url = STATISTICS_REPORT_DATA_URL(requireReportUuid(this.getNodeParameter("reportUuid", 0)));
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

module.exports = { OzonPerformance, requireCampaignIds, requireDate, requirePositiveInteger, requireReportUuid };
