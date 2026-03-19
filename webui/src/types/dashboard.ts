export type Tone = "default" | "success" | "warning" | "danger" | "info";

export interface StatItem {
  label: string;
  value: string;
  hint: string;
  tone: Tone;
}

export interface ActionCard {
  id: string;
  taskType?: "roster" | "orglist" | "rolecatalog";
  title: string;
  description: string;
  buttonLabel: string;
  status: string;
}

export interface DetailField {
  label: string;
  value: string;
  hint?: string;
}

export interface JobRow {
  id: string;
  jobType: string;
  target: string;
  status: string;
  startedAt: string;
  finishedAt: string;
  records: number;
  operator: string;
}

export interface MasterDataDashboard {
  stats: StatItem[];
  actions: ActionCard[];
  currentTask: MasterDataRunSummary | null;
  recentRuns: MasterDataRunSummary[];
}

export interface MasterDataRunRequest {
  taskType: "roster" | "orglist" | "rolecatalog";
  headed: boolean | null;
  dryRun: boolean;
  inputFile: string;
  skipExport: boolean;
  skipImport: boolean;
  queryTimeoutSeconds: number;
  downloadTimeoutMinutes: number;
  scheme: string;
  employmentType: string;
  forceRefresh: boolean;
}

export interface MasterDataPermissionLevelCount {
  permissionLevel: string;
  count: number;
}

export interface MasterDataRunSummary {
  id: string;
  taskId: string;
  taskType: string;
  status: string;
  requestedAt: string;
  startedAt: string;
  finishedAt: string;
  headed: boolean;
  dryRun: boolean;
  inputFile: string;
  skipExport: boolean;
  skipImport: boolean;
  queryTimeoutSeconds: number;
  downloadTimeoutMinutes: number;
  scheme: string;
  employmentType: string;
  forceRefresh: boolean;
  tableName: string;
  importBatchNo: string;
  sourceFileName: string;
  insertedCount: number;
  totalRows: number;
  countsByPermissionLevel: MasterDataPermissionLevelCount[];
  message: string;
  dumpFile: string;
  summaryFile: string;
  logFile: string;
  outputTail: string;
}

export interface CollectDocumentRow {
  id: string;
  documentNo: string;
  applicantName: string;
  applicantNo: string;
  permissionTarget: string;
  departmentName: string;
  documentStatus: string;
  collectStatus: string;
  applyTime: string;
  latestApprovalTime: string;
  collectedAt: string;
  roleCount: number;
  approvalCount: number;
  orgScopeCount: number;
  collectionCount: number;
}

export interface CollectRoleRow {
  id: string;
  lineNo: string;
  applyType: string;
  roleCode: string;
  roleName: string;
  permissionLevel: string;
  orgScopeCount: number;
  skipOrgScopeCheck: string;
}

export interface CollectApprovalRow {
  id: string;
  nodeName: string;
  approver: string;
  action: string;
  finishedAt: string;
  comment: string;
}

export interface CollectOrgScopeRow {
  id: string;
  roleCode: string;
  roleName: string;
  organizationCode: string;
  organizationName: string;
  orgUnitName: string;
  physicalLevel: string;
  skipOrgScopeCheck: string;
}

export interface TableStatusRow {
  id: string;
  tableName: string;
  status: string;
  records: number;
  updatedAt: string;
  remark: string;
}

export interface CollectDetail {
  documentNo: string;
  collectStatus: string;
  overviewFields: DetailField[];
  tableStatus: TableStatusRow[];
  roles: CollectRoleRow[];
  approvals: CollectApprovalRow[];
  orgScopes: CollectOrgScopeRow[];
  notes: string[];
}

export interface CollectRunRequest {
  documentNo: string;
  limit: number;
  dryRun: boolean;
  autoAudit: boolean;
  forceRecollect: boolean;
}

export interface CollectRunSummary {
  id: string;
  taskId: string;
  status: string;
  requestedAt: string;
  startedAt: string;
  finishedAt: string;
  requestedDocumentNo: string;
  requestedLimit: number;
  dryRun: boolean;
  forceRecollect: boolean;
  requestedCount: number;
  successCount: number;
  skippedCount: number;
  failedCount: number;
  message: string;
  autoAudit: boolean;
  auditStatus: string;
  auditBatchNo: string;
  auditMessage: string;
  auditLogFile: string;
  dumpFile: string;
  skippedDumpFile: string;
  failedDumpFile: string;
  summaryFile: string;
  logFile: string;
  outputTail: string;
}

export interface CollectWorkbench {
  stats: StatItem[];
  documents: CollectDocumentRow[];
  currentTask: CollectRunSummary | null;
  recentRuns: CollectRunSummary[];
}

export interface ProcessDocumentRow {
  id: string;
  documentNo: string;
  applicantName: string;
  applicantNo: string;
  permissionTarget: string;
  department: string;
  documentStatus: string;
  todoProcessStatus: string;
  todoStatusUpdatedAt: string;
  finalScore: number;
  summaryConclusion: string;
  summaryConclusionLabel: string;
  suggestedAction: string;
  suggestedActionLabel: string;
  lowScoreDetailCount: number;
  assessedAt: string;
  latestBatchNo: string;
}

export interface RoleRow {
  id: string;
  lineNo: string;
  roleCode: string;
  roleName: string;
  permissionLevel: string;
  applyType: string;
  orgScopeCount: number;
  skipOrgScopeCheck: string;
}

export interface ApprovalRow {
  id: string;
  nodeName: string;
  approver: string;
  action: string;
  finishedAt: string;
  comment: string;
}

export interface OrgScopeRow {
  id: string;
  roleCode: string;
  roleName: string;
  organizationCode: string;
  organizationName: string;
  orgUnitName: string;
  physicalLevel: string;
  skipOrgScopeCheck: string;
}

export interface RiskDetailRow {
  id: string;
  dimensionName: string;
  ruleId: string;
  ruleSummary: string;
  roleCode: string;
  roleName: string;
  orgCode: string;
  score: number;
  detailConclusion: string;
  interventionAction: string;
}

export interface FeedbackGroupRow {
  id: string;
  category: string;
  title: string;
  summary: string;
  summaryLines?: string[];
  hint: string;
  rawDetailCount: number;
  affectedOrgUnitCount: number;
  affectedOrgCount: number;
  affectedRoleCount: number;
}

export interface FeedbackOverview {
  summaryConclusionLabel: string;
  feedbackStats: StatItem[];
  feedbackGroups: FeedbackGroupRow[];
  feedbackLines: string[];
}

export interface ProcessDetail {
  documentNo: string;
  overviewFields: DetailField[];
  feedbackOverview: FeedbackOverview;
  roles: RoleRow[];
  approvals: ApprovalRow[];
  orgScopes: OrgScopeRow[];
  riskDetails: RiskDetailRow[];
  notes: string[];
}

export interface ProcessApprovalRequest {
  action: "approve";
  approvalOpinion: string;
  dryRun: boolean;
}

export interface ProcessAuditRunRequest {
  documentNo: string;
  documentNos: string[];
  limit: number;
  dryRun: boolean;
}

export interface ProcessAuditRunSummary {
  id: string;
  taskId: string;
  status: string;
  requestedAt: string;
  startedAt: string;
  finishedAt: string;
  requestedDocumentNos: string[];
  requestedLimit: number;
  dryRun: boolean;
  documentCount: number;
  detailCount: number;
  assessmentBatchNo: string;
  assessmentVersion: string;
  message: string;
  dumpFile: string;
  summaryFile: string;
  logFile: string;
  outputTail: string;
}

export interface ProcessApprovalResponse {
  documentNo: string;
  action: string;
  ehrDecision: string;
  ehrSubmitLabel: string;
  approvalOpinion: string;
  dryRun: boolean;
  status: string;
  startedAt: string;
  finishedAt: string;
  logFile: string;
  screenshotFile: string;
  confirmationType?: string;
  confirmationMessage?: string;
  message: string;
}

export interface ProcessTodoSyncRequest {
  dryRun: boolean;
}

export interface ProcessTodoSyncResponse {
  taskId: string;
  status: string;
  dryRun: boolean;
  startedAt: string;
  finishedAt: string;
  projectDocumentCount: number;
  ehrTodoCount: number;
  pendingCount: number;
  processedCount: number;
  changedCount: number;
  unchangedCount: number;
  extraEhrTodoCount: number;
  message: string;
  dumpFile: string;
  logFile: string;
  outputTail: string;
}

export interface DistributionItem {
  id: string;
  label: string;
  count: number;
}

export interface DistributionSection {
  id: string;
  title: string;
  subtitle: string;
  items: DistributionItem[];
}

export interface ProcessBatchSummary {
  batchNo: string;
  assessmentVersion: string;
  documentCount: number;
  lowScoreDetailCount: number;
  detailCount: number;
  assessedAt: string;
}

export interface ProcessExecutionLogRow {
  id: string;
  batchNo: string;
  assessmentVersion: string;
  executedAt: string;
  documentCount: number;
  detailCount: number;
  sampleDocumentNo: string;
  sourceFile: string;
  persistedToDatabase: boolean;
}

export interface ProcessWorkbench {
  stats: StatItem[];
  documents: ProcessDocumentRow[];
}

export interface ProcessAnalysisDashboard {
  latestBatch: ProcessBatchSummary | null;
  distributionSections: DistributionSection[];
  executionLogs: ProcessExecutionLogRow[];
}

export interface ProcessDashboard {
  stats: StatItem[];
  latestBatch: ProcessBatchSummary | null;
  distributionSections: DistributionSection[];
  executionLogs: ProcessExecutionLogRow[];
  documents: ProcessDocumentRow[];
}

export interface RuntimeSettingsSummary {
  environmentLabel: string;
  configFile: string;
  stats: StatItem[];
  runtime: DetailField[];
  browser: DetailField[];
  database: DetailField[];
  paths: DetailField[];
  securityNotes: string[];
}
