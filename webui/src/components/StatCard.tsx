import { Box, Paper, Typography } from "@mui/material";

import type { StatItem, Tone } from "../types/dashboard";

const toneColorMap: Record<Tone, string> = {
  default: "#0f172a",
  success: "#217a4b",
  warning: "#9a6700",
  danger: "#b42318",
  info: "#175cd3",
};

interface StatCardProps {
  item: StatItem;
}

export function StatCard({ item }: StatCardProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        overflow: "hidden",
        border: "1px solid",
        borderColor: "divider",
        backgroundColor: "rgba(255,255,255,0.94)",
      }}
    >
      <Box sx={{ height: 4, backgroundColor: toneColorMap[item.tone] }} />
      <Box sx={{ px: 2, py: 2.25 }}>
        <Typography variant="body2" color="text.secondary">
          {item.label}
        </Typography>
        <Typography variant="h5" sx={{ mt: 0.75 }}>
          {item.value}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {item.hint}
        </Typography>
      </Box>
    </Paper>
  );
}
