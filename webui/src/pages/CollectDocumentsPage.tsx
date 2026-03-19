import { useDeferredValue, useEffect, useState } from "react";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import {
  Alert,
  Box,
  Button,
  Drawer,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import type { GridColDef, GridRenderCellParams } from "@mui/x-data-grid";
import { useSearchParams } from "react-router-dom";

import { AppDataGrid } from "../components/AppDataGrid";
import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type {
  CollectApprovalRow,
  CollectDetail,
  CollectDocumentRow,
  CollectOrgScopeRow,
  CollectRoleRow,
  CollectRunSummary,
  CollectWorkbench,
  TableStatusRow,
  Tone,
} from "../types/dashboard";

type DetailTab = "summary" | "tableStatus" | "roles" | "orgScopes" | "approvals";

const MAIN_GRID_PAGE_SIZE = 10;
const DETAIL_GRID_PAGE_SIZE = 10;
const MAIN_GRID_HEIGHT = 760;
const DETAIL_GRID_HEIGHT = 760;

const detailTabs: Array<{ value: DetailTab; label: string }> = [
  { value: "summary", label: "单据概览" },
  { value: "tableStatus", label: "落库情况" },
  { value: "roles", label: "申请角色" },
  { value: "orgScopes", label: "目标组织" },
  { value: "approvals", label: "审批记录" },
];

const collectStatusTone: Record<string, Tone> = {
  已落库: "success",
  待补采: "warning",
  审批为空: "info",
};

const tableStatusTone: Record<string, Tone> = {
  已落库: "success",
  待补采: "warning",
  审批为空: "info",
};

const taskStatusTone: Record<string, Tone> = {
  queued: "info",
  running: "warning",
  succeeded: "success",
  partial: "warning",
  failed: "danger",
};

function isDetailTab(value: string | null): value is DetailTab {
  return detailTabs.some((item) => item.value === value);
}

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function formatTaskStatusLabel(value: string): string {
  return (
    {
      queued: "排队中",
      running: "运行中",
      succeeded: "已完成",
      partial: "部分失败",
      failed: "执行失败",
    }[value] ?? value
  );
}

function isCollectWorkbenchResponse(value: unknown): value is CollectWorkbench {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<CollectWorkbench>;
  return Array.isArray(candidate.stats) && Array.isArray(candidate.documents) && Array.isArray(candidate.recentRuns);
}

function isCollectDetailResponse(value: unknown): value is CollectDetail {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<CollectDetail>;
  return (
    typeof candidate.documentNo === "string" &&
    Array.isArray(candidate.overviewFields) &&
    Array.isArray(candidate.tableStatus) &&
    Array.isArray(candidate.roles) &&
    Array.isArray(candidate.orgScopes) &&
    Array.isArray(candidate.approvals) &&
    Array.isArray(candidate.notes)
  );
}

const tableColumns: GridColDef<TableStatusRow>[] = [
  { field: "tableName", headerName: "目标表", minWidth: 180, flex: 1.1 },
  {
    field: "status",
    headerName: "状态",
    minWidth: 120,
    renderCell: (params) => (
      <StatusTag label={String(params.value ?? "")} tone={tableStatusTone[String(params.value)] ?? "default"} />
    ),
  },
  { field: "records", headerName: "记录数", minWidth: 90, type: "number" },
  { field: "updatedAt", headerName: "更新时间", minWidth: 170 },
  { field: "remark", headerName: "备注", minWidth: 260, flex: 1.4 },
];

const roleColumns: GridColDef<CollectRoleRow>[] = [
  { field: "lineNo", headerName: "明细行号", minWidth: 100 },
  { field: "applyType", headerName: "申请类型", minWidth: 110 },
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 220, flex: 1.2 },
  { field: "permissionLevel", headerName: "权限级别", minWidth: 120 },
  { field: "orgScopeCount", headerName: "组织范围数", minWidth: 110, type: "number" },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const approvalColumns: GridColDef<CollectApprovalRow>[] = [
  { field: "nodeName", headerName: "节点", minWidth: 150 },
  { field: "approver", headerName: "审批人", minWidth: 160 },
  { field: "action", headerName: "动作", minWidth: 110 },
  { field: "finishedAt", headerName: "完成时间", minWidth: 170 },
  { field: "comment", headerName: "审批意见", minWidth: 280, flex: 1.3 },
];

const orgScopeColumns: GridColDef<CollectOrgScopeRow>[] = [
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 220, flex: 1.1 },
  { field: "organizationCode", headerName: "组织编码", minWidth: 120 },
  { field: "organizationName", headerName: "组织名称", minWidth: 180, flex: 1 },
  { field: "orgUnitName", headerName: "组织单位", minWidth: 160 },
  { field: "physicalLevel", headerName: "物理层级", minWidth: 110 },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const runColumns: GridColDef<CollectRunSummary>[] = [
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
  { field: "requestedDocumentNo", headerName: "指定单据", minWidth: 180, flex: 1 },
  { field: "requestedLimit", headerName: "上限", minWidth: 80, type: "number" },
  { field: "successCount", headerName: "成功", minWidth: 80, type: "number" },
  { field: "skippedCount", headerName: "跳过", minWidth: 80, type: "number" },
  { field: "failedCount", headerName: "失败", minWidth: 80, type: "number" },
  { field: "startedAt", headerName: "开始时间", minWidth: 170 },
  { field: "finishedAt", headerName: "结束时间", minWidth: 170 },
];

export function CollectDocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [workbench, setWorkbench] = useState<CollectWorkbench | null>(null);
  const [detail, setDetail] = useState<CollectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [runDocumentNo, setRunDocumentNo] = useState("");
  const [runLimit, setRunLimit] = useState("100");
  const [runDryRun, setRunDryRun] = useState(false);
  const [runAutoAudit, setRunAutoAudit] = useState(true);
  const [runForceRecollect, setRunForceRecollect] = useState(false);
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runNotice, setRunNotice] = useState<string | null>(null);
  const [auditSubmitting, setAuditSubmitting] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditNotice, setAuditNotice] = useState<string | null>(null);

  const queryText = searchParams.get("q") ?? "";
  const deferredQueryText = useDeferredValue(queryText);
  const collectStatusFilter = searchParams.get("collectStatus") ?? "all";
  const selectedDocumentNo = searchParams.get("documentNo") ?? "";
  const detailDrawerOpen = selectedDocumentNo !== "";
  const activeTab: DetailTab = isDetailTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as DetailTab)
    : "summary";

  const currentTask = workbench?.currentTask ?? null;
  const currentTaskRunning = currentTask?.status === "queued" || currentTask?.status === "running";
  const workbenchDocuments = workbench?.documents ?? [];
  const selectedDocumentRow =
    workbenchDocuments.find((item) => item.documentNo === selectedDocumentNo) ?? null;

  const normalizedQueryText = normalizeText(deferredQueryText);
  const collectStatusOptions = Array.from(
    new Set(workbenchDocuments.map((item) => item.collectStatus).filter((item) => Boolean(item))),
  );
  const filteredDocuments = workbenchDocuments.filter((item) => {
    if (collectStatusFilter !== "all" && item.collectStatus !== collectStatusFilter) {
      return false;
    }
    if (!normalizedQueryText) {
      return true;
    }
    return normalizeText(
      [
        item.documentNo,
        item.applicantName,
        item.applicantNo,
        item.permissionTarget,
        item.departmentName,
        item.documentStatus,
        item.collectStatus,
      ].join(" "),
    ).includes(normalizedQueryText);
  });
  const hasActiveFilters = Boolean(queryText || collectStatusFilter !== "all");

  function updateSearchParams(
    updates: Record<string, string | null>,
    options: { replace?: boolean } = {},
  ) {
    const nextParams = new URLSearchParams(searchParams);

    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "" || value === "all") {
        nextParams.delete(key);
      } else {
        nextParams.set(key, value);
      }
    }

    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: options.replace ?? true });
    }
  }

  function openDetail(documentNo: string) {
    updateSearchParams(
      {
        documentNo,
        tab: "summary",
      },
      { replace: false },
    );
  }

  function closeDetail() {
    updateSearchParams(
      {
        documentNo: null,
        tab: null,
      },
      { replace: false },
    );
  }

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getCollectWorkbench()) as unknown;
        if (!isCollectWorkbenchResponse(response)) {
          throw new Error(
            "采集工作台接口返回的不是 202 方案正式结构。请重启 FastAPI 服务，确保 `/documents/collect-workbench` 已切换到真实 PostgreSQL / collect runner 接口。",
          );
        }
        if (!active) {
          return;
        }

        setWorkbench(response);
        setError(null);
      } catch (loadError) {
        if (active) {
          setWorkbench(null);
          setError(loadError instanceof Error ? loadError.message : "加载采集单据页失败");
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
    if (!selectedDocumentNo || !workbench) {
      return;
    }

    if (!workbench.documents.some((item) => item.documentNo === selectedDocumentNo)) {
      updateSearchParams({ documentNo: null, tab: null }, { replace: true });
    }
  }, [selectedDocumentNo, workbench]);

  useEffect(() => {
    if (!detailDrawerOpen || !selectedDocumentNo) {
      return;
    }

    let active = true;

    async function loadDetail() {
      try {
        setDetailLoading(true);
        setDetail(null);
        setDetailError(null);
        const response = (await dashboardApi.getCollectDocumentDetail(selectedDocumentNo)) as unknown;
        if (!isCollectDetailResponse(response)) {
          throw new Error(
            "采集详情接口返回的不是 202 方案正式结构。请重启 FastAPI 服务，确保 `/documents/collect-workbench/{documentNo}` 已接入真实查询。",
          );
        }
        if (active) {
          setDetail(response);
        }
      } catch (loadError) {
        if (active) {
          const status =
            typeof loadError === "object" && loadError !== null && "status" in loadError
              ? Number((loadError as { status?: number }).status)
              : undefined;
          if (status === 404) {
            setDetailError(`当前未找到单据 ${selectedDocumentNo} 的采集详情。请先执行采集或检查数据库是否已落库。`);
          } else {
            setDetailError(loadError instanceof Error ? loadError.message : "加载采集详情失败");
          }
        }
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      active = false;
    };
  }, [detailDrawerOpen, selectedDocumentNo, refreshVersion]);

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

  async function triggerCollect(payloadOverride?: { documentNo?: string; limit?: number; forceRecollect?: boolean }) {
    const normalizedDocumentNo = (payloadOverride?.documentNo ?? runDocumentNo).trim();
    const parsedLimit = payloadOverride?.limit ?? Math.max(Number.parseInt(runLimit, 10) || 0, 1);
    const forceRecollect = payloadOverride?.forceRecollect ?? runForceRecollect;

    try {
      setRunSubmitting(true);
      setRunError(null);
      setRunNotice(null);

      const result = await dashboardApi.startCollectTask({
        documentNo: normalizedDocumentNo,
        limit: normalizedDocumentNo ? 1 : parsedLimit,
        dryRun: runDryRun,
        autoAudit: runDryRun ? false : runAutoAudit,
        forceRecollect: normalizedDocumentNo ? forceRecollect : false,
      });

      setRunNotice(result.message || "采集任务已提交。");
      setRefreshVersion((currentValue) => currentValue + 1);
    } catch (submitError) {
      setRunError(submitError instanceof Error ? submitError.message : "启动采集任务失败");
    } finally {
      setRunSubmitting(false);
    }
  }

  async function triggerAudit(documentNo: string) {
    const normalizedDocumentNo = documentNo.trim();
    if (!normalizedDocumentNo) {
      return;
    }
    try {
      setAuditSubmitting(true);
      setAuditError(null);
      setAuditNotice(null);
      const result = await dashboardApi.startProcessAuditTask({
        documentNo: normalizedDocumentNo,
        documentNos: [],
        limit: 1,
        dryRun: false,
      });
      setAuditNotice(result.message || "评估任务已提交。");
    } catch (submitError) {
      setAuditError(submitError instanceof Error ? submitError.message : "启动评估任务失败");
    } finally {
      setAuditSubmitting(false);
    }
  }

  const documentColumns: GridColDef<CollectDocumentRow>[] = [
    {
      field: "documentNo",
      headerName: "单据编号",
      minWidth: 190,
      flex: 1.1,
      renderCell: (params: GridRenderCellParams<CollectDocumentRow>) => (
        <Button
          color="primary"
          size="small"
          onClick={(event) => {
            event.stopPropagation();
            openDetail(params.row.documentNo);
          }}
          sx={{ minWidth: 0, px: 0, justifyContent: "flex-start", textTransform: "none", fontWeight: 700 }}
        >
          {params.row.documentNo}
        </Button>
      ),
    },
    { field: "permissionTarget", headerName: "权限对象", minWidth: 140, flex: 1 },
    { field: "applicantName", headerName: "申请人", minWidth: 110 },
    { field: "applicantNo", headerName: "工号", minWidth: 100 },
    { field: "departmentName", headerName: "部门", minWidth: 180, flex: 1 },
    {
      field: "collectStatus",
      headerName: "采集状态",
      minWidth: 120,
      renderCell: (params) => (
        <StatusTag label={String(params.value ?? "")} tone={collectStatusTone[String(params.value)] ?? "default"} />
      ),
    },
    { field: "roleCount", headerName: "角色数", minWidth: 90, type: "number" },
    { field: "approvalCount", headerName: "审批记录", minWidth: 100, type: "number" },
    { field: "orgScopeCount", headerName: "组织范围", minWidth: 100, type: "number" },
    { field: "collectedAt", headerName: "最近落库时间", minWidth: 170 },
    {
      field: "recollectAction",
      headerName: "操作",
      minWidth: 130,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams<CollectDocumentRow>) => (
        <Button
          size="small"
          variant="outlined"
          onClick={(event) => {
            event.stopPropagation();
            void triggerCollect({
              documentNo: params.row.documentNo,
              limit: 1,
              forceRecollect: true,
            });
          }}
          disabled={runSubmitting || currentTaskRunning}
          sx={{ textTransform: "none", minWidth: 0 }}
        >
          重新采集
        </Button>
      ),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          当前页面已按 `202` 方案升级为真实采集工作台：主列表读取 PostgreSQL 实时结果，顶部直接接入 `collect`
          runner，详情改为右侧抽屉。
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {runError ? <Alert severity="error">{runError}</Alert> : null}
      {auditError ? <Alert severity="error">{auditError}</Alert> : null}
      {runNotice ? <Alert severity="success">{runNotice}</Alert> : null}
      {auditNotice ? <Alert severity="success">{auditNotice}</Alert> : null}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(workbench?.stats ?? []).map((item) => (
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
              label="查询单据"
              placeholder="单据编号 / 申请人 / 工号 / 权限对象 / 部门"
              value={queryText}
              onChange={(event) => updateSearchParams({ q: event.target.value }, { replace: true })}
              size="small"
              sx={{ minWidth: { xs: "100%", xl: 360 } }}
            />
            <TextField
              select
              label="采集状态"
              value={collectStatusFilter}
              onChange={(event) => updateSearchParams({ collectStatus: event.target.value }, { replace: true })}
              size="small"
              sx={{ minWidth: { xs: "100%", sm: 180 } }}
            >
              <MenuItem value="all">全部状态</MenuItem>
              {collectStatusOptions.map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="指定单据编号"
              placeholder="不填则按待办顺序采集"
              value={runDocumentNo}
              onChange={(event) => setRunDocumentNo(event.target.value)}
              size="small"
              sx={{ minWidth: { xs: "100%", xl: 260 } }}
            />
            <TextField
              label="采集上限"
              value={runLimit}
              onChange={(event) => setRunLimit(event.target.value)}
              size="small"
              sx={{ width: { xs: "100%", sm: 120 } }}
              disabled={Boolean(runDocumentNo.trim())}
            />
            <FormControlLabel
              control={<Switch checked={runDryRun} onChange={(event) => setRunDryRun(event.target.checked)} />}
              label="仅验证不落库"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={runAutoAudit}
                  onChange={(event) => setRunAutoAudit(event.target.checked)}
                  disabled={runDryRun}
                />
              }
              label="采集后自动评估"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={runForceRecollect}
                  onChange={(event) => setRunForceRecollect(event.target.checked)}
                  disabled={!runDocumentNo.trim()}
                />
              }
              label="指定单据强制重采"
              sx={{ ml: 0 }}
            />
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                disableElevation
                onClick={() => void triggerCollect()}
                disabled={runSubmitting || currentTaskRunning}
              >
                {runSubmitting ? "提交中..." : currentTaskRunning ? "采集中..." : "启动采集"}
              </Button>
              <Button
                variant="outlined"
                size="small"
                onClick={() => setRefreshVersion((currentValue) => currentValue + 1)}
              >
                刷新
              </Button>
              <Button
                variant="text"
                size="small"
                disabled={!hasActiveFilters}
                onClick={() => updateSearchParams({ q: null, collectStatus: null }, { replace: true })}
              >
                重置筛选
              </Button>
            </Stack>
          </Stack>

          <Stack
            direction={{ xs: "column", lg: "row" }}
            spacing={1.5}
            justifyContent="space-between"
            alignItems={{ lg: "center" }}
          >
            <Typography variant="body2" color="text.secondary">
              当前结果 {filteredDocuments.length} / {workbenchDocuments.length} 项
              {hasActiveFilters ? "，已按工具栏条件过滤" : "，当前未设置额外筛选"}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              运行中会每 4 秒自动轮询一次工作台；详情抽屉与筛选条件会同步到 URL。
            </Typography>
          </Stack>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.2fr) minmax(320px, 0.8fr)" },
              gap: 2,
            }}
          >
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                border: "1px solid",
                borderColor: "divider",
                backgroundColor: "rgba(255,255,255,0.72)",
              }}
            >
              <Stack spacing={1}>
                <Typography variant="subtitle2">当前采集任务</Typography>
                {currentTask ? (
                  <>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <StatusTag
                        label={formatTaskStatusLabel(currentTask.status)}
                        tone={taskStatusTone[currentTask.status] ?? "default"}
                      />
                      <Typography variant="caption" color="text.secondary">
                        任务号 {currentTask.taskId}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {currentTask.message || "当前任务暂无额外描述。"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      开始 {currentTask.startedAt || currentTask.requestedAt}，成功 {currentTask.successCount} 张，跳过{" "}
                      {currentTask.skippedCount} 张，失败 {currentTask.failedCount} 张。
                    </Typography>
                    {currentTask.auditStatus ? (
                      <Typography variant="caption" color="text.secondary">
                        增量评估 {currentTask.auditStatus === "succeeded" ? "已完成" : currentTask.auditStatus}，
                        批次 {currentTask.auditBatchNo || "-"}。
                      </Typography>
                    ) : null}
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    当前没有运行中的采集任务。
                  </Typography>
                )}
              </Stack>
            </Paper>

            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                border: "1px solid",
                borderColor: "divider",
                backgroundColor: "rgba(255,255,255,0.72)",
              }}
            >
              <Stack spacing={1}>
                <Typography variant="subtitle2">最近一次任务</Typography>
                {workbench?.recentRuns?.[0] ? (
                  <>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <StatusTag
                        label={formatTaskStatusLabel(workbench.recentRuns[0].status)}
                        tone={taskStatusTone[workbench.recentRuns[0].status] ?? "default"}
                      />
                      <Typography variant="caption" color="text.secondary">
                        {workbench.recentRuns[0].startedAt || workbench.recentRuns[0].requestedAt}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {workbench.recentRuns[0].message || "最近一次采集任务已完成。"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      dump: {workbench.recentRuns[0].dumpFile || "-"}
                    </Typography>
                    {workbench.recentRuns[0].auditStatus ? (
                      <Typography variant="caption" color="text.secondary">
                        增量评估 {workbench.recentRuns[0].auditStatus === "succeeded" ? "已完成" : workbench.recentRuns[0].auditStatus}
                        ，批次 {workbench.recentRuns[0].auditBatchNo || "-"}。
                      </Typography>
                    ) : null}
                  </>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    当前还没有可展示的采集任务摘要文件。
                  </Typography>
                )}
              </Stack>
            </Paper>
          </Box>
        </Stack>
      </Paper>

      <AppDataGrid<CollectDocumentRow>
        title="采集单据列表"
        subtitle="默认每页 10 项，仅点击单据编号打开右侧详情抽屉；关闭抽屉后保留列表上下文。"
        rows={filteredDocuments}
        columns={documentColumns}
        loading={loading}
        rowCount={filteredDocuments.length}
        minHeight={MAIN_GRID_HEIGHT}
        pageSizeOptions={[10, 20, 50, 100]}
        initialState={{
          sorting: {
            sortModel: [{ field: "collectedAt", sort: "desc" }],
          },
          pagination: {
            paginationModel: {
              pageSize: MAIN_GRID_PAGE_SIZE,
              page: 0,
            },
          },
        }}
      />

      <AppDataGrid<CollectRunSummary>
        title="最近采集任务"
        subtitle="保留最近任务摘要，便于确认当前 UI 已经接入真实 collect runner。"
        rows={workbench?.recentRuns ?? []}
        columns={runColumns}
        loading={loading}
        rowCount={workbench?.recentRuns.length ?? 0}
        minHeight={320}
        pageSizeOptions={[5, 10, 20]}
        initialState={{
          pagination: {
            paginationModel: {
              pageSize: 5,
              page: 0,
            },
          },
        }}
      />

      <Drawer
        anchor="right"
        open={detailDrawerOpen}
        onClose={closeDetail}
        ModalProps={{ keepMounted: true }}
        PaperProps={{
          sx: {
            width: { xs: "100%", lg: "min(1080px, 72vw)" },
            maxWidth: "100%",
            background: "linear-gradient(180deg, rgba(248,250,252,0.98) 0%, rgba(255,255,255,0.98) 100%)",
          },
        }}
      >
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <Box
            sx={{
              px: { xs: 2, md: 2.5 },
              py: 2.5,
              borderBottom: "1px solid",
              borderColor: "divider",
              backgroundColor: "rgba(255,255,255,0.9)",
            }}
          >
            <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2}>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="overline" color="text.secondary">
                  采集详情抽屉
                </Typography>
                <Typography variant="h5" sx={{ mt: 0.5, wordBreak: "break-all" }}>
                  {selectedDocumentNo || "未选择单据"}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                  当前抽屉只在点击 `单据编号` 时打开，关闭后保留主列表筛选与分页状态。
                </Typography>
              </Box>
              <IconButton onClick={closeDetail} aria-label="关闭采集详情">
                <CloseOutlinedIcon />
              </IconButton>
            </Stack>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>
              <Paper
                elevation={0}
                sx={{
                  px: 1.25,
                  py: 1,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.72)",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  采集状态
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <StatusTag
                    label={detail?.collectStatus ?? selectedDocumentRow?.collectStatus ?? "-"}
                    tone={collectStatusTone[detail?.collectStatus ?? selectedDocumentRow?.collectStatus ?? "-"] ?? "default"}
                  />
                </Box>
              </Paper>
              <Paper
                elevation={0}
                sx={{
                  px: 1.25,
                  py: 1,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.72)",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  权限对象
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  {selectedDocumentRow?.permissionTarget ?? "-"}
                </Typography>
              </Paper>
              <Paper
                elevation={0}
                sx={{
                  px: 1.25,
                  py: 1,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.72)",
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  当前记录
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  角色 {selectedDocumentRow?.roleCount ?? 0} / 审批 {selectedDocumentRow?.approvalCount ?? 0} / 组织{" "}
                  {selectedDocumentRow?.orgScopeCount ?? 0}
                </Typography>
              </Paper>
              <Button
                variant="outlined"
                size="small"
                disabled={!selectedDocumentNo || runSubmitting || currentTaskRunning}
                onClick={() => void triggerCollect({ documentNo: selectedDocumentNo, limit: 1 })}
              >
                {runSubmitting ? "提交中..." : "重新采集当前单据"}
              </Button>
              <Button
                variant="outlined"
                size="small"
                disabled={!selectedDocumentNo || auditSubmitting}
                onClick={() => void triggerAudit(selectedDocumentNo)}
              >
                {auditSubmitting ? "提交中..." : "评估当前单据"}
              </Button>
            </Stack>

            <Tabs
              value={activeTab}
              onChange={(_, value: DetailTab) => updateSearchParams({ tab: value }, { replace: true })}
              variant="scrollable"
              allowScrollButtonsMobile
              sx={{
                mt: 2.5,
                minHeight: 54,
                "& .MuiTabs-flexContainer": {
                  gap: 0.75,
                },
              }}
            >
              {detailTabs.map((tab) => (
                <Tab
                  key={tab.value}
                  value={tab.value}
                  label={tab.label}
                  disableRipple
                  sx={{
                    border: "1px solid",
                    borderColor: "divider",
                    backgroundColor: "rgba(255,255,255,0.7)",
                    "&.Mui-selected": {
                      color: "primary.main",
                      borderColor: "primary.main",
                      backgroundColor: "#ffffff",
                      boxShadow: "inset 0 -3px 0 0 currentColor",
                    },
                  }}
                />
              ))}
            </Tabs>
          </Box>

          <Box sx={{ flex: 1, overflowY: "auto", px: { xs: 2, md: 2.5 }, py: 2.5 }}>
            {detailError ? <Alert severity="error" sx={{ mb: 2 }}>{detailError}</Alert> : null}

            {detailLoading ? (
              <SectionCard title="加载中" subtitle="正在读取采集详情。">
                <Typography variant="body2" color="text.secondary">
                  正在从 PostgreSQL 读取该单据的主表、角色明细、审批记录与组织范围。
                </Typography>
              </SectionCard>
            ) : null}

            {!detailLoading && !detail && selectedDocumentNo ? (
              <SectionCard title="暂无详情" subtitle="当前尚未读取到该单据的采集详情。">
                <Typography variant="body2" color="text.secondary">
                  请先执行采集，或确认该单据已写入 PostgreSQL。
                </Typography>
              </SectionCard>
            ) : null}

            {detail && activeTab === "summary" ? (
              <SectionCard title="单据概览" subtitle="先看主表事实，再判断是否需要补采当前单据。">
                <Stack spacing={2}>
                  <KeyValueList items={detail.overviewFields} />
                  <Box>
                    <Typography variant="subtitle2">处理提示</Typography>
                    <Stack spacing={1} sx={{ mt: 1.5 }}>
                      {detail.notes.map((item, index) => (
                        <Typography key={`${index}-${item}`} variant="body2" color="text.secondary">
                          • {item}
                        </Typography>
                      ))}
                    </Stack>
                  </Box>
                </Stack>
              </SectionCard>
            ) : null}

            {detail && activeTab === "tableStatus" ? (
              <AppDataGrid<TableStatusRow>
                title="四张表落库情况"
                subtitle="按主表、权限明细、审批记录、组织范围四张表展示当前单据的实时落库结果。"
                rows={detail.tableStatus}
                columns={tableColumns}
                loading={detailLoading}
                rowCount={detail.tableStatus.length}
                minHeight={DETAIL_GRID_HEIGHT}
                pageSizeOptions={[10, 20, 50]}
                initialState={{
                  pagination: {
                    paginationModel: {
                      pageSize: DETAIL_GRID_PAGE_SIZE,
                      page: 0,
                    },
                  },
                }}
              />
            ) : null}

            {detail && activeTab === "roles" ? (
              <AppDataGrid<CollectRoleRow>
                title="申请角色"
                subtitle="角色编码、权限级别与组织范围数量均来自当前落库结果。"
                rows={detail.roles}
                columns={roleColumns}
                loading={detailLoading}
                rowCount={detail.roles.length}
                minHeight={DETAIL_GRID_HEIGHT}
                pageSizeOptions={[10, 20, 50]}
                initialState={{
                  pagination: {
                    paginationModel: {
                      pageSize: DETAIL_GRID_PAGE_SIZE,
                      page: 0,
                    },
                  },
                }}
              />
            ) : null}

            {detail && activeTab === "orgScopes" ? (
              <AppDataGrid<CollectOrgScopeRow>
                title="目标组织"
                subtitle="按 `013` 方案落库后的角色-组织展开结果。"
                rows={detail.orgScopes}
                columns={orgScopeColumns}
                loading={detailLoading}
                rowCount={detail.orgScopes.length}
                minHeight={DETAIL_GRID_HEIGHT}
                pageSizeOptions={[10, 20, 50]}
                initialState={{
                  pagination: {
                    paginationModel: {
                      pageSize: DETAIL_GRID_PAGE_SIZE,
                      page: 0,
                    },
                  },
                }}
              />
            ) : null}

            {detail && activeTab === "approvals" ? (
              <AppDataGrid<CollectApprovalRow>
                title="审批记录"
                subtitle="审批轨迹为空时会在主概览与落库情况中单独提示。"
                rows={detail.approvals}
                columns={approvalColumns}
                loading={detailLoading}
                rowCount={detail.approvals.length}
                minHeight={DETAIL_GRID_HEIGHT}
                pageSizeOptions={[10, 20, 50]}
                initialState={{
                  pagination: {
                    paginationModel: {
                      pageSize: DETAIL_GRID_PAGE_SIZE,
                      page: 0,
                    },
                  },
                }}
              />
            ) : null}
          </Box>
        </Box>
      </Drawer>
    </Stack>
  );
}
