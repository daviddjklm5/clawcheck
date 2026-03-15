import { alpha, createTheme } from "@mui/material/styles";
import type {} from "@mui/x-data-grid/themeAugmentation";

export const appTheme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#0b4f6c",
      dark: "#08384c",
      light: "#2c7da0",
    },
    secondary: {
      main: "#2c7da0",
    },
    success: {
      main: "#217a4b",
    },
    warning: {
      main: "#9a6700",
    },
    error: {
      main: "#b42318",
    },
    info: {
      main: "#175cd3",
    },
    background: {
      default: "#f3f6fb",
      paper: "#ffffff",
    },
    text: {
      primary: "#101828",
      secondary: "#475467",
    },
  },
  shape: {
    borderRadius: 10,
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif',
    h4: {
      fontWeight: 600,
      letterSpacing: "-0.03em",
    },
    h5: {
      fontWeight: 600,
      letterSpacing: "-0.02em",
    },
    h6: {
      fontWeight: 600,
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background:
            "radial-gradient(circle at top right, rgba(44, 125, 160, 0.14), transparent 32%), linear-gradient(180deg, #f7fafc 0%, #eef2f8 100%)",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: {
          display: "none",
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          minHeight: 52,
          padding: "12px 16px",
          borderRadius: 0,
          textTransform: "none",
          fontWeight: 600,
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          backgroundColor: alpha("#ffffff", 0.92),
        },
      },
    },
  },
});
