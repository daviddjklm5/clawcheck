export type Tone = "default" | "success" | "warning" | "danger" | "info";

export interface StatItem {
  label: string;
  value: string;
  hint: string;
  tone: Tone;
}

export interface ActionCard {
  id: string;
  title: string;
  description: string;
  buttonLabel: string;
  command: string;
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
  jobs: JobRow[];
}

export interface CollectDocumentRow {
  id: string;
  documentNo: string;
  applicantName: string;
  applicantNo: string;
  subject: string;
  documentStatus: string;
  collectedAt: string;
  roleCount: number;
  approvalCount: number;
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
  basicInfo: DetailField[];
  tableStatus: TableStatusRow[];
  nextActions: string[];
}

export interface CollectDashboard {
  stats: StatItem[];
  scopes: ActionCard[];
  documents: CollectDocumentRow[];
  detailsByDocumentNo: Record<string, CollectDetail>;
}

export interface ProcessDocumentRow {
  id: string;
  documentNo: string;
  applicantName: string;
  applicantNo: string;
  permissionTarget: string;
  department: string;
  documentStatus: string;
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
  message: string;
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
