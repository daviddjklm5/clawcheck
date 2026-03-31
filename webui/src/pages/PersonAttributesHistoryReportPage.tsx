import { useEffect, useMemo, useState } from "react";
import { Alert, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import type { GridColDef } from "@mui/x-data-grid";

import { AppDataGrid } from "../components/AppDataGrid";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { dashboardApi } from "../services/api";
import type {
  PersonAttributesHistoryOptions,
  PersonAttributesHistoryPreviewRow,
  PersonAttributesHistoryReportResult,
  StatItem,
} from "../types/dashboard";

function buildStats(result: PersonAttributesHistoryReportResult): StatItem[] {
  return [
    {
      label: "生效日期",
      value: result.effectiveDate,
      hint: "当前筛选生效日期",
      tone: "info",
    },
    {
      label: "记录总数",
      value: String(result.rowCount),
      hint: "历史快照总行数",
      tone: "success",
    },
    {
      label: "预览行数",
      value: String(result.previewRows.length),
      hint: "页面最多展示前 200 行",
      tone: "default",
    },
  ];
}

export function PersonAttributesHistoryReportPage() {
  const [options, setOptions] = useState<PersonAttributesHistoryOptions | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loadingResult, setLoadingResult] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<PersonAttributesHistoryReportResult | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [saveAsPath, setSaveAsPath] = useState("");

  useEffect(() => {
    let active = true;

    async function loadOptions() {
      try {
        setLoadingOptions(true);
        const response = await dashboardApi.getPersonAttributesHistoryOptions();
        if (active) {
          setOptions(response);
          setEffectiveDate((currentValue) => currentValue || response.defaultEffectiveDate || "");
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

  const stats = useMemo(() => (result ? buildStats(result) : []), [result]);

  const previewColumns = useMemo<GridColDef<PersonAttributesHistoryPreviewRow>[]>(() => {
    if (!result) {
      return [];
    }
    return result.columns.map((columnName) => ({
      field: columnName,
      headerName: columnName,
      minWidth: 140,
      flex: 1,
    }));
  }, [result]);

  async function runQuery() {
    try {
      setLoadingResult(true);
      setError(null);
      setNotice(null);
      const response = await dashboardApi.queryPersonAttributesHistoryReport({
        effectiveDate,
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
      const response = await dashboardApi.exportPersonAttributesHistoryReport({
        effectiveDate,
        saveAsPath,
      });
      setResult((previous) => {
        if (!previous) {
          return response;
        }
        return {
          ...previous,
          effectiveDate: response.effectiveDate,
          rowCount: response.rowCount,
          columns: response.columns,
          exportInfo: response.exportInfo,
        };
      });
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
        人员属性查询报表支持按生效日期筛选 `人员属性查询历史` 快照，并导出不含技术元数据字段的 Excel。
      </Typography>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {notice ? <Alert severity="success">{notice}</Alert> : null}
      {options && !options.canRun ? <Alert severity="warning">{options.hint}</Alert> : null}

      <SectionCard
        title="查询参数"
        subtitle={loadingOptions ? "正在加载可用生效日期..." : "选择生效日期后可先查询，再导出 Excel"}
        action={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => void runQuery()}
              disabled={loadingOptions || !options?.canRun || loadingResult}
            >
              {loadingResult ? "查询中..." : "执行查询"}
            </Button>
            <Button
              variant="contained"
              disableElevation
              size="small"
              onClick={() => void exportWorkbook()}
              disabled={loadingOptions || !options?.canRun || exporting}
            >
              {exporting ? "导出中..." : "导出 Excel"}
            </Button>
          </Stack>
        }
      >
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={1.5}>
            <TextField
              select
              label="生效日期"
              size="small"
              value={effectiveDate}
              onChange={(event) => setEffectiveDate(event.target.value)}
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
            可选生效日期数量：{options?.availableSnapshotDates.length ?? 0}
          </Typography>
        </Stack>
      </SectionCard>

      {result ? (
        <>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            {stats.map((item) => (
              <StatCard key={item.label} item={item} />
            ))}
          </Stack>

          <SectionCard
            title="导出结果"
            subtitle="默认目录为 automation/logs/report_exports，也支持自定义另存路径。"
            action={
              <Stack direction="row" spacing={1}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => void copyExportPath()}
                  disabled={!result.exportInfo?.filePath}
                >
                  复制路径
                </Button>
                <Button
                  variant="contained"
                  disableElevation
                  size="small"
                  onClick={() => void openExportFolder()}
                  disabled={!result.exportInfo?.filePath}
                >
                  打开所在目录
                </Button>
              </Stack>
            }
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                文件名：{result.exportInfo?.fileName || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                绝对路径：{result.exportInfo?.filePath || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                导出时间：{result.exportInfo?.exportedAt || "-"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                文件大小：{result.exportInfo ? `${result.exportInfo.fileSize} bytes` : "-"}
              </Typography>
            </Stack>
          </SectionCard>

          <AppDataGrid
            title="数据预览"
            subtitle="仅展示前 200 行，完整数据请使用导出文件。"
            rows={result.previewRows}
            columns={previewColumns}
            loading={loadingResult}
            minHeight={520}
            pageSizeOptions={[10, 20, 50]}
          />
        </>
      ) : null}
    </Stack>
  );
}
