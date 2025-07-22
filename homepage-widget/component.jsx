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

  if (statusError || statsError || ollamaError) {
    return <Container service={service} error={statusError || statsError || ollamaError} />;
  }

  if (!statusData || !statsData || !ollamaData) {
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

  // Get CPU usage
  const cpuUsage = ollamaData.system?.cpu_percent || 0;

  // Get GPU usage (first GPU if available)
  const gpuData = ollamaData.system?.gpu;
  const gpuUsage = gpuData?.available && gpuData.gpus.length > 0 
    ? gpuData.gpus[0].load 
    : 0;

  // Get Ollama status
  const ollamaStatus = ollamaData.ollama?.status || "unknown";

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
        value={gpuData?.available 
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
