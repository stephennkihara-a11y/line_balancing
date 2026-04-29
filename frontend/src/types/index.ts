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
