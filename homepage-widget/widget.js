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
    // Direct Ollama API access
    ollama_direct: {
      endpoint: "api/tags",
      url: "http://localhost:11434"
    },
  },
};

export default widget;
