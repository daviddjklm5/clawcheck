import { useDeferredValue, useEffect, useState } from "react";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";
import {
  Alert,
  Box,
  Button,
  Drawer,
  IconButton,
  MenuItem,
  Paper,
  Stack,
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
import { StatusTag } from "../components/StatusTag";
import { StatCard } from "../components/StatCard";
import { dashboardApi } from "../services/api";
import type {
  ApprovalRow,
  OrgScopeRow,
  ProcessApprovalResponse,
  ProcessDetail,
  ProcessDocumentRow,
  ProcessWorkbench,
  RiskDetailRow,
  RoleRow,
  StatItem,
  Tone,
} from "../types/dashboard";

type DetailTab =
  | "summary"
  | "riskOverview"
  | "approvalAction"
  | "lowScoreDetails"
  | "roles"
  | "orgScopes"
  | "approvals";

const MAIN_GRID_PAGE_SIZE = 10;
const DETAIL_GRID_PAGE_SIZE = 10;
const MAIN_GRID_HEIGHT = 760;
const DETAIL_GRID_HEIGHT = 920;

const documentStatusTone: Record<string, Tone> = {
  已提交: "warning",
  已完成: "success",
  已驳回: "danger",
  待处理: "warning",
};

const conclusionTone: Record<string, Tone> = {
  拒绝: "danger",
  人工干预: "warning",
  加强审核: "warning",
  仅关注: "info",
  可信任: "success",
};

const actionTone: Record<string, Tone> = {
  reject: "danger",
  manual_review: "warning",
  warning: "info",
  allow: "success",
};

const detailTabs: Array<{ value: DetailTab; label: string }> = [
  { value: "summary", label: "单据概览" },
  { value: "riskOverview", label: "风险总览" },
  { value: "approvalAction", label: "审批单据" },
  { value: "lowScoreDetails", label: "原始低分明细" },
  { value: "roles", label: "申请角色" },
  { value: "orgScopes", label: "目标组织" },
  { value: "approvals", label: "审批记录" },
];

const quickConclusionFilters = ["all", "拒绝", "加强审核"] as const;

function isDetailTab(value: string | null): value is DetailTab {
  return detailTabs.some((item) => item.value === value);
}

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function formatScoreLabel(score: number | null | undefined): string {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "-";
  }
  return score.toFixed(1);
}

function getScoreTone(score: number | null | undefined): Tone {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "default";
  }
  if (score <= 0) {
    return "danger";
  }
  if (score <= 1) {
    return "warning";
  }
  if (score <= 1.5) {
    return "info";
  }
  return "success";
}

function isProcessWorkbenchResponse(value: unknown): value is ProcessWorkbench {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ProcessWorkbench>;
  return Array.isArray(candidate.stats) && Array.isArray(candidate.documents);
}

function isProcessDetailResponse(value: unknown): value is ProcessDetail {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ProcessDetail>;
  return (
    typeof candidate.documentNo === "string" &&
    Array.isArray(candidate.overviewFields) &&
    Boolean(candidate.feedbackOverview) &&
    Array.isArray(candidate.roles) &&
    Array.isArray(candidate.approvals) &&
    Array.isArray(candidate.orgScopes) &&
    Array.isArray(candidate.riskDetails) &&
    Array.isArray(candidate.notes)
  );
}

function WorkbenchStat({ item }: { item: StatItem }) {
  return (
    <Paper
      elevation={0}
      sx={{
        minWidth: 0,
        px: 1.5,
        py: 1.25,
        border: "1px solid",
        borderColor: "divider",
        backgroundColor: "rgba(255,255,255,0.78)",
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {item.label}
      </Typography>
      <Box sx={{ mt: 0.75, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Typography variant="subtitle2">{item.value}</Typography>
        <StatusTag label={item.value} tone={item.tone} />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: "block" }}>
        {item.hint}
      </Typography>
    </Paper>
  );
}

const roleColumns: GridColDef<RoleRow>[] = [
  { field: "lineNo", headerName: "明细行号", minWidth: 100 },
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 220, flex: 1.2 },
  { field: "permissionLevel", headerName: "权限级别", minWidth: 130 },
  { field: "applyType", headerName: "申请类型", minWidth: 110 },
  { field: "orgScopeCount", headerName: "组织范围数", minWidth: 110, type: "number" },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const approvalColumns: GridColDef<ApprovalRow>[] = [
  { field: "nodeName", headerName: "节点", minWidth: 150 },
  { field: "approver", headerName: "审批人", minWidth: 120 },
  { field: "action", headerName: "动作", minWidth: 100 },
  { field: "finishedAt", headerName: "完成时间", minWidth: 170 },
  { field: "comment", headerName: "审批意见", minWidth: 220, flex: 1.2 },
];

const orgScopeColumns: GridColDef<OrgScopeRow>[] = [
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 200, flex: 1.1 },
  { field: "organizationCode", headerName: "组织编码", minWidth: 120 },
  { field: "organizationName", headerName: "组织名称", minWidth: 180, flex: 1.1 },
  { field: "orgUnitName", headerName: "组织单位", minWidth: 150 },
  { field: "physicalLevel", headerName: "物理层级", minWidth: 110 },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const riskColumns: GridColDef<RiskDetailRow>[] = [
  { field: "dimensionName", headerName: "维度", minWidth: 170 },
  { field: "ruleId", headerName: "规则编码", minWidth: 180 },
  {
    field: "score",
    headerName: "得分",
    minWidth: 90,
    renderCell: (params) => (
      <StatusTag label={formatScoreLabel(params.value as number)} tone={getScoreTone(params.value as number)} />
    ),
  },
  { field: "roleCode", headerName: "角色编码", minWidth: 120 },
  { field: "orgCode", headerName: "组织编码", minWidth: 120 },
  { field: "interventionAction", headerName: "建议干预动作", minWidth: 170 },
  { field: "detailConclusion", headerName: "明细结论", minWidth: 320, flex: 1.5 },
];

export function ProcessDocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [workbench, setWorkbench] = useState<ProcessWorkbench | null>(null);
  const [detail, setDetail] = useState<ProcessDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [approvalOpinion, setApprovalOpinion] = useState("同意");
  const [approvalSubmittingMode, setApprovalSubmittingMode] = useState<"approve" | "dryRun" | null>(null);
  const [approvalResult, setApprovalResult] = useState<ProcessApprovalResponse | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const queryText = searchParams.get("q") ?? "";
  const deferredQueryText = useDeferredValue(queryText);
  const conclusionFilter = searchParams.get("conclusion") ?? "all";
  const statusFilter = searchParams.get("status") ?? "all";
  const selectedDocumentNo = searchParams.get("documentNo") ?? "";
  const detailDrawerOpen = selectedDocumentNo !== "";
  const activeTab: DetailTab = isDetailTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as DetailTab)
    : "summary";

  const workbenchStats = workbench?.stats ?? [];
  const workbenchDocuments = workbench?.documents ?? [];
  const selectedDocumentRow =
    workbenchDocuments.find((item) => item.documentNo === selectedDocumentNo) ?? null;
  const detailOverviewFields = detail?.overviewFields ?? [];
  const detailFeedbackOverview = detail?.feedbackOverview ?? null;
  const detailFeedbackStats = detailFeedbackOverview?.feedbackStats ?? [];
  const detailFeedbackGroups = detailFeedbackOverview?.feedbackGroups ?? [];
  const detailNotes = detail?.notes ?? [];
  const detailRiskDetails = detail?.riskDetails ?? [];
  const detailRoles = detail?.roles ?? [];
  const detailOrgScopes = detail?.orgScopes ?? [];
  const detailApprovals = detail?.approvals ?? [];

  const normalizedQueryText = normalizeText(deferredQueryText);
  const statusOptions = Array.from(
    new Set(workbenchDocuments.map((item) => item.documentStatus).filter((item) => Boolean(item))),
  );
  const filteredDocuments = workbenchDocuments.filter((item) => {
    if (conclusionFilter !== "all" && item.summaryConclusionLabel !== conclusionFilter) {
      return false;
    }
    if (statusFilter !== "all" && item.documentStatus !== statusFilter) {
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
        item.department,
        item.summaryConclusionLabel,
      ].join(" "),
    ).includes(normalizedQueryText);
  });
  const hasActiveFilters = Boolean(queryText || conclusionFilter !== "all" || statusFilter !== "all");

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

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getProcessWorkbench()) as unknown;
        if (!isProcessWorkbenchResponse(response)) {
          throw new Error(
            "处理工作台接口返回的不是 201 方案正式结构。请重启 FastAPI 服务，确保 `/documents/process-workbench` 已切换到 PostgreSQL 实时接口。",
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
          setError(loadError instanceof Error ? loadError.message : "加载处理单据页失败");
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
        const response = (await dashboardApi.getProcessDocumentDetail(selectedDocumentNo)) as unknown;
        if (!isProcessDetailResponse(response)) {
          throw new Error(
            "单据详情接口返回的不是 201 方案正式结构。请重启 FastAPI 服务，确保 `/documents/process-workbench/{documentNo}` 已切换到 PostgreSQL 实时查询。",
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
            setDetailError(`当前未找到单据 ${selectedDocumentNo} 的评估详情。请确认该单据已完成评估并成功落库。`);
          } else {
            setDetailError(loadError instanceof Error ? loadError.message : "加载单据详情失败");
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
    setApprovalOpinion("同意");
    setApprovalResult(null);
    setApprovalError(null);
    setApprovalSubmittingMode(null);
  }, [selectedDocumentNo]);

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

  async function runApproval(dryRun: boolean) {
    if (!selectedDocumentNo) {
      return;
    }

    const opinion = approvalOpinion.trim();
    if (!opinion) {
      setApprovalError("请先填写审批意见，再执行审批。");
      setApprovalResult(null);
      return;
    }

    try {
      setApprovalSubmittingMode(dryRun ? "dryRun" : "approve");
      setApprovalError(null);
      setApprovalResult(null);
      const response = await dashboardApi.approveProcessDocument(selectedDocumentNo, {
        action: "approve",
        approvalOpinion: opinion,
        dryRun,
      });
      setApprovalResult(response);
    } catch (approvalLoadError) {
      setApprovalError(approvalLoadError instanceof Error ? approvalLoadError.message : "审批执行失败");
    } finally {
      setApprovalSubmittingMode(null);
    }
  }

  const documentColumns: GridColDef<ProcessDocumentRow>[] = [
    {
      field: "documentNo",
      headerName: "单据编号",
      minWidth: 180,
      flex: 1.1,
      renderCell: (params: GridRenderCellParams<ProcessDocumentRow>) => (
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
    { field: "permissionTarget", headerName: "权限对象", minWidth: 130, flex: 0.9 },
    { field: "applicantName", headerName: "申请人", minWidth: 110 },
    { field: "applicantNo", headerName: "工号", minWidth: 100 },
    { field: "department", headerName: "部门", minWidth: 180, flex: 1 },
    {
      field: "documentStatus",
      headerName: "单据状态",
      minWidth: 110,
      renderCell: (params) => (
        <StatusTag
          label={String(params.value ?? "")}
          tone={documentStatusTone[String(params.value)] ?? "default"}
        />
      ),
    },
    {
      field: "finalScore",
      headerName: "最终信任分",
      minWidth: 110,
      renderCell: (params) => (
        <StatusTag label={formatScoreLabel(params.value as number)} tone={getScoreTone(params.value as number)} />
      ),
    },
    {
      field: "summaryConclusion",
      headerName: "总结论",
      minWidth: 120,
      renderCell: (params) => (
        <StatusTag
          label={String(params.row.summaryConclusionLabel ?? params.value ?? "")}
          tone={conclusionTone[String(params.row.summaryConclusionLabel ?? params.value)] ?? "default"}
        />
      ),
    },
    {
      field: "suggestedActionLabel",
      headerName: "建议动作",
      minWidth: 140,
      renderCell: (params) => (
        <StatusTag
          label={String(params.value ?? "")}
          tone={actionTone[params.row.suggestedAction] ?? "default"}
        />
      ),
    },
    {
      field: "lowScoreDetailCount",
      headerName: "原始低分明细数",
      minWidth: 140,
      type: "number",
    },
    { field: "assessedAt", headerName: "评估时间", minWidth: 170 },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          当前页面已按 `201` 方案收敛为单据处理工作台，仅保留待处理列表；批次分布与执行日志已拆到 `评估分析` 页面。
        </Typography>
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={1.5}
          sx={{ mt: 1.5, flexWrap: "wrap" }}
        >
          {workbenchStats.map((item) => (
            <WorkbenchStat key={item.label} item={item} />
          ))}
        </Stack>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

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
              label="单据状态"
              value={statusFilter}
              onChange={(event) => updateSearchParams({ status: event.target.value }, { replace: true })}
              size="small"
              sx={{ minWidth: { xs: "100%", sm: 180 } }}
            >
              <MenuItem value="all">全部状态</MenuItem>
              {statusOptions.map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
              {quickConclusionFilters.map((item) => {
                const selected = conclusionFilter === item || (item === "all" && conclusionFilter === "all");
                const label = item === "all" ? "全部结论" : item;
                return (
                  <Button
                    key={item}
                    variant={selected ? "contained" : "outlined"}
                    disableElevation
                    size="small"
                    onClick={() => updateSearchParams({ conclusion: item }, { replace: true })}
                    sx={{ textTransform: "none" }}
                  >
                    {label}
                  </Button>
                );
              })}
            </Stack>
            <Stack direction="row" spacing={1}>
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
                onClick={() =>
                  updateSearchParams(
                    {
                      q: null,
                      conclusion: null,
                      status: null,
                    },
                    { replace: true },
                  )
                }
              >
                重置筛选
              </Button>
            </Stack>
          </Stack>

          <Stack
            direction={{ xs: "column", md: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", md: "center" }}
            spacing={1}
          >
            <Typography variant="body2" color="text.secondary">
              当前结果 {filteredDocuments.length} / {workbenchDocuments.length} 项
              {hasActiveFilters ? "，已按工具栏条件过滤" : "，当前未设置额外筛选"}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              当前筛选条件与抽屉状态会同步到 URL，刷新页面后可恢复上下文。
            </Typography>
          </Stack>
        </Stack>
      </Paper>

      <AppDataGrid<ProcessDocumentRow>
        title="待处理单据列表"
        subtitle="默认每页 10 项，仅点击单据编号打开右侧详情抽屉；关闭抽屉后保留列表上下文。"
        rows={filteredDocuments}
        columns={documentColumns}
        loading={loading}
        rowCount={filteredDocuments.length}
        minHeight={MAIN_GRID_HEIGHT}
        pageSizeOptions={[10, 20, 50, 100]}
        initialState={{
          sorting: {
            sortModel: [{ field: "finalScore", sort: "asc" }],
          },
          pagination: {
            paginationModel: {
              pageSize: MAIN_GRID_PAGE_SIZE,
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
            width: { xs: "100%", lg: "min(1120px, 72vw)" },
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
                  单据详情抽屉
                </Typography>
                <Typography variant="h5" sx={{ mt: 0.5, wordBreak: "break-all" }}>
                  {selectedDocumentNo || "未选择单据"}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                  详情按需从右侧打开，关闭后保留当前列表的筛选、排序和分页状态。
                </Typography>
              </Box>
              <IconButton onClick={closeDetail} aria-label="关闭单据详情">
                <CloseOutlinedIcon />
              </IconButton>
            </Stack>

            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={1}
              sx={{ mt: 2, flexWrap: "wrap" }}
            >
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
                  当前总结论
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <StatusTag
                    label={selectedDocumentRow?.summaryConclusionLabel ?? "-"}
                    tone={conclusionTone[selectedDocumentRow?.summaryConclusionLabel ?? "-"] ?? "default"}
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
                  最终信任分
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <StatusTag
                    label={formatScoreLabel(selectedDocumentRow?.finalScore)}
                    tone={getScoreTone(selectedDocumentRow?.finalScore)}
                  />
                </Box>
              </Paper>
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
              <SectionCard title="加载中" subtitle="正在读取单据详情。">
                <Typography variant="body2" color="text.secondary">
                  正在从 PostgreSQL 读取该单据的单据概览、聚合反馈、原始低分明细、组织范围与审批记录。
                </Typography>
              </SectionCard>
            ) : null}

            {!detailLoading && !detail && selectedDocumentNo ? (
              <SectionCard title="暂无详情" subtitle="当前尚未读取到该单据的详情数据。">
                <Typography variant="body2" color="text.secondary">
                  请确认该单据已完成评估并成功落库。
                </Typography>
              </SectionCard>
            ) : null}

            {detail && activeTab === "summary" ? (
              <SectionCard title="单据概览" subtitle="先看单据基础事实，再进入风险判断与审批动作。">
                <KeyValueList items={detailOverviewFields} />
              </SectionCard>
            ) : null}

            {detail && activeTab === "riskOverview" ? (
              <SectionCard title="风险总览" subtitle="默认按 104 方案聚合展示风险摘要，避免把角色 x 组织展开条数误读为风险点数量。">
                <Stack spacing={2}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 2,
                      p: 1.5,
                      border: "1px solid",
                      borderColor: "divider",
                      backgroundColor: "rgba(255,255,255,0.75)",
                    }}
                  >
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        当前展示结论
                      </Typography>
                      <Typography variant="h6" sx={{ mt: 0.75 }}>
                        {detailFeedbackOverview?.summaryConclusionLabel ?? "-"}
                      </Typography>
                    </Box>
                    <StatusTag
                      label={detailFeedbackOverview?.summaryConclusionLabel ?? "-"}
                      tone={conclusionTone[detailFeedbackOverview?.summaryConclusionLabel ?? "-"] ?? "default"}
                    />
                  </Box>

                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(5, minmax(0, 1fr))" },
                      gap: 2,
                    }}
                  >
                    {detailFeedbackStats.map((item) => (
                      <StatCard key={item.label} item={item} />
                    ))}
                  </Box>

                  <Stack spacing={1.25}>
                    {detailFeedbackGroups.map((group) => (
                      <Box
                        key={group.id}
                        sx={{
                          p: 1.75,
                          border: "1px solid",
                          borderColor: "divider",
                          backgroundColor: "rgba(255,255,255,0.7)",
                        }}
                      >
                        <Typography variant="subtitle2">{group.title}</Typography>
                        <Typography variant="body2" sx={{ mt: 1, lineHeight: 1.75 }}>
                          {group.summary}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                          影响组织单位 {group.affectedOrgUnitCount} 个，影响组织 {group.affectedOrgCount} 个，
                          影响角色 {group.affectedRoleCount} 个，原始低分明细 {group.rawDetailCount} 条。
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: "block" }}>
                          {group.hint}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>

                  <Box>
                    <Typography variant="subtitle2">处理提示</Typography>
                    <Stack spacing={1} sx={{ mt: 1.5 }}>
                      {detailNotes.map((item, index) => (
                        <Typography key={`${index}-${item}`} variant="body2" color="text.secondary">
                          • {item}
                        </Typography>
                      ))}
                    </Stack>
                  </Box>
                </Stack>
              </SectionCard>
            ) : null}

            {activeTab === "approvalAction" ? (
              <SectionCard title="审批单据" subtitle="第一阶段仅开放批准动作；前端“批准”会映射到 EHR 的“同意 + 提交”。">
                <Stack spacing={2}>
                  <Alert severity="warning">
                    本操作会真实写回 EHR。当前实现会自动打开目标单据的 `任务处理`，将 `审批决策` 设为 `同意`，把下方审批意见写入 EHR 后点击 `提交`。
                  </Alert>

                  <KeyValueList
                    items={[
                      { label: "单据编号", value: selectedDocumentNo || "-", hint: "当前将对该单据执行审批动作。" },
                      { label: "权限对象", value: selectedDocumentRow?.permissionTarget ?? "-", hint: "来自处理单据主表。" },
                      {
                        label: "当前总结论",
                        value: selectedDocumentRow?.summaryConclusionLabel ?? "-",
                        hint: "展示层沿用 104 方案结论文案。",
                      },
                      {
                        label: "建议动作",
                        value: selectedDocumentRow?.suggestedActionLabel ?? "-",
                        hint: "仅作参考，不自动替代真实审批动作。",
                      },
                      { label: "EHR 审批决策", value: "同意", hint: "后端执行时固定选择该决策值。" },
                      { label: "EHR 执行按钮", value: "提交", hint: "EHR 实页执行按钮文案。前端按钮文案仍显示“批准”。" },
                    ]}
                  />

                  <TextField
                    label="审批意见"
                    multiline
                    minRows={4}
                    value={approvalOpinion}
                    onChange={(event) => setApprovalOpinion(event.target.value)}
                    disabled={!selectedDocumentNo || approvalSubmittingMode !== null}
                    placeholder="请输入要带到 EHR 的审批意见。"
                  />

                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                    <Button
                      variant="contained"
                      disableElevation
                      disabled={!selectedDocumentNo || approvalSubmittingMode !== null || !approvalOpinion.trim()}
                      onClick={() => void runApproval(false)}
                    >
                      {approvalSubmittingMode === "approve" ? "批准中..." : "批准"}
                    </Button>
                    <Button
                      variant="outlined"
                      disabled={!selectedDocumentNo || approvalSubmittingMode !== null || !approvalOpinion.trim()}
                      onClick={() => void runApproval(true)}
                    >
                      {approvalSubmittingMode === "dryRun" ? "验证中..." : "验证连通性（dry-run）"}
                    </Button>
                  </Stack>

                  {approvalError ? <Alert severity="error">{approvalError}</Alert> : null}

                  {approvalResult ? (
                    <Stack spacing={1.5}>
                      <Alert severity={approvalResult.dryRun ? "info" : "success"}>{approvalResult.message}</Alert>
                      <KeyValueList
                        items={[
                          { label: "执行状态", value: approvalResult.status, hint: approvalResult.dryRun ? "当前只做连通性验证，不点击提交。" : "已按返回结果完成执行。" },
                          { label: "开始时间", value: approvalResult.startedAt || "-", hint: "后端开始执行审批的时间。" },
                          { label: "结束时间", value: approvalResult.finishedAt || "-", hint: "后端完成执行或返回结果的时间。" },
                          { label: "EHR 决策", value: approvalResult.ehrDecision || "-", hint: "当前固定为“同意”。" },
                          { label: "EHR 提交按钮", value: approvalResult.ehrSubmitLabel || "-", hint: "实际点击的 EHR 页面按钮文案。" },
                          { label: "日志文件", value: approvalResult.logFile || "-", hint: "审批执行 JSON 日志，可用于排障。" },
                          {
                            label: "异常截图",
                            value: approvalResult.screenshotFile || "-",
                            hint: approvalResult.screenshotFile ? "失败时自动抓取。" : "本次执行未产生异常截图。",
                          },
                        ]}
                      />
                    </Stack>
                  ) : null}
                </Stack>
              </SectionCard>
            ) : null}

            {detail && activeTab === "lowScoreDetails" ? (
              <AppDataGrid<RiskDetailRow>
                title="原始低分明细"
                subtitle="保留原始 `<= 1.0` 明细作为审计与回放证据；默认用户视角请查看“风险总览”。"
                rows={detailRiskDetails}
                columns={riskColumns}
                loading={detailLoading}
                rowCount={detailRiskDetails.length}
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
              <AppDataGrid<RoleRow>
                title="申请角色"
                subtitle="按角色维度展示明细行号、权限级别、申请类型与组织范围数量。"
                rows={detailRoles}
                columns={roleColumns}
                loading={detailLoading}
                rowCount={detailRoles.length}
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
              <AppDataGrid<OrgScopeRow>
                title="目标组织"
                subtitle="结合 013 与 104 方案查看角色、组织、组织单位与物理层级。"
                rows={detailOrgScopes}
                columns={orgScopeColumns}
                loading={detailLoading}
                rowCount={detailOrgScopes.length}
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
              <AppDataGrid<ApprovalRow>
                title="审批记录"
                subtitle="展示当前审批轨迹，后续审批动作页可继续复用这里的数据结构。"
                rows={detailApprovals}
                columns={approvalColumns}
                loading={detailLoading}
                rowCount={detailApprovals.length}
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
