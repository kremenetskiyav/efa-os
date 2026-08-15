"use strict";

class OzonPerformanceOAuth2Api {
	constructor() {
		this.name = "ozonPerformanceOAuth2Api";
		this.displayName = "Ozon Performance OAuth2";
		this.documentationUrl = "https://docs.ozon.ru/api/performance/";
		this.properties = [
			{
				displayName: "Client ID",
				name: "clientId",
				type: "string",
				default: "",
				required: true,
			},
			{
				displayName: "Client Secret",
				name: "clientSecret",
				type: "string",
				typeOptions: { password: true },
				default: "",
				required: true,
			},
		];
	}
}

module.exports = { OzonPerformanceOAuth2Api };
