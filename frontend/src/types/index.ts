export type MachineType =
  | "SNLS" | "OL" | "FOA" | "BARTACK" | "BUTTON" | "BUTTONHOLE" | "IRON" | "MANUAL";

export type MachineStatus = "WORKING" | "IDLE" | "BREAKDOWN" | "MAINTENANCE";
export type AttendanceStatus = "PRESENT" | "ABSENT" | "LEAVE";
export type BalanceStatus = "DRAFT" | "PROPOSED" | "APPLIED" | "REJECTED";
export type Role = "ADMIN" | "PRODUCTION_MANAGER" | "SUPERVISOR" | "IE" | "OPERATOR";

export interface Line {
  id: number;
  code: string;
  name: string;
  capacity: number;
  working_minutes: number;
  is_active: boolean;
}

export interface Machine {
  id: number;
  machine_code: string;
  type: MachineType;
  line_id: number | null;
  status: MachineStatus;
  notes: string | null;
  last_maintenance_at: string | null;
}

export interface Skill {
  operation_id: number;
  efficiency: number;
  is_certified: boolean;
}

export interface Operator {
  id: number;
  employee_code: string;
  name: string;
  grade: number;
  base_efficiency: number;
  current_line_id: number | null;
  attendance_status: AttendanceStatus;
  is_active: boolean;
  skills: Skill[];
}

export interface Operation {
  id: number;
  op_code: string;
  sequence: number;
  description: string;
  sam: number;
  machine_type: MachineType;
  skill_level: number;
  section: string | null;
}

export interface Style {
  id: number;
  style_code: string;
  name: string;
  garment_type: string | null;
  total_sam: number | null;
  description: string | null;
}

export interface StyleDetail extends Style {
  operations: Operation[];
  precedence: { predecessor_id: number; successor_id: number }[];
}

export interface Assignment {
  station: number;
  operator_id: number | null;
  operator_name: string | null;
  operation_id: number;
  operation_code: string;
  operation_description: string;
  machine_id: number | null;
  machine_type: MachineType;
  sam: number;
  cycle_time: number;
  expected_output: number | null;
}

export interface StationLoad {
  station: number;
  operator_id: number | null;
  operator_name: string | null;
  operation_ids: number[];
  operation_codes: string[];
  machine_type: MachineType;
  cycle_time: number;
  load_pct: number;
  is_bottleneck: boolean;
}

export interface BalanceResponse {
  run_id: number;
  style_id: number;
  line_id: number;
  takt_time: number;
  theoretical_ops: number;
  line_efficiency: number;
  balance_loss: number;
  bottleneck_station: number | null;
  bottleneck_operation_code: string | null;
  status: BalanceStatus;
  solver: string;
  solver_status: string;
  assignments: Assignment[];
  station_loads: StationLoad[];
  explanation: string | null;
  warnings: string[];
}

export interface BalanceRunSummary {
  id: number;
  style_id: number;
  line_id: number;
  target_output_hour: number;
  line_efficiency: number | null;
  balance_loss: number | null;
  status: BalanceStatus;
  created_at: string;
}

// ---------- Phase 2 ----------------------------------------------
export type RebalanceTrigger =
  | "OPERATOR_ABSENT" | "MACHINE_BREAKDOWN" | "TARGET_CHANGE"
  | "OUTPUT_DEVIATION" | "MANUAL";

export interface HourlyProduction {
  id: number;
  line_id: number;
  run_id: number | null;
  captured_at: string;
  hour_slot: number;
  target: number;
  actual: number;
  note: string | null;
}

export interface StationWIP {
  id: number;
  run_id: number;
  station: number;
  captured_at: string;
  wip_units: number;
  threshold: number;
}

export interface RebalanceCheck {
  line_id: number;
  run_id: number | null;
  triggered: boolean;
  trigger: RebalanceTrigger | null;
  reasons: string[];
  target_output_hour: number;
  last_hour_actual: number | null;
  deviation_pct: number | null;
  absent_operator_ids: number[];
  broken_machine_ids: number[];
}

export interface StationDiff {
  station: number;
  operator_before: string | null;
  operator_after: string | null;
  op_codes_before: string[];
  op_codes_after: string[];
  cycle_before: number;
  cycle_after: number;
  load_pct_before: number;
  load_pct_after: number;
  is_bottleneck_after: boolean;
}

export interface RebalanceDiff {
  event_id: number;
  previous_run_id: number | null;
  new_run_id: number;
  trigger: RebalanceTrigger;
  eff_before: number | null;
  eff_after: number;
  output_before: number | null;
  output_after: number;
  delta_eff: number;
  delta_output: number;
  diffs: StationDiff[];
  explanation: string | null;
  warnings: string[];
}

export interface BottleneckRootCause {
  cause: string;
  detail: string;
  suggestion: string;
}

export interface StationHeatPoint {
  station: number;
  operator_name: string | null;
  op_codes: string[];
  machine_type: MachineType;
  cycle_time: number;
  load_pct: number;
  is_bottleneck: boolean;
  wip_units: number | null;
  wip_threshold: number | null;
}

export interface WIPAlert {
  run_id: number;
  station: number;
  wip_units: number;
  threshold: number;
  severity: "warning" | "critical";
}

export interface BottleneckDashboard {
  line_id: number;
  run_id: number | null;
  line_efficiency: number | null;
  balance_loss: number | null;
  target_output_hour: number | null;
  heat: StationHeatPoint[];
  bottleneck_station: number | null;
  bottleneck_op_code: string | null;
  wip_alerts: WIPAlert[];
  root_causes: BottleneckRootCause[];
  last_hour: HourlyProduction | null;
}

// ---------- Phase 3 ----------------------------------------------
export interface TimeStudy {
  id: number;
  operation_id: number;
  operator_id: number | null;
  cycle_seconds: number;
  rating: number;
  allowance: number;
  captured_sam: number | null;
  sample_size: number;
  note: string | null;
  captured_at: string;
  operation_code: string | null;
  operation_description: string | null;
  standard_sam: number | null;
  deviation_pct: number | null;
}

export interface TimeStudyAggregate {
  operation_id: number;
  operation_code: string;
  standard_sam: number;
  captured_avg: number;
  captured_min: number;
  captured_max: number;
  sample_count: number;
  deviation_pct: number;
  flag: "ok" | "high" | "low";
}

export interface MachineUtilisation {
  machine_id: number;
  machine_code: string;
  type: MachineType;
  line_id: number | null;
  sample_count: number;
  running_pct: number;
  avg_rpm: number | null;
  last_seen: string | null;
  last_state: "RUNNING" | "IDLE";
}
