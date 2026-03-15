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
  OrgScopeRow,
  ProcessDashboard,
  ProcessDocumentRow,
  RiskDetailRow,
  RoleRow,
  Tone,
} from "../types/dashboard";

type DetailTab = "basic" | "roles" | "approvals" | "orgScopes" | "risk";

const documentStatusTone: Record<string, Tone> = {
  待处理: "warning",
  待补功能: "info",
};

const riskTone: Record<string, Tone> = {
  低: "success",
  中: "warning",
  高: "danger",
};

const trustTone: Record<string, Tone> = {
  低: "danger",
  中: "warning",
  高: "success",
};

const recommendationTone: Record<string, Tone> = {
  建议审批: "success",
  建议复核: "warning",
  "等待 103 功能补齐": "info",
};

const documentColumns: GridColDef<ProcessDocumentRow>[] = [
  { field: "documentNo", headerName: "单据编号", minWidth: 180, flex: 1.2 },
  { field: "applicantName", headerName: "申请人", minWidth: 110 },
  { field: "department", headerName: "部门", minWidth: 180, flex: 1.1 },
  {
    field: "documentStatus",
    headerName: "处理状态",
    minWidth: 120,
    renderCell: (params) => (
      <StatusTag label={String(params.value ?? "")} tone={documentStatusTone[String(params.value)] ?? "default"} />
    ),
  },
  {
    field: "riskLevel",
    headerName: "风险",
    minWidth: 90,
    renderCell: (params) => <StatusTag label={String(params.value ?? "")} tone={riskTone[String(params.value)] ?? "default"} />,
  },
  {
    field: "trustLevel",
    headerName: "信任",
    minWidth: 90,
    renderCell: (params) => <StatusTag label={String(params.value ?? "")} tone={trustTone[String(params.value)] ?? "default"} />,
  },
  {
    field: "recommendation",
    headerName: "建议",
    minWidth: 150,
    renderCell: (params) => (
      <StatusTag label={String(params.value ?? "")} tone={recommendationTone[String(params.value)] ?? "default"} />
    ),
  },
  { field: "submittedAt", headerName: "申请时间", minWidth: 150 },
];

const roleColumns: GridColDef<RoleRow>[] = [
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 180, flex: 1.2 },
  { field: "applyType", headerName: "申请类型", minWidth: 100 },
  { field: "orgScopeCount", headerName: "组织范围数", minWidth: 110, type: "number" },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const approvalColumns: GridColDef<ApprovalRow>[] = [
  { field: "nodeName", headerName: "节点", minWidth: 120 },
  { field: "approver", headerName: "审批人", minWidth: 110 },
  { field: "action", headerName: "动作", minWidth: 90 },
  { field: "finishedAt", headerName: "完成时间", minWidth: 150 },
  { field: "comment", headerName: "审批意见", minWidth: 220, flex: 1.2 },
];

const orgScopeColumns: GridColDef<OrgScopeRow>[] = [
  { field: "roleCode", headerName: "角色编码", minWidth: 130 },
  { field: "roleName", headerName: "角色名称", minWidth: 160, flex: 1.1 },
  { field: "organizationCode", headerName: "组织编码", minWidth: 120 },
  { field: "organizationName", headerName: "组织名称", minWidth: 180, flex: 1.2 },
  { field: "skipOrgScopeCheck", headerName: "跳过组织范围", minWidth: 130 },
];

const riskColumns: GridColDef<RiskDetailRow>[] = [
  { field: "ruleCode", headerName: "规则编码", minWidth: 110 },
  { field: "ruleName", headerName: "规则名称", minWidth: 180, flex: 1.1 },
  { field: "result", headerName: "命中结果", minWidth: 100 },
  {
    field: "riskLevel",
    headerName: "风险",
    minWidth: 90,
    renderCell: (params) => <StatusTag label={String(params.value ?? "")} tone={riskTone[String(params.value)] ?? "default"} />,
  },
  {
    field: "trustLevel",
    headerName: "信任",
    minWidth: 90,
    renderCell: (params) => <StatusTag label={String(params.value ?? "")} tone={trustTone[String(params.value)] ?? "default"} />,
  },
  { field: "hitDetail", headerName: "命中详情", minWidth: 260, flex: 1.6 },
];

const detailTabs: Array<{ value: DetailTab; label: string }> = [
  { value: "basic", label: "基本信息" },
  { value: "roles", label: "权限明细" },
  { value: "approvals", label: "审批记录" },
  { value: "orgScopes", label: "组织范围" },
  { value: "risk", label: "风险明细" },
];

export function ProcessDocumentsPage() {
  const [data, setData] = useState<ProcessDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocumentNo, setSelectedDocumentNo] = useState("");
  const [activeTab, setActiveTab] = useState<DetailTab>("basic");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getProcessDashboard();
        if (active) {
          setData(response);
          setSelectedDocumentNo(response.documents[0]?.documentNo ?? "");
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

  const detail = selectedDocumentNo ? data?.detailsByDocumentNo[selectedDocumentNo] : null;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">使用单据列表 + 顶部卡片式页签联动详情，不引入 DataGridPro master-detail。</Typography>
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
          gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.45fr) minmax(420px, 1fr)" },
          gap: 2,
        }}
      >
        <AppDataGrid
          title="待处理单据列表"
          subtitle="主表点击后，通过右侧详情页签查看基本信息、明细、审批记录与评估结果。"
          rows={data?.documents ?? []}
          columns={documentColumns}
          loading={loading}
          rowCount={data?.documents.length ?? 0}
          onRowClick={(params: GridRowParams<ProcessDocumentRow>) => {
            setSelectedDocumentNo(params.row.documentNo);
            setActiveTab("basic");
          }}
          initialState={{
            pagination: {
              paginationModel: {
                pageSize: 5,
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
              顶部页签采用矩形卡片风格，文本居中，避免胶囊感。
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

          {detail && activeTab === "basic" ? (
            <SectionCard title="基本信息" subtitle="用于承接 103 风险与信任度评估之后的审批建议。">
              <KeyValueList items={detail.basicInfo} />
              <Typography variant="subtitle2" sx={{ mt: 2.5 }}>
                处理提示
              </Typography>
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                {detail.notes.map((item) => (
                  <Typography key={item} variant="body2" color="text.secondary">
                    • {item}
                  </Typography>
                ))}
              </Stack>
            </SectionCard>
          ) : null}

          {detail && activeTab === "roles" ? (
            <AppDataGrid
              title="权限明细"
              subtitle="按角色维度展示申请类型、组织范围数量与组织范围例外。"
              rows={detail.roles}
              columns={roleColumns}
              loading={loading}
              rowCount={detail.roles.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 5,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}

          {detail && activeTab === "approvals" ? (
            <AppDataGrid
              title="审批记录"
              subtitle="展示当前审批轨迹，后续可在此处接入审批 / 驳回 / 加签入口。"
              rows={detail.approvals}
              columns={approvalColumns}
              loading={loading}
              rowCount={detail.approvals.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 5,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}

          {detail && activeTab === "orgScopes" ? (
            <AppDataGrid
              title="组织范围"
              subtitle="结合 013 方案查看角色与组织展开结果。"
              rows={detail.orgScopes}
              columns={orgScopeColumns}
              loading={loading}
              rowCount={detail.orgScopes.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 5,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}

          {detail && activeTab === "risk" ? (
            <AppDataGrid
              title="风险与信任度评估"
              subtitle="当前仅展示评估结果与建议，后续与 103 页面动作联动。"
              rows={detail.riskDetails}
              columns={riskColumns}
              loading={loading}
              rowCount={detail.riskDetails.length}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 5,
                    page: 0,
                  },
                },
              }}
            />
          ) : null}
        </Stack>
      </Box>
    </Stack>
  );
}
