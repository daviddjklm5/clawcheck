import type { ReactNode } from "react";

import { Stack, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";
import {
  DataGrid,
  type DataGridProps,
  type GridValidRowModel,
} from "@mui/x-data-grid";

import { SectionCard } from "./SectionCard";

function EmptyOverlay() {
  return (
    <Stack height="100%" alignItems="center" justifyContent="center" spacing={0.5}>
      <Typography variant="body2" color="text.secondary">
        暂无数据
      </Typography>
      <Typography variant="caption" color="text.secondary">
        当前视图没有可展示内容
      </Typography>
    </Stack>
  );
}

interface AppDataGridProps<R extends GridValidRowModel> extends Omit<DataGridProps<R>, "slots"> {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  minHeight?: number;
  sx?: SxProps<Theme>;
}

export function AppDataGrid<R extends GridValidRowModel>({
  title,
  subtitle,
  actions,
  minHeight = 360,
  sx,
  pageSizeOptions,
  ...props
}: AppDataGridProps<R>) {
  const paginationMode = props.paginationMode ?? "client";
  const normalizedProps = paginationMode === "server" ? props : { ...props, rowCount: undefined };
  const mergedSx = [
    {
      border: 0,
      backgroundColor: "transparent",
      "& .MuiDataGrid-columnHeaders": {
        backgroundColor: "rgba(15, 23, 42, 0.04)",
        borderBottom: "1px solid rgba(15, 23, 42, 0.08)",
      },
      "& .MuiDataGrid-cell": {
        borderColor: "rgba(15, 23, 42, 0.08)",
      },
      "& .MuiDataGrid-row:hover": {
        backgroundColor: "rgba(11, 79, 108, 0.04)",
      },
      "& .MuiDataGrid-footerContainer": {
        borderTop: "1px solid rgba(15, 23, 42, 0.08)",
      },
    },
    ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
  ] as SxProps<Theme>;

  return (
    <SectionCard title={title} subtitle={subtitle} action={actions}>
      <DataGrid
        {...normalizedProps}
        pagination
        hideFooterSelectedRowCount
        disableRowSelectionOnClick
        disableColumnMenu
        disableColumnFilter
        disableDensitySelector
        pageSizeOptions={pageSizeOptions ?? [5, 10, 20]}
        slots={{ noRowsOverlay: EmptyOverlay }}
        sx={mergedSx}
        style={{ height: minHeight }}
      />
    </SectionCard>
  );
}
