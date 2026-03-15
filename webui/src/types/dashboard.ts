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
  department: string;
  documentStatus: string;
  riskLevel: string;
  trustLevel: string;
  recommendation: string;
  submittedAt: string;
}

export interface RoleRow {
  id: string;
  roleCode: string;
  roleName: string;
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
  skipOrgScopeCheck: string;
}

export interface RiskDetailRow {
  id: string;
  ruleCode: string;
  ruleName: string;
  result: string;
  riskLevel: string;
  trustLevel: string;
  hitDetail: string;
}

export interface ProcessDetail {
  basicInfo: DetailField[];
  roles: RoleRow[];
  approvals: ApprovalRow[];
  orgScopes: OrgScopeRow[];
  riskDetails: RiskDetailRow[];
  notes: string[];
}

export interface ProcessDashboard {
  stats: StatItem[];
  documents: ProcessDocumentRow[];
  detailsByDocumentNo: Record<string, ProcessDetail>;
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
