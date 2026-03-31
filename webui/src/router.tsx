import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { CollectDocumentsPage } from "./pages/CollectDocumentsPage";
import { MasterDataPage } from "./pages/MasterDataPage";
import { ProcessAnalysisPage } from "./pages/ProcessAnalysisPage";
import { ProcessDocumentsPage } from "./pages/ProcessDocumentsPage";
import { ReportCenterPage } from "./pages/ReportCenterPage";
import { RuntimeSettingsPage } from "./pages/RuntimeSettingsPage";
import { ServiceStationFlowReportPage } from "./pages/ServiceStationFlowReportPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/master-data" replace />,
      },
      {
        path: "master-data",
        element: <MasterDataPage />,
      },
      {
        path: "collect-documents",
        element: <CollectDocumentsPage />,
      },
      {
        path: "process-documents",
        element: <ProcessDocumentsPage />,
      },
      {
        path: "process-analysis",
        element: <ProcessAnalysisPage />,
      },
      {
        path: "runtime-settings",
        element: <RuntimeSettingsPage />,
      },
      {
        path: "report-center",
        element: <Navigate to="/report-center/service-station-analysis" replace />,
      },
      {
        path: "report-center/service-station-analysis",
        element: <ReportCenterPage />,
      },
      {
        path: "report-center/service-station-flow",
        element: <ServiceStationFlowReportPage />,
      },
    ],
  },
]);
