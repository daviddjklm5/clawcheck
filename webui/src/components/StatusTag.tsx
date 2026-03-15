import { Box } from "@mui/material";

import type { Tone } from "../types/dashboard";

const styleMap: Record<Tone, { backgroundColor: string; borderColor: string; color: string }> = {
  default: {
    backgroundColor: "rgba(15, 23, 42, 0.05)",
    borderColor: "rgba(15, 23, 42, 0.12)",
    color: "#0f172a",
  },
  success: {
    backgroundColor: "rgba(33, 122, 75, 0.08)",
    borderColor: "rgba(33, 122, 75, 0.2)",
    color: "#217a4b",
  },
  warning: {
    backgroundColor: "rgba(154, 103, 0, 0.08)",
    borderColor: "rgba(154, 103, 0, 0.2)",
    color: "#9a6700",
  },
  danger: {
    backgroundColor: "rgba(180, 35, 24, 0.08)",
    borderColor: "rgba(180, 35, 24, 0.2)",
    color: "#b42318",
  },
  info: {
    backgroundColor: "rgba(23, 92, 211, 0.08)",
    borderColor: "rgba(23, 92, 211, 0.2)",
    color: "#175cd3",
  },
};

interface StatusTagProps {
  label: string;
  tone?: Tone;
}

export function StatusTag({ label, tone = "default" }: StatusTagProps) {
  const styles = styleMap[tone];

  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        px: 1,
        py: 0.35,
        border: "1px solid",
        borderRadius: 1,
        fontSize: 12,
        fontWeight: 600,
        lineHeight: 1.4,
        whiteSpace: "nowrap",
        ...styles,
      }}
    >
      {label}
    </Box>
  );
}
