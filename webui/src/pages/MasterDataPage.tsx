import { useEffect, useState } from "react";
import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import type { GridColDef } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type { JobRow, MasterDataDashboard, Tone } from "../types/dashboard";

const toneByJobStatus: Record<string, Tone> = {
  成功: "success",
  待确认: "warning",
};

const jobColumns: GridColDef<JobRow>[] = [
  { field: "jobType", headerName: "任务类型", flex: 1.2, minWidth: 150 },
  { field: "target", headerName: "目标对象", flex: 1.6, minWidth: 180 },
  {
    field: "status",
    headerName: "状态",
    minWidth: 110,
    renderCell: (params) => <StatusTag label={String(params.value ?? "")} tone={toneByJobStatus[String(params.value)] ?? "default"} />,
  },
  { field: "startedAt", headerName: "开始时间", minWidth: 150 },
  { field: "finishedAt", headerName: "完成时间", minWidth: 150 },
  { field: "records", headerName: "记录数", minWidth: 90, type: "number" },
  { field: "operator", headerName: "执行人", minWidth: 90 },
];

export function MasterDataPage() {
  const [data, setData] = useState<MasterDataDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getMasterData();
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
        <Typography variant="body1">统一承接花名册、组织列表与权限主数据同步的执行入口和最近结果。</Typography>
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
          gridTemplateColumns: { xs: "1fr", lg: "repeat(3, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(data?.actions ?? []).map((action) => (
          <SectionCard key={action.id} title={action.title} subtitle={action.status}>
            <Typography variant="body2" color="text.secondary">
              {action.description}
            </Typography>
            <Box
              component="pre"
              sx={{
                mt: 2,
                mb: 2,
                px: 1.5,
                py: 1.25,
                fontSize: 12,
                whiteSpace: "pre-wrap",
                border: "1px solid",
                borderColor: "divider",
                backgroundColor: "rgba(15, 23, 42, 0.03)",
              }}
            >
              {action.command}
            </Box>
            <Button variant="contained" disableElevation>
              {action.buttonLabel}
            </Button>
          </SectionCard>
        ))}
      </Box>

      <AppDataGrid
        title="最近主数据任务"
        subtitle="当前为 UI 骨架版本，按钮与表格展示 mock 接口数据。"
        rows={data?.jobs ?? []}
        columns={jobColumns}
        loading={loading}
        rowCount={data?.jobs.length ?? 0}
        initialState={{
          pagination: {
            paginationModel: {
              pageSize: 5,
              page: 0,
            },
          },
        }}
      />
    </Stack>
  );
}
