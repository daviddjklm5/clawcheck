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
  ProfileChangeAuditAttachmentRow,
  ProfileChangeAuditDetail,
  ProfileChangeAuditDocumentRow,
  ProfileChangeAuditFieldRow,
  ProfileChangeAuditRunSummary,
  ProfileChangeAuditSectionRow,
  ProfileChangeAuditWorkbench,
  TableStatusRow,
  Tone,
} from "../types/dashboard";

type DetailTab = "summary" | "sections" | "fields" | "attachments";

const detailTabs: Array<{ value: DetailTab; label: string }> = [
  { value: "summary", label: "单据总览" },
  { value: "sections", label: "区段分布" },
  { value: "fields", label: "区段字段" },
  { value: "attachments", label: "附件信息" },
];

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

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function isWorkbench(value: unknown): value is ProfileChangeAuditWorkbench {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ProfileChangeAuditWorkbench>;
  return Array.isArray(candidate.stats) && Array.isArray(candidate.documents) && Array.isArray(candidate.recentRuns);
}

function isDetail(value: unknown): value is ProfileChangeAuditDetail {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ProfileChangeAuditDetail>;
  return (
    typeof candidate.documentNo === "string" &&
    Array.isArray(candidate.overviewFields) &&
    Array.isArray(candidate.tableStatus) &&
    Array.isArray(candidate.sectionRows) &&
    Array.isArray(candidate.fieldRows) &&
    Array.isArray(candidate.attachmentRows) &&
    Array.isArray(candidate.notes)
  );
}

const documentColumns: GridColDef<ProfileChangeAuditDocumentRow>[] = [
  {
    field: "documentNo",
    headerName: "单据编号",
    minWidth: 190,
    flex: 1,
    renderCell: () => null,
  },
  { field: "documentName", headerName: "单据名称", minWidth: 260, flex: 1.3 },
  { field: "documentStatus", headerName: "单据状态", minWidth: 120 },
  { field: "creatorName", headerName: "创建人", minWidth: 110 },
  { field: "submitTime", headerName: "提交时间", minWidth: 170 },
  { field: "sectionCount", headerName: "区段数", minWidth: 90, type: "number" },
  { field: "fieldCount", headerName: "字段记录", minWidth: 100, type: "number" },
  { field: "attachmentCount", headerName: "附件数", minWidth: 90, type: "number" },
  { field: "collectedAt", headerName: "最近落库时间", minWidth: 170 },
];

const runColumns: GridColDef<ProfileChangeAuditRunSummary>[] = [
  {
    field: "status",
    headerName: "任务状态",
    minWidth: 120,
    renderCell: (params) => (
      <StatusTag label={formatTaskStatusLabel(String(params.value ?? ""))} tone={taskStatusTone[String(params.value)] ?? "default"} />
    ),
  },
  { field: "requestedDocumentNo", headerName: "指定单据", minWidth: 180, flex: 1 },
  { field: "requestedLimit", headerName: "上限", minWidth: 80, type: "number" },
  { field: "pageSize", headerName: "分页", minWidth: 80, type: "number" },
  { field: "successCount", headerName: "成功", minWidth: 80, type: "number" },
  { field: "failedCount", headerName: "失败", minWidth: 80, type: "number" },
  { field: "startedAt", headerName: "开始时间", minWidth: 170 },
];

const tableColumns: GridColDef<TableStatusRow>[] = [
  { field: "tableName", headerName: "目标表", minWidth: 220, flex: 1 },
  { field: "status", headerName: "状态", minWidth: 120 },
  { field: "records", headerName: "记录数", minWidth: 90, type: "number" },
  { field: "updatedAt", headerName: "更新时间", minWidth: 170 },
];

const sectionColumns: GridColDef<ProfileChangeAuditSectionRow>[] = [
  { field: "sectionSeq", headerName: "区段序号", minWidth: 100 },
  { field: "sectionName", headerName: "区段名称", minWidth: 180, flex: 1 },
  { field: "subsectionName", headerName: "子区段名称", minWidth: 180, flex: 1 },
  { field: "sectionType", headerName: "区段类型", minWidth: 120 },
  { field: "rowCount", headerName: "行数", minWidth: 90, type: "number" },
  { field: "fieldCount", headerName: "字段数", minWidth: 90, type: "number" },
  { field: "attachmentCount", headerName: "附件数", minWidth: 90, type: "number" },
];

const fieldColumns: GridColDef<ProfileChangeAuditFieldRow>[] = [
  { field: "sectionName", headerName: "区段名称", minWidth: 160 },
  { field: "subsectionName", headerName: "子区段名称", minWidth: 160 },
  { field: "rowSeq", headerName: "行", minWidth: 80 },
  { field: "fieldSeq", headerName: "字段序号", minWidth: 90 },
  { field: "fieldName", headerName: "字段名称", minWidth: 180, flex: 1 },
  { field: "fieldValue", headerName: "字段值", minWidth: 260, flex: 1.2 },
  { field: "fieldType", headerName: "字段类型", minWidth: 120 },
];

const attachmentColumns: GridColDef<ProfileChangeAuditAttachmentRow>[] = [
  { field: "sectionName", headerName: "区段名称", minWidth: 160 },
  { field: "changeItem", headerName: "变更项", minWidth: 160 },
  { field: "attachmentName", headerName: "附件名称", minWidth: 240, flex: 1.2 },
  { field: "downloadStatus", headerName: "下载状态", minWidth: 120 },
  { field: "downloadTime", headerName: "下载时间", minWidth: 170 },
  { field: "relativePath", headerName: "相对路径", minWidth: 260, flex: 1.2 },
];

export function ProfileChangeAuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [workbench, setWorkbench] = useState<ProfileChangeAuditWorkbench | null>(null);
  const [detail, setDetail] = useState<ProfileChangeAuditDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [runDocumentNo, setRunDocumentNo] = useState("");
  const [runLimit, setRunLimit] = useState("20");
  const [runPageSize, setRunPageSize] = useState("100");
  const [runHeaded, setRunHeaded] = useState(false);
  const [runDryRun, setRunDryRun] = useState(false);
  const [runDownloadAttachments, setRunDownloadAttachments] = useState(false);
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runNotice, setRunNotice] = useState<string | null>(null);

  const queryText = searchParams.get("q") ?? "";
  const statusFilter = searchParams.get("status") ?? "all";
  const selectedDocumentNo = searchParams.get("documentNo") ?? "";
  const activeTab: DetailTab = isDetailTab(searchParams.get("tab")) ? (searchParams.get("tab") as DetailTab) : "summary";
  const deferredQueryText = useDeferredValue(queryText);
  const normalizedQueryText = normalizeText(deferredQueryText);
  const currentTask = workbench?.currentTask ?? null;
  const currentTaskRunning = currentTask?.status === "queued" || currentTask?.status === "running";
  const workbenchDocuments = workbench?.documents ?? [];
  const selectedDocumentRow = workbenchDocuments.find((item) => item.documentNo === selectedDocumentNo) ?? null;
  const filteredDocuments = workbenchDocuments.filter((item) => {
    if (statusFilter !== "all" && item.documentStatus !== statusFilter) return false;
    if (!normalizedQueryText) return true;
    return normalizeText([item.documentNo, item.documentName, item.creatorName, item.documentStatus].join(" ")).includes(normalizedQueryText);
  });

  function updateSearchParams(updates: Record<string, string | null>, replace = true) {
    const nextParams = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "" || value === "all") nextParams.delete(key);
      else nextParams.set(key, value);
    });
    if (nextParams.toString() !== searchParams.toString()) setSearchParams(nextParams, { replace });
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getProfileChangeAuditWorkbench()) as unknown;
        if (!isWorkbench(response)) throw new Error("310 工作台接口返回结构不正确。");
        if (!active) return;
        setWorkbench(response);
        setError(null);
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : "加载 310 工作台失败");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [refreshVersion]);

  useEffect(() => {
    if (!selectedDocumentNo) return;
    let active = true;
    async function loadDetail() {
      try {
        setDetailLoading(true);
        setDetail(null);
        const response = (await dashboardApi.getProfileChangeAuditDocumentDetail(selectedDocumentNo)) as unknown;
        if (!isDetail(response)) throw new Error("310 详情接口返回结构不正确。");
        if (active) {
          setDetail(response);
          setDetailError(null);
        }
      } catch (loadError) {
        if (active) setDetailError(loadError instanceof Error ? loadError.message : "加载详情失败");
      } finally {
        if (active) setDetailLoading(false);
      }
    }
    void loadDetail();
    return () => {
      active = false;
    };
  }, [selectedDocumentNo, refreshVersion]);

  useEffect(() => {
    if (!currentTaskRunning) return;
    const timer = window.setInterval(() => setRefreshVersion((currentValue) => currentValue + 1), 4000);
    return () => window.clearInterval(timer);
  }, [currentTaskRunning]);

  async function triggerRun(documentNo = "", limitOverride?: number) {
    const normalizedDocumentNo = documentNo || runDocumentNo.trim();
    try {
      setRunSubmitting(true);
      setRunError(null);
      setRunNotice(null);
      const result = await dashboardApi.startProfileChangeAuditTask({
        documentNo: normalizedDocumentNo,
        limit: normalizedDocumentNo ? 1 : limitOverride ?? Math.max(Number.parseInt(runLimit, 10) || 0, 1),
        pageSize: Math.max(Number.parseInt(runPageSize, 10) || 0, 1),
        headed: runHeaded,
        dryRun: runDryRun,
        downloadAttachments: runDownloadAttachments,
      });
      setRunNotice(result.message || "310 采集任务已提交。");
      setRefreshVersion((currentValue) => currentValue + 1);
    } catch (submitError) {
      setRunError(submitError instanceof Error ? submitError.message : "启动 310 采集任务失败");
    } finally {
      setRunSubmitting(false);
    }
  }

  documentColumns[0] = {
    ...documentColumns[0],
    renderCell: (params: GridRenderCellParams<ProfileChangeAuditDocumentRow>) => (
      <Button
        color="primary"
        size="small"
        onClick={(event) => {
          event.stopPropagation();
          updateSearchParams({ documentNo: params.row.documentNo, tab: "summary" }, false);
        }}
        sx={{ minWidth: 0, px: 0, justifyContent: "flex-start", textTransform: "none", fontWeight: 700 }}
      >
        {params.row.documentNo}
      </Button>
    ),
  };

  return (
    <Stack spacing={3}>
      <Typography variant="body1">
        310 工作台用于查看“人员档案修改审核”采集结果，支持按正确入口发起采集任务，并核对主表、区段字段、附件三张表的落库情况。
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {runError ? <Alert severity="error">{runError}</Alert> : null}
      {runNotice ? <Alert severity="success">{runNotice}</Alert> : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", xl: "repeat(4,1fr)" }, gap: 2 }}>
        {(workbench?.stats ?? []).map((item) => <StatCard key={item.label} item={item} />)}
      </Box>

      <SectionCard title="启动采集" subtitle="默认按“最近使用 -> 人员档案信息变更申请 -> 我的审批进度”采集。">
        <Stack spacing={2}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(4,1fr)" }, gap: 2 }}>
            <TextField label="指定单据编号" value={runDocumentNo} onChange={(event) => setRunDocumentNo(event.target.value)} />
            <TextField label="采集上限" value={runLimit} onChange={(event) => setRunLimit(event.target.value)} type="number" disabled={Boolean(runDocumentNo.trim())} />
            <TextField label="分页大小" value={runPageSize} onChange={(event) => setRunPageSize(event.target.value)} select>
              {[20, 50, 100].map((item) => <MenuItem key={item} value={String(item)}>{item} 条/页</MenuItem>)}
            </TextField>
            <TextField label="状态筛选" value={statusFilter} onChange={(event) => updateSearchParams({ status: event.target.value })} select>
              <MenuItem value="all">全部状态</MenuItem>
              {Array.from(new Set(workbenchDocuments.map((item) => item.documentStatus))).filter(Boolean).map((item) => (
                <MenuItem key={item} value={item}>{item}</MenuItem>
              ))}
            </TextField>
          </Box>

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <FormControlLabel control={<Switch checked={runHeaded} onChange={(event) => setRunHeaded(event.target.checked)} />} label="可视浏览器" sx={{ ml: 0 }} />
            <FormControlLabel control={<Switch checked={runDryRun} onChange={(event) => setRunDryRun(event.target.checked)} />} label="dry-run" sx={{ ml: 0 }} />
            <FormControlLabel control={<Switch checked={runDownloadAttachments} onChange={(event) => setRunDownloadAttachments(event.target.checked)} />} label="尝试下载附件" sx={{ ml: 0 }} />
          </Stack>

          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button variant="contained" disableElevation onClick={() => void triggerRun()} disabled={runSubmitting || currentTaskRunning}>
              {runSubmitting ? "提交中..." : currentTaskRunning ? "采集中..." : "启动 310 采集"}
            </Button>
            <Button variant="outlined" onClick={() => setRefreshVersion((currentValue) => currentValue + 1)}>刷新</Button>
            <Button variant="text" onClick={() => updateSearchParams({ q: null, status: null })}>重置筛选</Button>
          </Stack>
        </Stack>
      </SectionCard>

      {currentTask ? (
        <Alert severity={currentTask.status === "failed" ? "error" : currentTask.status === "partial" ? "warning" : "info"}>
          {formatTaskStatusLabel(currentTask.status)}：{currentTask.message}
        </Alert>
      ) : null}

      <AppDataGrid<ProfileChangeAuditDocumentRow>
        title="人员档案修改审核单据"
        subtitle="点击单据编号打开右侧详情抽屉。"
        rows={filteredDocuments}
        columns={documentColumns}
        loading={loading}
        rowCount={filteredDocuments.length}
        minHeight={760}
        pageSizeOptions={[10, 20, 50, 100]}
        initialState={{ pagination: { paginationModel: { pageSize: 20, page: 0 } } }}
      />

      <AppDataGrid<ProfileChangeAuditRunSummary>
        title="最近任务"
        subtitle="保留 310 任务摘要，确认前后端接线已生效。"
        rows={workbench?.recentRuns ?? []}
        columns={runColumns}
        loading={loading}
        rowCount={workbench?.recentRuns.length ?? 0}
        minHeight={320}
        pageSizeOptions={[5, 10]}
        initialState={{ pagination: { paginationModel: { pageSize: 5, page: 0 } } }}
      />

      <Drawer anchor="right" open={Boolean(selectedDocumentNo)} onClose={() => updateSearchParams({ documentNo: null, tab: null }, false)} PaperProps={{ sx: { width: { xs: "100%", lg: "min(1480px,100vw)" } } }}>
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.5, borderBottom: "1px solid", borderColor: "divider" }}>
            <Stack direction="row" justifyContent="space-between" spacing={2}>
              <Box>
                <Typography variant="overline" color="text.secondary">310 详情抽屉</Typography>
                <Typography variant="h5" sx={{ mt: 0.5, wordBreak: "break-all" }}>{selectedDocumentNo || "未选择单据"}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                  当前抽屉展示主表、区段字段、附件三张表的聚合结果。
                </Typography>
              </Box>
              <IconButton onClick={() => updateSearchParams({ documentNo: null, tab: null }, false)} aria-label="关闭 310 详情"><CloseOutlinedIcon /></IconButton>
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>
              <Typography variant="body2">状态：{detail?.documentStatus ?? selectedDocumentRow?.documentStatus ?? "-"}</Typography>
              <Button variant="outlined" size="small" disabled={!selectedDocumentNo || runSubmitting || currentTaskRunning} onClick={() => void triggerRun(selectedDocumentNo, 1)}>重新采集当前单据</Button>
            </Stack>
            <Tabs value={activeTab} onChange={(_, value: DetailTab) => updateSearchParams({ tab: value })} variant="scrollable" allowScrollButtonsMobile sx={{ mt: 2 }}>
              {detailTabs.map((tab) => <Tab key={tab.value} value={tab.value} label={tab.label} />)}
            </Tabs>
          </Box>

          <Box sx={{ flex: 1, overflowY: "auto", px: { xs: 2, md: 2.5 }, py: 2.5 }}>
            {detailError ? <Alert severity="error" sx={{ mb: 2 }}>{detailError}</Alert> : null}
            {detailLoading ? <Alert severity="info">正在读取 310 详情...</Alert> : null}

            {detail && activeTab === "summary" ? (
              <Stack spacing={3}>
                <SectionCard title="单据概览" subtitle="先看主表摘要，再判断是否需要重采。">
                  <Stack spacing={2}>
                    <KeyValueList items={detail.overviewFields} />
                    <Box>
                      <Typography variant="subtitle2">处理提示</Typography>
                      <Stack spacing={1} sx={{ mt: 1.5 }}>
                        {detail.notes.map((item, index) => <Typography key={`${index}-${item}`} variant="body2" color="text.secondary">- {item}</Typography>)}
                      </Stack>
                    </Box>
                  </Stack>
                </SectionCard>
                <AppDataGrid<TableStatusRow>
                  title="落库情况"
                  rows={detail.tableStatus}
                  columns={tableColumns}
                  rowCount={detail.tableStatus.length}
                  minHeight={320}
                  pageSizeOptions={[5, 10]}
                  initialState={{ pagination: { paginationModel: { pageSize: 5, page: 0 } } }}
                />
              </Stack>
            ) : null}

            {detail && activeTab === "sections" ? <AppDataGrid<ProfileChangeAuditSectionRow> title="区段分布" rows={detail.sectionRows} columns={sectionColumns} rowCount={detail.sectionRows.length} minHeight={760} pageSizeOptions={[10, 20, 50]} initialState={{ pagination: { paginationModel: { pageSize: 20, page: 0 } } }} /> : null}
            {detail && activeTab === "fields" ? <AppDataGrid<ProfileChangeAuditFieldRow> title="区段字段" rows={detail.fieldRows} columns={fieldColumns} rowCount={detail.fieldRows.length} minHeight={760} pageSizeOptions={[10, 20, 50]} initialState={{ pagination: { paginationModel: { pageSize: 20, page: 0 } } }} /> : null}
            {detail && activeTab === "attachments" ? <AppDataGrid<ProfileChangeAuditAttachmentRow> title="附件信息" rows={detail.attachmentRows} columns={attachmentColumns} rowCount={detail.attachmentRows.length} minHeight={760} pageSizeOptions={[10, 20, 50]} initialState={{ pagination: { paginationModel: { pageSize: 20, page: 0 } } }} /> : null}
          </Box>
        </Box>
      </Drawer>
    </Stack>
  );
}
