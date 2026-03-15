import { useEffect, useState } from "react";
import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import type { GridColDef, GridRowParams } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type {
  CollectDashboard,
  CollectDocumentRow,
  TableStatusRow,
  Tone,
} from "../types/dashboard";

const collectStatusTone: Record<string, Tone> = {
  已采集: "success",
  待补采: "warning",
};

const tableStatusTone: Record<string, Tone> = {
  已落库: "success",
  待补采: "warning",
};

const documentColumns: GridColDef<CollectDocumentRow>[] = [
  { field: "documentNo", headerName: "单据编号", minWidth: 180, flex: 1.2 },
  { field: "applicantName", headerName: "申请人", minWidth: 110 },
  { field: "applicantNo", headerName: "工号", minWidth: 90 },
  { field: "subject", headerName: "申请主题", minWidth: 220, flex: 1.4 },
  {
    field: "documentStatus",
    headerName: "采集状态",
    minWidth: 120,
    renderCell: (params) => (
      <StatusTag label={String(params.value ?? "")} tone={collectStatusTone[String(params.value)] ?? "default"} />
    ),
  },
  { field: "collectedAt", headerName: "采集时间", minWidth: 150 },
  { field: "roleCount", headerName: "角色数", minWidth: 90, type: "number" },
  { field: "approvalCount", headerName: "审批记录", minWidth: 100, type: "number" },
];

const tableColumns: GridColDef<TableStatusRow>[] = [
  { field: "tableName", headerName: "目标表", minWidth: 180, flex: 1.1 },
  {
    field: "status",
    headerName: "状态",
    minWidth: 110,
    renderCell: (params) => (
      <StatusTag label={String(params.value ?? "")} tone={tableStatusTone[String(params.value)] ?? "default"} />
    ),
  },
  { field: "records", headerName: "记录数", minWidth: 90, type: "number" },
  { field: "updatedAt", headerName: "更新时间", minWidth: 150 },
  { field: "remark", headerName: "备注", minWidth: 220, flex: 1.2 },
];

export function CollectDocumentsPage() {
  const [data, setData] = useState<CollectDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDocumentNo, setSelectedDocumentNo] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getCollectDashboard();
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
        <Typography variant="body1">围绕 4 张申请单表设计统一采集入口、批次状态与单据详情联动查询。</Typography>
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
          gridTemplateColumns: { xs: "1fr", xl: "repeat(4, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(data?.scopes ?? []).map((scope) => (
          <SectionCard key={scope.id} title={scope.title} subtitle={scope.status}>
            <Typography variant="body2" color="text.secondary">
              {scope.description}
            </Typography>
            <Typography variant="subtitle2" sx={{ mt: 2 }}>
              当前口径
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {scope.command}
            </Typography>
            <Button variant="outlined" sx={{ mt: 2 }}>
              {scope.buttonLabel}
            </Button>
          </SectionCard>
        ))}
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.6fr) minmax(360px, 1fr)" },
          gap: 2,
        }}
      >
        <AppDataGrid
          title="采集单据列表"
          subtitle="点击单据后，在右侧查看四张表的采集落库情况。"
          rows={data?.documents ?? []}
          columns={documentColumns}
          loading={loading}
          rowCount={data?.documents.length ?? 0}
          onRowClick={(params: GridRowParams<CollectDocumentRow>) => setSelectedDocumentNo(params.row.documentNo)}
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
          <SectionCard
            title={selectedDocumentNo ? `单据详情：${selectedDocumentNo}` : "单据详情"}
            subtitle="单据号联动详情区域，不依赖 DataGridPro master-detail。"
          >
            {detail ? (
              <>
                <KeyValueList items={detail.basicInfo} />
                <Typography variant="subtitle2" sx={{ mt: 2.5 }}>
                  下一步建议
                </Typography>
                <Stack spacing={1} sx={{ mt: 1.5 }}>
                  {detail.nextActions.map((item) => (
                    <Typography key={item} variant="body2" color="text.secondary">
                      • {item}
                    </Typography>
                  ))}
                </Stack>
              </>
            ) : (
              <Typography variant="body2" color="text.secondary">
                请选择左侧单据查看详情。
              </Typography>
            )}
          </SectionCard>

          <AppDataGrid
            title="四张表落库状态"
            subtitle="当前示意数据与后续真实链路结构保持一致。"
            rows={detail?.tableStatus ?? []}
            columns={tableColumns}
            loading={loading}
            rowCount={detail?.tableStatus.length ?? 0}
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
      </Box>
    </Stack>
  );
}
