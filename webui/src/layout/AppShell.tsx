import { useState } from "react";
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import SettingsSuggestOutlinedIcon from "@mui/icons-material/SettingsSuggestOutlined";
import SyncAltOutlinedIcon from "@mui/icons-material/SyncAltOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import GridViewOutlinedIcon from "@mui/icons-material/GridViewOutlined";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const drawerWidth = 264;

const navItems = [
  {
    path: "/master-data",
    label: "同步主数据",
    description: "花名册、组织列表与权限主数据",
    icon: <SyncAltOutlinedIcon />,
  },
  {
    path: "/collect-documents",
    label: "采集单据",
    description: "采集四张申请单表的字段与状态",
    icon: <DescriptionOutlinedIcon />,
  },
  {
    path: "/process-documents",
    label: "处理单据",
    description: "待处理列表与抽屉化单据详情",
    icon: <FactCheckOutlinedIcon />,
  },
  {
    path: "/process-analysis",
    label: "评估分析",
    description: "批次分布、规则热点与执行日志",
    icon: <InsightsOutlinedIcon />,
  },
  {
    path: "/runtime-settings",
    label: "常规配置",
    description: "浏览器运行参数、路径与数据库摘要",
    icon: <SettingsSuggestOutlinedIcon />,
  },
  {
    path: "/chat-workspace",
    label: "对话工作台",
    description: "Web 对话入口，基于 Codex CLI 与外部模型 Key",
    icon: <SmartToyOutlinedIcon />,
  },
];

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const currentItem = navItems.find((item) => location.pathname.startsWith(item.path)) ?? navItems[0];

  const drawerContent = (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        p: 2,
        background: "linear-gradient(180deg, #0b1728 0%, #132238 100%)",
        color: "#f8fafc",
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: 2,
          border: "1px solid rgba(148, 163, 184, 0.18)",
          background: "linear-gradient(180deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.04) 100%)",
          color: "inherit",
        }}
      >
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <GridViewOutlinedIcon fontSize="small" />
            <Typography variant="overline" sx={{ letterSpacing: "0.12em", opacity: 0.78 }}>
              clawcheck
            </Typography>
          </Stack>
          <Typography variant="h6">200 计划可视化页面</Typography>
          <Typography variant="body2" sx={{ color: "rgba(226, 232, 240, 0.78)" }}>
            社区版 DataGrid + FastAPI + React/Vite
          </Typography>
        </Stack>
      </Paper>

      <List sx={{ mt: 2, px: 0 }}>
        {navItems.map((item) => {
          const selected = location.pathname.startsWith(item.path);

          return (
            <ListItemButton
              key={item.path}
              selected={selected}
              onClick={() => {
                navigate(item.path);
                setMobileOpen(false);
              }}
              sx={{
                mb: 1,
                alignItems: "flex-start",
                border: "1px solid",
                borderColor: selected ? "rgba(125, 211, 252, 0.6)" : "rgba(148, 163, 184, 0.12)",
                backgroundColor: selected ? "rgba(23, 92, 211, 0.16)" : "rgba(255, 255, 255, 0.02)",
                "&.Mui-selected": {
                  backgroundColor: "rgba(23, 92, 211, 0.16)",
                },
                "&.Mui-selected:hover": {
                  backgroundColor: "rgba(23, 92, 211, 0.22)",
                },
                "&:hover": {
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: "inherit", mt: 0.3 }}>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                secondary={item.description}
                primaryTypographyProps={{ fontWeight: 600 }}
                secondaryTypographyProps={{ color: "rgba(226, 232, 240, 0.72)", sx: { mt: 0.4 } }}
              />
            </ListItemButton>
          );
        })}
      </List>

      <Box sx={{ mt: "auto" }}>
        <Paper
          elevation={0}
          sx={{
            p: 2,
            borderRadius: 2,
            border: "1px solid rgba(148, 163, 184, 0.18)",
            backgroundColor: "rgba(255,255,255,0.03)",
            color: "inherit",
          }}
        >
          <Typography variant="subtitle2">当前范围</Typography>
          <Typography variant="body2" sx={{ mt: 1, color: "rgba(226, 232, 240, 0.74)" }}>
            当前已拆分处理工作台与评估分析页，并保留单据级审批连通能力。
          </Typography>
        </Paper>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        color="transparent"
        elevation={0}
        sx={{
          display: { md: "none" },
          boxShadow: "none",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(15, 23, 42, 0.08)",
        }}
      >
        <Toolbar>
          <IconButton color="inherit" edge="start" onClick={() => setMobileOpen(true)}>
            <MenuIcon />
          </IconButton>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {currentItem.label}
          </Typography>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              borderRight: "none",
            },
          }}
        >
          {drawerContent}
        </Drawer>

        <Drawer
          variant="permanent"
          open
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              borderRight: "none",
            },
          }}
        >
          {drawerContent}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          px: { xs: 2, md: 3 },
          pt: { xs: 10, md: 3 },
          pb: 3,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            mb: 3,
            px: { xs: 2, md: 2.5 },
            py: 2,
            border: "1px solid",
            borderColor: "divider",
            background: "linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(244,247,251,0.92) 100%)",
          }}
        >
          <Stack
            direction={{ xs: "column", lg: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", lg: "center" }}
            spacing={1.5}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                当前模块
              </Typography>
              <Typography variant="h4" sx={{ mt: 0.5 }}>
                {currentItem.label}
              </Typography>
            </Box>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25}>
              <Paper
                elevation={0}
                sx={{
                  px: 1.5,
                  py: 1,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.72)",
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  当前阶段
                </Typography>
                <Typography variant="subtitle2">UI 骨架联调</Typography>
              </Paper>
              <Paper
                elevation={0}
                sx={{
                  px: 1.5,
                  py: 1,
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "rgba(255,255,255,0.72)",
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  设计原则
                </Typography>
                <Typography variant="subtitle2">左侧菜单 + 详情联动 + 顶部卡片式页签</Typography>
              </Paper>
            </Stack>
          </Stack>
        </Paper>

        <Outlet />
      </Box>
    </Box>
  );
}
