import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import type { GridColDef, GridRowParams } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type {
  ApprovalRow,
  DistributionSection,
  OrgScopeRow,
  ProcessDashboard,
  ProcessDetail,
  ProcessDocumentRow,
  ProcessExecutionLogRow,
  RiskDetailRow,
  RoleRow,
  Tone,
} from "../types/dashboard";

type DetailTab = "overview" | "lowScoreDetails" | "roles" | "orgScopes" | "approvals";

const documentStatusTone: Record<string, Tone> = {
  已提交: "warning",
  已完成: "success",
  已驳回: "danger",
  待处理: "warning",
};

const conclusionTone: Record<string, Tone> = {
  拒绝: "danger",
  人工干预: "warning",
  仅关注: "info",
  可信任: "success",
};

const actionTone: Record<string, Tone> = {
  reject: "danger",
  manual_review: "warning",
  warning: "info",
  trust: "success",
};

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

function getDistributionTone(sectionId: string, label: string): Tone {
  if (sectionId === "summary-conclusion") {
    return conclusionTone[label] ?? "default";
  }
  if (sectionId === "score-distribution") {
    return getScoreTone(Number(label));
  }
  return "default";
}

function isProcessDashboardResponse(value: unknown): value is ProcessDashboard {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ProcessDashboard>;
  return (
    Array.isArray(candidate.stats) &&
    Array.isArray(candidate.documents) &&
    Array.isArray(candidate.distributionSections) &&
    Array.isArray(candidate.executionLogs) &&
    "latestBatch" in candidate
  );
}

function isProcessDetailResponse(value: unknown): value is ProcessDetail {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ProcessDetail>;
  return (
    typeof candidate.documentNo === "string" &&
    Array.isArray(candidate.overviewFields) &&
    Array.isArray(candidate.roles) &&
    Array.isArray(candidate.approvals) &&
    Array.isArray(candidate.orgScopes) &&
    Array.isArray(candidate.riskDetails) &&
    Array.isArray(candidate.notes)
  );
}

const documentColumns: GridColDef<ProcessDocumentRow>[] = [
  { field: "documentNo", headerName: "单据编号", minWidth: 180, flex: 1.1 },
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
        label={String(params.value ?? "")}
        tone={conclusionTone[String(params.value)] ?? "default"}
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
    headerName: "低分条数",
    minWidth: 100,
    type: "number",
  },
  { field: "assessedAt", headerName: "评估时间", minWidth: 170 },
];

const roleColumns: GridColDef<RoleRow>[] = [
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 220, flex: 1.2 },
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

const executionLogColumns: GridColDef<ProcessExecutionLogRow>[] = [
  { field: "batchNo", headerName: "批次号", minWidth: 180, flex: 1 },
  { field: "assessmentVersion", headerName: "版本", minWidth: 100 },
  { field: "executedAt", headerName: "执行时间", minWidth: 170 },
  { field: "documentCount", headerName: "单据数", minWidth: 90, type: "number" },
  { field: "detailCount", headerName: "明细数", minWidth: 90, type: "number" },
  {
    field: "persistedToDatabase",
    headerName: "落库状态",
    minWidth: 110,
    renderCell: (params) => (
      <StatusTag label={params.value ? "已落库" : "仅日志"} tone={params.value ? "success" : "info"} />
    ),
  },
  { field: "sampleDocumentNo", headerName: "样例单据", minWidth: 160 },
  { field: "sourceFile", headerName: "日志文件", minWidth: 240, flex: 1.2 },
];

const detailTabs: Array<{ value: DetailTab; label: string }> = [
  { value: "overview", label: "风险总览" },
  { value: "lowScoreDetails", label: "低分明细" },
  { value: "roles", label: "申请角色" },
  { value: "orgScopes", label: "目标组织" },
  { value: "approvals", label: "审批记录" },
];

function DistributionSectionCard({ section }: { section: DistributionSection }) {
  return (
    <SectionCard title={section.title} subtitle={section.subtitle}>
      <Stack spacing={1.25}>
        {section.items.map((item) => (
          <Box
            key={item.id}
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 2,
              px: 1.5,
              py: 1.25,
              border: "1px solid",
              borderColor: "divider",
              backgroundColor: "rgba(255,255,255,0.68)",
            }}
          >
            <Typography variant="body2">{item.label}</Typography>
            <StatusTag label={`${item.count} 条`} tone={getDistributionTone(section.id, item.label)} />
          </Box>
        ))}
      </Stack>
    </SectionCard>
  );
}

export function ProcessDocumentsPage() {
  const [dashboard, setDashboard] = useState<ProcessDashboard | null>(null);
  const [detail, setDetail] = useState<ProcessDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [selectedDocumentNo, setSelectedDocumentNo] = useState("");
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");

  const dashboardStats = dashboard?.stats ?? [];
  const dashboardDocuments = dashboard?.documents ?? [];
  const dashboardDistributionSections = dashboard?.distributionSections ?? [];
  const dashboardExecutionLogs = dashboard?.executionLogs ?? [];
  const detailOverviewFields = detail?.overviewFields ?? [];
  const detailNotes = detail?.notes ?? [];
  const detailRiskDetails = detail?.riskDetails ?? [];
  const detailRoles = detail?.roles ?? [];
  const detailOrgScopes = detail?.orgScopes ?? [];
  const detailApprovals = detail?.approvals ?? [];

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getProcessDashboard()) as unknown;
        if (!isProcessDashboardResponse(response)) {
          throw new Error(
            "处理单据接口返回的不是 200 方案正式结构。请重启 FastAPI 服务，确保 `/documents/process-dashboard` 已切换到 PostgreSQL 实时接口。",
          );
        }
        if (!active) {
          return;
        }

        setDashboard(response);
        setSelectedDocumentNo((currentValue) => {
          if (currentValue && response.documents.some((item) => item.documentNo === currentValue)) {
            return currentValue;
          }
          return response.documents[0]?.documentNo ?? "";
        });
        setError(null);
      } catch (loadError) {
        if (active) {
          setDashboard(null);
          setSelectedDocumentNo("");
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
  }, []);

  useEffect(() => {
    if (!selectedDocumentNo) {
      setDetail(null);
      setDetailError(null);
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
            "单据详情接口返回的不是 200 方案正式结构。请重启 FastAPI 服务，确保 `/documents/process-dashboard/{documentNo}` 已切换到 PostgreSQL 实时查询。",
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
            setDetailError(`当前评估批次未返回单据 ${selectedDocumentNo} 的详情。请确认该单据已完成评估并成功落库。`);
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
  }, [selectedDocumentNo]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          当前处理单据页只接受 `200` 方案正式接口，直接读取 PostgreSQL 最新评估批次，展示单据级总结论、低分明细、批次分布与最近执行日志。
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
        {dashboardStats.map((item) => (
          <StatCard key={item.label} item={item} />
        ))}
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.5fr) minmax(420px, 1fr)" },
          gap: 2,
        }}
      >
        <AppDataGrid<ProcessDocumentRow>
          title="待处理单据列表"
          subtitle="主表展示最新批次的单据级总结论；点击后在右侧查看风险总览、低分明细与联查结果。"
          rows={dashboardDocuments}
          columns={documentColumns}
          loading={loading}
          rowCount={dashboardDocuments.length}
          onRowClick={(params: GridRowParams<ProcessDocumentRow>) => {
            setSelectedDocumentNo(params.row.documentNo);
            setActiveTab("overview");
          }}
          initialState={{
            sorting: {
              sortModel: [{ field: "finalScore", sort: "asc" }],
            },
            pagination: {
              paginationModel: {
                pageSize: 10,
                page: 0,
              },
            },
          }}
        />

        <Stack spacing={2}>
          <Paper
            elevation={0}
            sx={{
              p: { xs: 2, md: 2.5 },
              border: "1px solid",
              borderColor: "divider",
              background: "linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(248,250,252,0.92) 100%)",
            }}
          >
            <Typography variant="h6">
              {selectedDocumentNo ? `单据详情：${selectedDocumentNo}` : "单据详情"}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
              右侧详情按 `200` 方案固定为风险总览、低分明细、申请角色、目标组织、审批记录五个页签。
            </Typography>

            <Tabs
              value={activeTab}
              onChange={(_, value: DetailTab) => setActiveTab(value)}
              variant="fullWidth"
              sx={{
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
          </Paper>

          {detailError ? <Alert severity="error">{detailError}</Alert> : null}

          {!selectedDocumentNo && !loading ? (
            <SectionCard title="暂无单据" subtitle="当前没有可查看的评估结果。">
              <Typography variant="body2" color="text.secondary">
                请先执行 `audit`，并确认最新评估批次已成功写入 `申请单风险信任评估`。
              </Typography>
            </SectionCard>
          ) : null}

          {detailLoading ? (
            <SectionCard title="加载中" subtitle="正在读取单据详情。">
              <Typography variant="body2" color="text.secondary">
                正在从 PostgreSQL 读取该单据的低分明细、组织范围与审批记录。
              </Typography>
            </SectionCard>
          ) : null}

          {detail && activeTab === "overview" ? (
            <SectionCard title="风险总览" subtitle="单据级结论、低分汇总与评估说明。">
              <KeyValueList items={detailOverviewFields} />
              <Typography variant="subtitle2" sx={{ mt: 2.5 }}>
                处理提示
              </Typography>
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                {detailNotes.map((item, index) => (
                  <Typography key={`${index}-${item}`} variant="body2" color="text.secondary">
                    • {item}
                  </Typography>
                ))}
              </Stack>
            </SectionCard>
          ) : null}

          {detail && activeTab === "lowScoreDetails" ? (
            <AppDataGrid<RiskDetailRow>
              title="低分明细"
              subtitle="仅展示低分明细，便于快速查看当前单据的主要风险来源。"
              rows={detailRiskDetails}
              columns={riskColumns}
              loading={detailLoading}
              rowCount={detailRiskDetails.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 10,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}

          {detail && activeTab === "roles" ? (
            <AppDataGrid<RoleRow>
              title="申请角色"
              subtitle="按角色维度展示申请类型、组织范围数量与组织范围例外。"
              rows={detailRoles}
              columns={roleColumns}
              loading={detailLoading}
              rowCount={detailRoles.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 10,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}

          {detail && activeTab === "orgScopes" ? (
            <AppDataGrid<OrgScopeRow>
              title="目标组织"
              subtitle="结合 013 方案查看角色与组织展开结果。"
              rows={detailOrgScopes}
              columns={orgScopeColumns}
              loading={detailLoading}
              rowCount={detailOrgScopes.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 10,
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
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 10,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}
        </Stack>
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.05fr) minmax(0, 1.2fr)" },
          gap: 2,
        }}
      >
        <Stack spacing={2}>
          {dashboard?.latestBatch ? (
            <SectionCard title="最新评估批次" subtitle="处理单据页当前默认读取该批次。">
              <KeyValueList
                items={[
                  { label: "批次号", value: dashboard.latestBatch.batchNo, hint: "来自评估总表最新批次。" },
                  { label: "评估版本", value: dashboard.latestBatch.assessmentVersion, hint: "与 YAML 规则版本保持一致。" },
                  { label: "单据数", value: String(dashboard.latestBatch.documentCount), hint: "本批次评估到的单据数。" },
                  { label: "明细数", value: String(dashboard.latestBatch.detailCount), hint: "总明细条数，包含非低分项。" },
                  {
                    label: "低分明细数",
                    value: String(dashboard.latestBatch.lowScoreDetailCount),
                    hint: "所有单据低分明细条数汇总。",
                  },
                  { label: "评估时间", value: dashboard.latestBatch.assessedAt, hint: "最近一次成功写入该批次的时间。" },
                ]}
              />
            </SectionCard>
          ) : (
            <SectionCard title="最新评估批次" subtitle="当前未读取到批次摘要。">
              <Typography variant="body2" color="text.secondary">
                请先执行 `audit`，并确认结果已成功写入 PostgreSQL 后再刷新页面。
              </Typography>
            </SectionCard>
          )}

          {dashboardDistributionSections.map((section) => (
            <DistributionSectionCard key={section.id} section={section} />
          ))}
        </Stack>

        <AppDataGrid<ProcessExecutionLogRow>
          title="最近执行日志"
          subtitle="扫描 `automation/logs/audit_*.json`，用于区分“已落库批次”和“仅日志结果 / dry-run”。"
          rows={dashboardExecutionLogs}
          columns={executionLogColumns}
          loading={loading}
          rowCount={dashboardExecutionLogs.length}
          minHeight={540}
          initialState={{
            pagination: {
              paginationModel: {
                pageSize: 6,
                page: 0,
              },
            },
          }}
        />
      </Box>
    </Stack>
  );
}
