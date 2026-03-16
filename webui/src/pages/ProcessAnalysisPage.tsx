import { useEffect, useState } from "react";
import { Alert, Box, Stack, Typography } from "@mui/material";
import type { GridColDef } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatusTag } from "../components/StatusTag";
import { dashboardApi } from "../services/api";
import type {
  DistributionSection,
  ProcessAnalysisDashboard,
  ProcessExecutionLogRow,
  Tone,
} from "../types/dashboard";

function formatScoreLabel(scoreLabel: string): number | null {
  const score = Number(scoreLabel);
  if (Number.isNaN(score)) {
    return null;
  }
  return score;
}

function getScoreTone(score: number | null): Tone {
  if (score === null) {
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

function getDisplaySummaryConclusion(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value === "人工干预" ? "加强审核" : value;
}

function getDistributionTone(sectionId: string, label: string): Tone {
  if (sectionId === "summary-conclusion") {
    const conclusionTone: Record<string, Tone> = {
      拒绝: "danger",
      人工干预: "warning",
      加强审核: "warning",
      仅关注: "info",
      可信任: "success",
    };
    return conclusionTone[label] ?? "default";
  }
  if (sectionId === "score-distribution") {
    return getScoreTone(formatScoreLabel(label));
  }
  return "default";
}

function isProcessAnalysisDashboardResponse(value: unknown): value is ProcessAnalysisDashboard {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ProcessAnalysisDashboard>;
  return (
    Array.isArray(candidate.distributionSections) &&
    Array.isArray(candidate.executionLogs) &&
    "latestBatch" in candidate
  );
}

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
            <Typography variant="body2">{getDisplaySummaryConclusion(item.label)}</Typography>
            <StatusTag label={`${item.count} 条`} tone={getDistributionTone(section.id, item.label)} />
          </Box>
        ))}
      </Stack>
    </SectionCard>
  );
}

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

export function ProcessAnalysisPage() {
  const [dashboard, setDashboard] = useState<ProcessAnalysisDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = (await dashboardApi.getProcessAnalysisDashboard()) as unknown;
        if (!isProcessAnalysisDashboardResponse(response)) {
          throw new Error(
            "评估分析接口返回的不是 201 方案正式结构。请重启 FastAPI 服务，确保 `/documents/process-analysis` 已切换到 PostgreSQL 实时接口。",
          );
        }
        if (!active) {
          return;
        }

        setDashboard(response);
        setError(null);
      } catch (loadError) {
        if (active) {
          setDashboard(null);
          setError(loadError instanceof Error ? loadError.message : "加载评估分析页失败");
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
          当前页面集中承接最新评估批次、总结论分布、分数分布、低分热点和执行日志，不再与单据处理工作台混放。
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

      {dashboard?.latestBatch ? (
        <SectionCard title="最新评估批次" subtitle="处理单据工作台当前默认读取该批次。">
          <KeyValueList
            items={[
              { label: "批次号", value: dashboard.latestBatch.batchNo, hint: "来自评估总表最新批次。" },
              { label: "评估版本", value: dashboard.latestBatch.assessmentVersion, hint: "与 YAML 规则版本保持一致。" },
              { label: "单据数", value: String(dashboard.latestBatch.documentCount), hint: "本批次评估到的单据数。" },
              { label: "明细数", value: String(dashboard.latestBatch.detailCount), hint: "总明细条数，包含非低分项。" },
              {
                label: "原始低分明细数",
                value: String(dashboard.latestBatch.lowScoreDetailCount),
                hint: "所有单据原始低分明细条数汇总，不等于风险类型数。",
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

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(dashboard?.distributionSections ?? []).map((section) => (
          <DistributionSectionCard key={section.id} section={section} />
        ))}
      </Box>

      <AppDataGrid<ProcessExecutionLogRow>
        title="最近执行日志"
        subtitle="扫描 `automation/logs/audit_*.json`，用于区分“已落库批次”和“仅日志结果 / dry-run”。"
        rows={dashboard?.executionLogs ?? []}
        columns={executionLogColumns}
        loading={loading}
        rowCount={dashboard?.executionLogs.length ?? 0}
        minHeight={920}
        pageSizeOptions={[20, 50]}
        initialState={{
          pagination: {
            paginationModel: {
              pageSize: 20,
              page: 0,
            },
          },
        }}
      />
    </Stack>
  );
}
