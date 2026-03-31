import { useEffect, useState } from "react";
import { Alert, Button, Paper, Stack, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";

import { SectionCard } from "../components/SectionCard";
import { dashboardApi } from "../services/api";
import type { ReportCenterCatalog } from "../types/dashboard";

export function ReportCenterPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<ReportCenterCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getReportCenterCatalog();
        if (active) {
          setCatalog(response);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setCatalog(null);
          setError(loadError instanceof Error ? loadError.message : "加载报表目录失败");
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
      <Typography variant="body1">
        报表中心统一承接专题分析型报表。当前已上线 `服务站分析` 模块，第一张正式报表为 `服务站人员流动表`。
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}

      {(catalog?.modules ?? []).map((module) => (
        <SectionCard
          key={module.id}
          title={module.label}
          subtitle={module.description}
          action={
            <Button
              variant="outlined"
              size="small"
              onClick={() => navigate("/report-center/service-station-flow")}
            >
              打开首个报表
            </Button>
          }
        >
          <Stack spacing={1.5}>
            {module.reports
              .slice()
              .sort((left, right) => left.order - right.order)
              .map((report) => (
                <Paper
                  key={report.id}
                  elevation={0}
                  sx={{
                    p: 2,
                    border: "1px solid",
                    borderColor: "divider",
                    backgroundColor: "rgba(248,250,252,0.78)",
                  }}
                >
                  <Stack
                    direction={{ xs: "column", md: "row" }}
                    spacing={1.5}
                    justifyContent="space-between"
                    alignItems={{ md: "center" }}
                  >
                    <Stack spacing={0.5}>
                      <Typography variant="subtitle1" fontWeight={600}>
                        {report.order}. {report.label}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {report.description}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        路由：{report.path}
                      </Typography>
                    </Stack>
                    <Button variant="contained" disableElevation onClick={() => navigate(report.path)}>
                      进入报表
                    </Button>
                  </Stack>
                </Paper>
              ))}

            {!loading && (module.reports?.length ?? 0) === 0 ? (
              <Typography variant="body2" color="text.secondary">
                当前模块尚未配置报表。
              </Typography>
            ) : null}
          </Stack>
        </SectionCard>
      ))}
    </Stack>
  );
}
