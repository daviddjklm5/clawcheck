import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";

import { KeyValueList } from "../components/KeyValueList";
import { SectionCard } from "../components/SectionCard";
import { StatCard } from "../components/StatCard";
import { dashboardApi } from "../services/api";
import type { DetailField, RuntimeSettingsSummary } from "../types/dashboard";

function buildCollectScheduleFields(data: RuntimeSettingsSummary | null): DetailField[] {
  const schedule = data?.collectSchedule;
  if (!schedule) {
    return [];
  }

  const fields: DetailField[] = [
    {
      label: "执行模式",
      value: schedule.mode === "headless" ? "无头浏览器" : schedule.mode || "-",
      hint: "定时采集固定后台无头执行，不显示浏览器。",
    },
    {
      label: "采集后自动评估",
      value: schedule.autoAudit ? "已启用" : "已关闭",
      hint: "启用后，定时采集成功落库的单据会立即执行增量评估，再进入处理单据工作台。",
    },
    {
      label: "当前状态",
      value: schedule.isRunning ? "运行中" : schedule.enabled ? "已启用" : "未启用",
      hint: schedule.isRunning
        ? "当前批次运行中，下一次计划时间待本批次结束后重算。"
        : "由 task daemon 负责轮询调度。",
    },
    {
      label: "最近开始时间",
      value: schedule.lastStartedAt || "-",
      hint: "最近一次实际启动采集的时间。",
    },
    {
      label: "最近结束时间",
      value: schedule.lastFinishedAt || "-",
      hint: "下一批次频率从该时间点起算。",
    },
    {
      label: "下一次计划时间",
      value: schedule.nextPlannedAt || (schedule.isRunning ? "待当前批次结束后重算" : "-"),
      hint: "定时采集按“上一批结束时间 + 频率分钟数”计算。",
    },
    {
      label: "最近一次结果",
      value: schedule.lastMessage || "-",
      hint: "无待办时会显示“本轮无待办，已快速结束”。",
      columnSpan: 2,
    },
    {
      label: "最近退出码",
      value: schedule.lastExitCode === null ? "-" : String(schedule.lastExitCode),
      hint: "0 代表成功结束；非 0 代表异常退出。",
    },
    {
      label: "daemon 轮询秒数",
      value: String(schedule.pollSeconds),
      hint: "页面保存后通常在一个轮询周期内生效。",
    },
    {
      label: "daemon 配置文件",
      value: schedule.configFile,
      hint: "定时采集的单一事实来源。",
      columnSpan: 2,
    },
    {
      label: "daemon 状态文件",
      value: schedule.stateFile,
      hint: "保存最近开始/结束时间与最近一次结果。",
      columnSpan: 2,
    },
    {
      label: "collect 锁文件",
      value: schedule.lockFile,
      hint: "用于避免人工采集和定时采集并发撞车。",
      columnSpan: 2,
    },
    {
      label: "最近日志",
      value: schedule.lastLogPath || "-",
      hint: "可用于排查最近一次定时采集执行过程。",
      columnSpan: 2,
    },
  ];
  fields.splice(2, 0, {
    label: "采集后自动批量批准",
    value: schedule.autoBatchApprove ? "已启用" : "已关闭",
    hint: "启用后，采集完成会自动批准最终分为 2.0/2.5 的待处理单据。",
  });
  return fields;
}

export function RuntimeSettingsPage() {
  const [data, setData] = useState<RuntimeSettingsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleInterval, setScheduleInterval] = useState("15");
  const [scheduleAutoAudit, setScheduleAutoAudit] = useState(true);
  const [scheduleAutoBatchApprove, setScheduleAutoBatchApprove] = useState(false);
  const [saveSubmitting, setSaveSubmitting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const response = await dashboardApi.getRuntimeSettings();
        if (active) {
          setData(response);
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
  }, [refreshVersion]);

  useEffect(() => {
    if (!data?.collectSchedule) {
      return;
    }
    setScheduleEnabled(data.collectSchedule.enabled);
    setScheduleInterval(String(data.collectSchedule.intervalMinutes || 15));
    setScheduleAutoAudit(data.collectSchedule.autoAudit);
    setScheduleAutoBatchApprove(data.collectSchedule.autoBatchApprove);
  }, [data]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRefreshVersion((currentValue) => currentValue + 1);
    }, 15_000);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  async function saveCollectSchedule() {
    const parsedInterval = Math.max(Number.parseInt(scheduleInterval, 10) || 0, 0);

    try {
      setSaveSubmitting(true);
      setSaveError(null);
      setSaveNotice(null);
      const response = await dashboardApi.updateCollectSchedule({
        enabled: scheduleEnabled,
        intervalMinutes: parsedInterval,
        autoAudit: scheduleAutoAudit,
        autoBatchApprove: scheduleAutoBatchApprove,
      });
      setData(response);
      setSaveNotice(scheduleEnabled ? "定时采集配置已保存。" : "已关闭定时采集。");
    } catch (saveLoadError) {
      setSaveError(saveLoadError instanceof Error ? saveLoadError.message : "保存定时采集配置失败");
    } finally {
      setSaveSubmitting(false);
    }
  }

  const collectScheduleFields = buildCollectScheduleFields(data);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="body1">
          常规配置页展示运行摘要、路径信息和定时采集配置，不在页面暴露真实口令或敏感安全凭据。
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {saveError ? <Alert severity="error">{saveError}</Alert> : null}
      {saveNotice ? <Alert severity="success">{saveNotice}</Alert> : null}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(5, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {(data?.stats ?? []).map((item) => (
          <StatCard key={item.label} item={item} />
        ))}
      </Box>

      <SectionCard
        title="定时采集单据"
        subtitle="频率单位为分钟；下一批次从上一批次结束时间起算。"
        action={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => setRefreshVersion((currentValue) => currentValue + 1)}
            >
              刷新
            </Button>
            <Button
              variant="contained"
              disableElevation
              onClick={() => void saveCollectSchedule()}
              disabled={saveSubmitting}
            >
              {saveSubmitting ? "保存中..." : "保存配置"}
            </Button>
          </Stack>
        }
      >
        <Stack spacing={2.5}>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }}>
            <FormControlLabel
              control={
                <Switch
                  checked={scheduleEnabled}
                  onChange={(event) => setScheduleEnabled(event.target.checked)}
                />
              }
              label="启用定时采集"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={scheduleAutoAudit}
                  onChange={(event) => setScheduleAutoAudit(event.target.checked)}
                />
              }
              label="采集后自动评估"
              sx={{ ml: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={scheduleAutoBatchApprove}
                  onChange={(event) => setScheduleAutoBatchApprove(event.target.checked)}
                />
              }
              label="采集后自动批量批准"
              sx={{ ml: 0 }}
            />
            <TextField
              label="采集频率（分钟）"
              value={scheduleInterval}
              onChange={(event) => setScheduleInterval(event.target.value)}
              size="small"
              sx={{ width: { xs: "100%", sm: 200 } }}
              disabled={!scheduleEnabled}
            />
            <Typography variant="body2" color="text.secondary">
              自动采集固定为无头执行；人工采集入口仍可单独选择可见浏览器。
            </Typography>
          </Stack>

          <KeyValueList items={collectScheduleFields} />
        </Stack>
      </SectionCard>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", xl: "repeat(2, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        <SectionCard
          title="运行时配置"
          subtitle={loading ? "读取中..." : `${data?.environmentLabel ?? ""} / ${data?.configFile ?? ""}`}
        >
          <KeyValueList items={data?.runtime ?? []} />
        </SectionCard>

        <SectionCard title="浏览器设置" subtitle="与当前 Playwright 配置保持一致">
          <KeyValueList items={data?.browser ?? []} />
        </SectionCard>

        <SectionCard title="数据库摘要" subtitle="仅展示 host / port / dbname / schema 等必要信息">
          <KeyValueList items={data?.database ?? []} />
        </SectionCard>

        <SectionCard title="路径与安全说明" subtitle="敏感信息管理遵循 AGENTS.md 约束">
          <KeyValueList items={data?.paths ?? []} />
          <Typography variant="subtitle2" sx={{ mt: 2.5 }}>
            安全说明
          </Typography>
          <Stack spacing={1} sx={{ mt: 1.5 }}>
            {(data?.securityNotes ?? []).map((item) => (
              <Typography key={item} variant="body2" color="text.secondary">
                • {item}
              </Typography>
            ))}
          </Stack>
        </SectionCard>
      </Box>
    </Stack>
  );
}
