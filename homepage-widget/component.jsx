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

  // Get Cecilia process CPU usage instead of system-wide CPU
  const ceciliaCpuUsage = ollamaData?.ollama_processes?.cecilia_total_cpu || 0;

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

  // Check if Cecilia is online (for status indicator)
  const isOnline = statusData?.discord_bot === "online" && activeServices > 0;

  if (!isOnline) {
    return (
      <Container service={service}>
        <Block label="widget.status" value={t("cecilia.offline")} />
      </Container>
    );
  }

  return (
    <Container service={service}>
            <Block 
              label="cecilia.services" 
              value={t("common.number", { value: activeServices })} 
            />
            <Block 
              label="cecilia.cpu_usage" 
              value={t("common.percent", { value: ceciliaCpuUsage })} 
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
