import { useDeferredValue, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import type { GridColDef } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type {
  MasterDataDashboard,
  MasterDataPermissionLevelCount,
  MasterDataRunSummary,
  Tone,
} from "../types/dashboard";

const taskLabelByType: Record<string, string> = {
  roster: "在职花名册",
  orglist: "组织列表",
  rolecatalog: "权限主数据",
};

const taskStatusTone: Record<string, Tone> = {
  queued: "info",
  running: "warning",
  succeeded: "success",
  failed: "danger",
};

function formatTaskStatusLabel(value: string): string {
  return (
    {
      queued: "排队中",
      running: "运行中",
      succeeded: "已完成",
      failed: "执行失败",
    }[value] ?? value
  );
}

function isMasterDataDashboard(value: unknown): value is MasterDataDashboard {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<MasterDataDashboard>;
  return Array.isArray(candidate.stats) && Array.isArray(candidate.actions) && Array.isArray(candidate.recentRuns);
}

const runColumns: GridColDef<MasterDataRunSummary>[] = [
  {
    field: "taskType",
    headerName: "任务类型",
    minWidth: 130,
    renderCell: (params) => taskLabelByType[String(params.value)] ?? String(params.value ?? ""),
  },
  {
    field: "status",
    headerName: "任务状态",
    minWidth: 120,
    renderCell: (params) => (
      <StatusTag
        label={formatTaskStatusLabel(String(params.value ?? ""))}
        tone={taskStatusTone[String(params.value)] ?? "default"}
      />
    ),
  },
  { field: "requestedAt", headerName: "触发时间", minWidth: 170 },
  { field: "finishedAt", headerName: "完成时间", minWidth: 170 },
  { field: "importBatchNo", headerName: "导入批次", minWidth: 170, flex: 1 },
  { field: "sourceFileName", headerName: "来源文件", minWidth: 220, flex: 1.2 },
  { field: "insertedCount", headerName: "写入行数", minWidth: 100, type: "number" },
  { field: "totalRows", headerName: "表总行数", minWidth: 100, type: "number" },
];

export function MasterDataPage() {
  const [data, setData] = useState<MasterDataDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const [taskType, setTaskType] = useState<"roster" | "orglist" | "rolecatalog">("roster");
  const [headed, setHeaded] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [inputFile, setInputFile] = useState("");
  const [skipExport, setSkipExport] = useState(false);
  const [skipImport, setSkipImport] = useState(false);
  const [queryTimeoutSeconds, setQueryTimeoutSeconds] = useState("60");
  const [downloadTimeoutMinutes, setDownloadTimeoutMinutes] = useState("15");
  const [scheme, setScheme] = useState("在职花名册基础版");
  const [employmentType, setEmploymentType] = useState("全职任职");
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runNotice, setRunNotice] = useState<string | null>(null);
  const [runQueryText, setRunQueryText] = useState("");
  const deferredRunQueryText = useDeferredValue(runQueryText);

  const currentTask = data?.currentTask ?? null;
  const currentTaskRunning = currentTask?.status === "queued" || currentTask?.status === "running";
  const roleCatalogTask = taskType === "rolecatalog";
  const rosterTask = taskType === "roster";
  const normalizedRunQueryText = deferredRunQueryText.trim().toLowerCase();

  const filteredRuns = (data?.recentRuns ?? []).filter((item) => {
    if (!normalizedRunQueryText) {
      return true;
    }
    return (
      `${item.taskId} ${item.taskType} ${item.status} ${item.message} ${item.importBatchNo} ${item.sourceFileName}`
        .toLowerCase()
        .includes(normalizedRunQueryText)
    );
  });

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getMasterData()) as unknown;
        if (!isMasterDataDashboard(response)) {
          throw new Error("同步主数据接口返回结构不正确，请重启 FastAPI 并确认已切到真实工作台接口。");
        }
        if (active) {
          setData(response);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setData(null);
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
  }, [refreshVersion]);

  useEffect(() => {
    if (!currentTaskRunning) {
      return;
    }
    const timer = window.setInterval(() => {
      setRefreshVersion((currentValue) => currentValue + 1);
    }, 4000);
    return () => {
      window.clearInterval(timer);
    };
  }, [currentTaskRunning]);

  async function triggerTask() {
    try {
      setRunSubmitting(true);
      setRunError(null);
      setRunNotice(null);
      const result = await dashboardApi.startMasterDataTask({
        taskType,
        headed,
        dryRun: roleCatalogTask ? false : dryRun,
        inputFile: inputFile.trim(),
        skipExport: roleCatalogTask ? false : skipExport,
        skipImport: roleCatalogTask ? false : skipImport,
        queryTimeoutSeconds: Number.parseInt(queryTimeoutSeconds, 10) || 0,
        downloadTimeoutMinutes: Number.parseInt(downloadTimeoutMinutes, 10) || 0,
        scheme: rosterTask ? scheme.trim() : "",
        employmentType: rosterTask ? employmentType.trim() : "",
        forceRefresh: true,
      });
      setRunNotice(result.message || "主数据任务已提交。");
      setRefreshVersion((currentValue) => currentValue + 1);
    } catch (submitError) {
      setRunError(submitError instanceof Error ? submitError.message : "启动主数据任务失败");
    } finally {
      setRunSubmitting(false);
    }
  }

  function renderPermissionLevelCounts(rows: MasterDataPermissionLevelCount[] | undefined) {
    if (!rows || rows.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary">
          当前任务未返回权限级别分布。
        </Typography>
      );
    }
    return (
      <Stack spacing={0.5}>
        {rows.slice(0, 8).map((row) => (
          <Typography key={row.permissionLevel} variant="caption" color="text.secondary">
            {row.permissionLevel}：{row.count}
          </Typography>
        ))}
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          当前页面已切换为真实主数据工作台：前端直接调用 `/api/jobs/master-data*`，后端执行真实 `run.py` 任务并输出任务摘要。
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {runError ? <Alert severity="error">{runError}</Alert> : null}
      {runNotice ? <Alert severity="success">{runNotice}</Alert> : null}

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

      <Paper
        elevation={0}
        sx={{
          p: 2,
          border: "1px solid",
          borderColor: "divider",
          backgroundColor: "rgba(255,255,255,0.84)",
        }}
      >
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", xl: "row" }} spacing={1.5} alignItems={{ xl: "center" }}>
            <TextField
              select
              label="任务类型"
              size="small"
              value={taskType}
              onChange={(event) => setTaskType(event.target.value as "roster" | "orglist" | "rolecatalog")}
              sx={{ minWidth: { xs: "100%", sm: 180 } }}
            >
              <MenuItem value="roster">同步在职花名册</MenuItem>
              <MenuItem value="orglist">同步组织列表</MenuItem>
              <MenuItem value="rolecatalog">刷新权限主数据</MenuItem>
            </TextField>
            <FormControlLabel
              control={<Switch checked={headed} onChange={(event) => setHeaded(event.target.checked)} />}
              label="可见浏览器"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={dryRun}
                  onChange={(event) => setDryRun(event.target.checked)}
                  disabled={roleCatalogTask}
                />
              }
              label="仅验证不落库"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={skipExport}
                  onChange={(event) => setSkipExport(event.target.checked)}
                  disabled={roleCatalogTask}
                />
              }
              label="仅查询不导出"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={skipImport}
                  onChange={(event) => setSkipImport(event.target.checked)}
                  disabled={roleCatalogTask}
                />
              }
              label="仅导出不入库"
              sx={{ ml: 0 }}
            />
          </Stack>

          <Stack direction={{ xs: "column", xl: "row" }} spacing={1.5}>
            <TextField
              label="输入文件路径"
              size="small"
              fullWidth
              value={inputFile}
              onChange={(event) => setInputFile(event.target.value)}
              placeholder="可选：服务端本机可访问路径"
            />
            <TextField
              label="查询超时秒数"
              size="small"
              value={queryTimeoutSeconds}
              onChange={(event) => setQueryTimeoutSeconds(event.target.value)}
              sx={{ width: { xs: "100%", xl: 160 } }}
              disabled={roleCatalogTask}
            />
            <TextField
              label="下载超时分钟"
              size="small"
              value={downloadTimeoutMinutes}
              onChange={(event) => setDownloadTimeoutMinutes(event.target.value)}
              sx={{ width: { xs: "100%", xl: 160 } }}
              disabled={roleCatalogTask}
            />
            <TextField
              label="花名册方案"
              size="small"
              value={scheme}
              onChange={(event) => setScheme(event.target.value)}
              sx={{ width: { xs: "100%", xl: 220 } }}
              disabled={!rosterTask}
            />
            <TextField
              label="任职类型"
              size="small"
              value={employmentType}
              onChange={(event) => setEmploymentType(event.target.value)}
              sx={{ width: { xs: "100%", xl: 220 } }}
              disabled={!rosterTask}
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                disableElevation
                onClick={() => void triggerTask()}
                disabled={runSubmitting || currentTaskRunning}
              >
                {runSubmitting ? "提交中..." : currentTaskRunning ? "执行中..." : "启动任务"}
              </Button>
              <Button variant="outlined" onClick={() => setRefreshVersion((currentValue) => currentValue + 1)}>
                刷新
              </Button>
            </Stack>
          </Stack>

          <Typography variant="caption" color="text.secondary">
            `inputFile` 为服务端本机路径，不是浏览器上传文件；运行中每 4 秒自动轮询状态。
          </Typography>
        </Stack>
      </Paper>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.2fr) minmax(320px, 0.8fr)" },
          gap: 2,
        }}
      >
        <SectionCard title="当前主数据任务" subtitle="运行中任务会持续刷新状态">
          {currentTask ? (
            <Stack spacing={1}>
              <Stack direction="row" spacing={1} alignItems="center">
                <StatusTag
                  label={formatTaskStatusLabel(currentTask.status)}
                  tone={taskStatusTone[currentTask.status] ?? "default"}
                />
                <Typography variant="caption" color="text.secondary">
                  {currentTask.taskId}
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                任务类型：{taskLabelByType[currentTask.taskType] ?? currentTask.taskType}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {currentTask.message || "当前任务暂无额外描述。"}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                开始 {currentTask.startedAt || currentTask.requestedAt}，导入批次 {currentTask.importBatchNo || "-"}，写入{" "}
                {currentTask.insertedCount} 行。
              </Typography>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              当前没有运行中的主数据任务。
            </Typography>
          )}
        </SectionCard>

        <SectionCard title="最近一次任务" subtitle="用于快速确认任务结果与排障路径">
          {data?.recentRuns?.[0] ? (
            <Stack spacing={1}>
              <Stack direction="row" spacing={1} alignItems="center">
                <StatusTag
                  label={formatTaskStatusLabel(data.recentRuns[0].status)}
                  tone={taskStatusTone[data.recentRuns[0].status] ?? "default"}
                />
                <Typography variant="caption" color="text.secondary">
                  {taskLabelByType[data.recentRuns[0].taskType] ?? data.recentRuns[0].taskType}
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {data.recentRuns[0].message || "最近任务已结束。"}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                导入批次：{data.recentRuns[0].importBatchNo || "-"}，来源文件：{data.recentRuns[0].sourceFileName || "-"}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                日志：{data.recentRuns[0].logFile || "-"}；摘要：{data.recentRuns[0].summaryFile || "-"}
              </Typography>
              {data.recentRuns[0].taskType === "rolecatalog"
                ? renderPermissionLevelCounts(data.recentRuns[0].countsByPermissionLevel)
                : null}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              当前还没有可展示的主数据任务摘要文件。
            </Typography>
          )}
        </SectionCard>
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
            <Button
              sx={{ mt: 2 }}
              variant="outlined"
              onClick={() => setTaskType((action.taskType as "roster" | "orglist" | "rolecatalog") ?? "roster")}
            >
              {action.buttonLabel}
            </Button>
          </SectionCard>
        ))}
      </Box>

      <AppDataGrid<MasterDataRunSummary>
        title="最近主数据任务"
        subtitle="真实任务摘要来自 logs 目录中的 master_data_summary_*.json。"
        rows={filteredRuns}
        columns={runColumns}
        loading={loading}
        rowCount={filteredRuns.length}
        minHeight={380}
        pageSizeOptions={[5, 10, 20]}
        initialState={{
          sorting: {
            sortModel: [{ field: "requestedAt", sort: "desc" }],
          },
          pagination: {
            paginationModel: {
              pageSize: 5,
              page: 0,
            },
          },
        }}
        actions={
          <TextField
            size="small"
            label="筛选任务"
            placeholder="任务号 / 类型 / 状态 / 批次 / 文件"
            value={runQueryText}
            onChange={(event) => setRunQueryText(event.target.value)}
            sx={{ width: { xs: "100%", sm: 320 } }}
          />
        }
      />
    </Stack>
  );
}
