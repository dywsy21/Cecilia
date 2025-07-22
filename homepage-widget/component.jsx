import { useTranslation } from "next-i18next";
import Container from "components/services/widget/container";
import Block from "components/services/widget/block";

import useWidgetAPI from "utils/proxy/use-widget-api";

export default function Component({ service }) {
  const { t } = useTranslation();
  const { widget } = service;
  const { data: statusData, error: statusError } = useWidgetAPI(widget, "status");
  const { data: statsData, error: statsError } = useWidgetAPI(widget, "stats");
  const { data: ollamaData, error: ollamaError } = useWidgetAPI(widget, "ollama");
  const { data: ollamaDirectData, error: ollamaDirectError } = useWidgetAPI(widget, "ollama_direct");

  if (statusError || statsError) {
    return <Container service={service} error={statusError || statsError} />;
  }

  if (!statusData || !statsData) {
    return (
      <Container service={service}>
              <Block label="cecilia.services" />
              <Block label="cecilia.cpu_usage" />
              <Block label="cecilia.gpu_usage" />
              <Block label="cecilia.ollama_status" />
      </Container>
    );
  }

  // Calculate active services
  const activeServices = Object.values(statusData).filter(status => 
    status === "online" || status === "running"
  ).length;

  // Get CPU usage from system monitoring
  const cpuUsage = ollamaData?.system?.cpu_percent || 0;

  // Get GPU usage (first GPU if available)
  const gpuData = ollamaData?.system?.gpu;
  const gpuUsage = gpuData?.available && gpuData.gpus && gpuData.gpus.length > 0 
    ? gpuData.gpus[0].load 
    : null;

  // Get Ollama status - check direct API first, fallback to system monitoring
  let ollamaStatus = "offline";
  if (ollamaDirectData && !ollamaDirectError) {
    ollamaStatus = "online";
  } else if (ollamaData?.ollama?.status) {
    ollamaStatus = ollamaData.ollama.status;
  }

  return (
    <Container service={service}>
            <Block 
              label="cecilia.services" 
              value={t("common.number", { value: activeServices })} 
            />
            <Block 
              label="cecilia.cpu_usage" 
              value={t("common.percent", { value: cpuUsage })} 
            />
            <Block 
              label="cecilia.gpu_usage" 
              value={gpuUsage !== null 
                ? t("common.percent", { value: gpuUsage }) 
                : t("cecilia.no_gpu")
              } 
            />
            <Block 
              label="cecilia.ollama_status" 
              value={t(`cecilia.ollama_${ollamaStatus}`)} 
            />
    </Container>
  );
}
