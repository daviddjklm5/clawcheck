import { useEffect, useState } from "react";
import { Alert, Box, Stack, Typography } from "@mui/material";

import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { dashboardApi } from "../services/api";
import type { RuntimeSettingsSummary } from "../types/dashboard";

export function RuntimeSettingsPage() {
  const [data, setData] = useState<RuntimeSettingsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getRuntimeSettings();
        if (active) {
          setData(response);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "加载失败");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          常规配置页只展示运行摘要与路径信息，不在页面暴露真实口令或敏感安全凭据。
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(data?.stats ?? []).map((item) => (
          <StatCard key={item.label} item={item} />
        ))}
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        <SectionCard
          title="运行时配置"
          subtitle={loading ? "读取中..." : `${data?.environmentLabel ?? ""} / ${data?.configFile ?? ""}`}
        >
          <KeyValueList items={data?.runtime ?? []} />
        </SectionCard>

        <SectionCard title="浏览器设置" subtitle="与当前 Playwright 配置保持一致">
          <KeyValueList items={data?.browser ?? []} />
        </SectionCard>

        <SectionCard title="数据库摘要" subtitle="仅展示 host / port / dbname / schema 等必要信息">
          <KeyValueList items={data?.database ?? []} />
        </SectionCard>

        <SectionCard title="路径与安全说明" subtitle="敏感信息管理遵循 AGENTS.md 约束">
          <KeyValueList items={data?.paths ?? []} />
          <Typography variant="subtitle2" sx={{ mt: 2.5 }}>
            安全说明
          </Typography>
          <Stack spacing={1} sx={{ mt: 1.5 }}>
            {(data?.securityNotes ?? []).map((item) => (
              <Typography key={item} variant="body2" color="text.secondary">
                • {item}
              </Typography>
            ))}
          </Stack>
        </SectionCard>
      </Box>
    </Stack>
  );
}
