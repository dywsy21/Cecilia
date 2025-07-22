import genericProxyHandler from "utils/proxy/handlers/generic";

const widget = {
  api: "{url}/{endpoint}",
  proxyHandler: genericProxyHandler,

  mappings: {
    status: {
      endpoint: "status",
    },
    stats: {
      endpoint: "stats",
    },
    ollama: {
      endpoint: "ollama",
    },
  },
};

export default widget;
