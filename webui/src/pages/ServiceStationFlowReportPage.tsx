import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import type { GridColDef } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { dashboardApi } from "../services/api";
import type {
  ServiceStationFlowCategoryRow,
  ServiceStationFlowDetailRow,
  ServiceStationFlowOptions,
  ServiceStationFlowReportResult,
  ServiceStationFlowZoneRow,
  StatItem,
} from "../types/dashboard";

const categoryColumns: GridColDef<ServiceStationFlowCategoryRow>[] = [
  { field: "category", headerName: "分类", minWidth: 220, flex: 1 },
  { field: "count", headerName: "人数", minWidth: 100, type: "number" },
];

const zoneColumns: GridColDef<ServiceStationFlowZoneRow>[] = [
  { field: "warZone", headerName: "战区", minWidth: 120, flex: 0.8 },
  { field: "startOperationsCount", headerName: "人事运营期初", minWidth: 120, type: "number" },
  { field: "endOperationsCount", headerName: "人事运营期末", minWidth: 120, type: "number" },
  { field: "operationsDelta", headerName: "人事运营增减", minWidth: 120, type: "number" },
  { field: "startRecruitCount", headerName: "招聘期初", minWidth: 110, type: "number" },
  { field: "endRecruitCount", headerName: "招聘期末", minWidth: 110, type: "number" },
  { field: "recruitDelta", headerName: "招聘增减", minWidth: 110, type: "number" },
  { field: "startTotalCount", headerName: "合计期初", minWidth: 100, type: "number" },
  { field: "endTotalCount", headerName: "合计期末", minWidth: 100, type: "number" },
  { field: "totalDelta", headerName: "合计增减", minWidth: 100, type: "number" },
  { field: "leftCount", headerName: "离职", minWidth: 90, type: "number" },
  { field: "otherHrOutCount", headerName: "转其他HR", minWidth: 110, type: "number" },
  { field: "otherHrInCount", headerName: "其他HR转入", minWidth: 120, type: "number" },
  { field: "opsToRecruitCount", headerName: "人事运营转招聘", minWidth: 140, type: "number" },
  { field: "recruitToOpsCount", headerName: "招聘转人事运营", minWidth: 140, type: "number" },
];

const detailColumns: GridColDef<ServiceStationFlowDetailRow>[] = [
  { field: "employeeNo", headerName: "工号", minWidth: 100 },
  { field: "employeeName", headerName: "姓名", minWidth: 100 },
  { field: "startSubdomain", headerName: "期初子域", minWidth: 140 },
  { field: "startWarZone", headerName: "期初战区", minWidth: 120 },
  { field: "startOrgUnitName", headerName: "期初组织单位", minWidth: 160 },
  { field: "startDepartmentId", headerName: "期初部门ID", minWidth: 120 },
  { field: "startPositionName", headerName: "期初职位名称", minWidth: 180, flex: 1 },
  { field: "startStandardPositionName", headerName: "期初标准岗位", minWidth: 180, flex: 1 },
  { field: "startHrType", headerName: "期初HR类型", minWidth: 120 },
  { field: "movementType", headerName: "分类", minWidth: 180 },
  { field: "endSubdomain", headerName: "期末子域", minWidth: 140 },
  { field: "endWarZone", headerName: "期末战区", minWidth: 120 },
  { field: "endOrgUnitName", headerName: "期末组织单位", minWidth: 160 },
  { field: "endDepartmentId", headerName: "期末部门ID", minWidth: 120 },
  { field: "endPositionName", headerName: "期末职位名称", minWidth: 180, flex: 1 },
  { field: "endStandardPositionName", headerName: "期末标准岗位", minWidth: 180, flex: 1 },
  { field: "endHrType", headerName: "期末HR类型", minWidth: 120 },
];

function buildSummaryStats(result: ServiceStationFlowReportResult): StatItem[] {
  return [
    {
      label: "期初目标岗位人数",
      value: String(result.summary.startTargetCount),
      hint: `${result.startDate} 快照中 HR子域=服务站-人事运营/服务站-招聘`,
      tone: "info",
    },
    {
      label: "期末目标岗位人数",
      value: String(result.summary.endTargetCount),
      hint: `${result.endDate} 快照中 HR子域=服务站-人事运营/服务站-招聘`,
      tone: "info",
    },
    {
      label: "离职人数",
      value: String(result.summary.leftCount),
      hint: `期初在目标岗位，期末按工号找不到`,
      tone: "danger",
    },
    {
      label: "转其他HR人数",
      value: String(result.summary.otherHrOutCount),
      hint: `期末不在目标岗位，但 HR类型仍属于 H*`,
      tone: "warning",
    },
    {
      label: "目标岗位内互转人数",
      value: String(result.summary.targetSwitchCount),
      hint: `服务站-人事运营 与 服务站-招聘 之间互转`,
      tone: "success",
    },
    {
      label: "其他HR转入人数",
      value: String(result.summary.otherHrInCount),
      hint: `期末在目标岗位，期初来自其他 HR 岗位`,
      tone: "success",
    },
  ];
}

export function ServiceStationFlowReportPage() {
  const [options, setOptions] = useState<ServiceStationFlowOptions | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loadingResult, setLoadingResult] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<ServiceStationFlowReportResult | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [saveAsPath, setSaveAsPath] = useState("");
  const [detailTab, setDetailTab] = useState("zone");

  useEffect(() => {
    let active = true;

    async function loadOptions() {
      try {
        setLoadingOptions(true);
        const response = await dashboardApi.getServiceStationFlowOptions();
        if (active) {
          setOptions(response);
          setStartDate((currentValue) => currentValue || response.defaultStartDate || "");
          setEndDate((currentValue) => currentValue || response.defaultEndDate || "");
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setOptions(null);
          setError(loadError instanceof Error ? loadError.message : "加载报表参数失败");
        }
      } finally {
        if (active) {
          setLoadingOptions(false);
        }
      }
    }

    void loadOptions();
    return () => {
      active = false;
    };
  }, []);

  const summaryStats = useMemo(() => (result ? buildSummaryStats(result) : []), [result]);

  async function runQuery() {
    try {
      setLoadingResult(true);
      setError(null);
      setNotice(null);
      const response = await dashboardApi.queryServiceStationFlowReport({
        startDate,
        endDate,
        saveAsPath: "",
      });
      setResult(response);
    } catch (queryError) {
      setError(queryError instanceof Error ? queryError.message : "查询失败");
    } finally {
      setLoadingResult(false);
    }
  }

  async function exportWorkbook() {
    try {
      setExporting(true);
      setError(null);
      setNotice(null);
      const response = await dashboardApi.exportServiceStationFlowReport({
        startDate,
        endDate,
        saveAsPath,
      });
      setResult(response);
      setNotice(response.exportInfo ? `导出成功：${response.exportInfo.filePath}` : "导出成功");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  async function copyExportPath() {
    if (!result?.exportInfo?.filePath) {
      return;
    }
    try {
      await navigator.clipboard.writeText(result.exportInfo.filePath);
      setNotice("导出路径已复制到剪贴板");
    } catch (copyError) {
      setError(copyError instanceof Error ? copyError.message : "复制路径失败");
    }
  }

  async function openExportFolder() {
    if (!result?.exportInfo?.filePath) {
      return;
    }
    try {
      await dashboardApi.openReportFolder(result.exportInfo.filePath);
      setNotice("已尝试打开导出所在目录");
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "打开目录失败");
    }
  }

  return (
    <Stack spacing={3}>
      <Typography variant="body1">
        服务站人员流动表按 `开始日期 -&gt; 结束日期` 两期历史快照做点对点分析，不会把结果解释成连续月度轨迹。
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {notice ? <Alert severity="success">{notice}</Alert> : null}
      {options && !options.canRun ? <Alert severity="warning">{options.hint}</Alert> : null}

      <SectionCard
        title="查询参数"
        subtitle={loadingOptions ? "正在读取可用历史快照..." : "开始日期和结束日期必须都来自历史快照。"}
        action={
          <Stack direction="row" spacing={1}>
            <Button variant="outlined" size="small" onClick={() => void runQuery()} disabled={loadingOptions || !options?.canRun || loadingResult}>
              {loadingResult ? "查询中..." : "执行查询"}
            </Button>
            <Button variant="contained" disableElevation size="small" onClick={() => void exportWorkbook()} disabled={loadingOptions || !options?.canRun || exporting}>
              {exporting ? "导出中..." : "导出 Excel"}
            </Button>
          </Stack>
        }
      >
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={1.5}>
            <TextField
              select
              label="开始日期"
              size="small"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              sx={{ minWidth: { xs: "100%", lg: 220 } }}
              disabled={loadingOptions || !(options?.availableSnapshotDates?.length)}
            >
              {(options?.availableSnapshotDates ?? []).map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="结束日期"
              size="small"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              sx={{ minWidth: { xs: "100%", lg: 220 } }}
              disabled={loadingOptions || !(options?.availableSnapshotDates?.length)}
            >
              {(options?.availableSnapshotDates ?? []).map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="另存为路径"
              size="small"
              fullWidth
              value={saveAsPath}
              onChange={(event) => setSaveAsPath(event.target.value)}
              placeholder="留空则导出到默认目录；支持绝对路径、仓库相对路径或目录路径"
            />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            默认导出目录：{options?.defaultExportDirectory || "-"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            可用历史快照：{(options?.availableSnapshotDates ?? []).join("、") || "-"}
          </Typography>
        </Stack>
      </SectionCard>

      {result ? (
        <>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(3, minmax(0, 1fr))" },
              gap: 2,
            }}
          >
            {summaryStats.map((item) => (
              <StatCard key={item.label} item={item} />
            ))}
          </Box>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" },
              gap: 2,
            }}
          >
            <AppDataGrid
              title="去向分类"
              subtitle={`${result.startDate} 期初目标岗位人员的期末去向`}
              rows={result.outflowCategoryRows}
              columns={categoryColumns}
              loading={loadingResult}
              minHeight={280}
            />
            <AppDataGrid
              title="来源分类"
              subtitle={`${result.endDate} 期末目标岗位人员的期初来源`}
              rows={result.inflowCategoryRows}
              columns={categoryColumns}
              loading={loadingResult}
              minHeight={280}
            />
            <AppDataGrid
              title="转其他HR去向分布"
              subtitle="期初在目标岗位、期末转去其他 HR 子域的人数分布"
              rows={result.otherHrOutDestinationRows}
              columns={categoryColumns}
              loading={loadingResult}
              minHeight={280}
            />
            <AppDataGrid
              title="其他HR转入来源分布"
              subtitle="期末进入目标岗位、期初来自其他 HR 子域的人数分布"
              rows={result.otherHrInSourceRows}
              columns={categoryColumns}
              loading={loadingResult}
              minHeight={280}
            />
          </Box>

          <SectionCard
            title="导出结果"
            subtitle="默认路径固定为 automation/logs/report_exports；也支持自定义另存为路径。"
            action={
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" size="small" onClick={() => void copyExportPath()} disabled={!result.exportInfo?.filePath}>
                  复制路径
                </Button>
                <Button variant="contained" disableElevation size="small" onClick={() => void openExportFolder()} disabled={!result.exportInfo?.filePath}>
                  打开所在目录
                </Button>
              </Stack>
            }
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                最终文件名：{result.exportInfo?.fileName || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                最终绝对路径：{result.exportInfo?.filePath || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                导出时间：{result.exportInfo?.exportedAt || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                文件大小：{result.exportInfo ? `${result.exportInfo.fileSize} bytes` : "-"}
              </Typography>
            </Stack>
          </SectionCard>

          <SectionCard title="结果明细" subtitle="战区汇总和四类明细都按当前查询结果实时生成。">
            <Tabs value={detailTab} onChange={(_, value) => setDetailTab(String(value))} sx={{ mb: 2 }}>
              <Tab value="zone" label="战区汇总" />
              <Tab value="left" label={`离职明细 (${result.leftRows.length})`} />
              <Tab value="otherHrOut" label={`转其他HR (${result.otherHrOutRows.length})`} />
              <Tab value="targetFlow" label={`目标岗位去向 (${result.targetFlowRows.length})`} />
              <Tab value="otherHrIn" label={`其他HR转入 (${result.otherHrInRows.length})`} />
            </Tabs>

            {detailTab === "zone" ? (
              <AppDataGrid
                title="战区汇总"
                subtitle="按战区展示期初/期末人数、增减和关键流动人数"
                rows={result.zoneSummaryRows}
                columns={zoneColumns}
                loading={loadingResult}
                minHeight={520}
                pageSizeOptions={[10, 20, 50]}
              />
            ) : null}
            {detailTab === "left" ? (
              <AppDataGrid
                title="离职明细"
                subtitle="期初在目标岗位、期末按工号找不到的人员"
                rows={result.leftRows}
                columns={detailColumns}
                loading={loadingResult}
                minHeight={520}
                pageSizeOptions={[10, 20, 50]}
              />
            ) : null}
            {detailTab === "otherHrOut" ? (
              <AppDataGrid
                title="转其他HR明细"
                subtitle="期末不在目标岗位，但仍属于 H* 的人员"
                rows={result.otherHrOutRows}
                columns={detailColumns}
                loading={loadingResult}
                minHeight={520}
                pageSizeOptions={[10, 20, 50]}
              />
            ) : null}
            {detailTab === "targetFlow" ? (
              <AppDataGrid
                title="目标岗位去向明细"
                subtitle="期初目标岗位全量人员的期末去向"
                rows={result.targetFlowRows}
                columns={detailColumns}
                loading={loadingResult}
                minHeight={520}
                pageSizeOptions={[10, 20, 50]}
              />
            ) : null}
            {detailTab === "otherHrIn" ? (
              <AppDataGrid
                title="其他HR转入明细"
                subtitle="期末进入目标岗位、期初来自其他 HR 岗位的人员"
                rows={result.otherHrInRows}
                columns={detailColumns}
                loading={loadingResult}
                minHeight={520}
                pageSizeOptions={[10, 20, 50]}
              />
            ) : null}
          </SectionCard>
        </>
      ) : null}
    </Stack>
  );
}
