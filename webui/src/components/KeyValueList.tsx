import { Box, Typography } from "@mui/material";

import type { DetailField } from "../types/dashboard";

interface KeyValueListProps {
  items: DetailField[];
}

export function KeyValueList({ items }: KeyValueListProps) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" },
        gap: 1.5,
      }}
    >
      {items.map((item) => (
        <Box
          key={`${item.label}-${item.value}`}
          sx={{
            gridColumn: {
              xs: "auto",
              md: item.columnSpan === 2 ? "span 2" : "auto",
            },
            p: 1.5,
            border: "1px solid",
            borderColor: "divider",
            backgroundColor: "rgba(255,255,255,0.68)",
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {item.label}
          </Typography>
          <Typography
            variant="body1"
            fontWeight={600}
            sx={{ mt: 0.75, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
          >
            {item.value}
          </Typography>
          {item.hint ? (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: "block" }}>
              {item.hint}
            </Typography>
          ) : null}
        </Box>
      ))}
    </Box>
  );
}
