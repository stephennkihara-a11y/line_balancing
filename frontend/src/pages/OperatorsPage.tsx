import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { AttendanceStatus, Line, Operator } from "@/types";

const ATTEND: AttendanceStatus[] = ["PRESENT", "ABSENT", "LEAVE"];

export function OperatorsPage() {
  const qc = useQueryClient();
  const operators = useQuery({
    queryKey: ["operators"], queryFn: () => api.get<Operator[]>("/operators").then((r) => r.data),
  });
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });

  const [form, setForm] = useState({
    employee_code: "", name: "", grade: 1, base_efficiency: 80,
    current_line_id: undefined as number | undefined, attendance_status: "PRESENT" as AttendanceStatus,
  });
  const create = useMutation({
    mutationFn: (p: typeof form) => api.post("/operators", { ...p, skills: [] }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["operators"] });
      setForm({ employee_code: "", name: "", grade: 1, base_efficiency: 80, current_line_id: undefined, attendance_status: "PRESENT" });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, attendance_status }: { id: number; attendance_status: AttendanceStatus }) =>
      api.put(`/operators/${id}`, { attendance_status }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["operators"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Operators</h1>
      <Card>
        <CardHeader><CardTitle>Add operator</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <div><Label>Code</Label><Input value={form.employee_code} onChange={(e) => setForm({ ...form, employee_code: e.target.value })} /></div>
          <div className="md:col-span-2"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><Label>Grade (1–5)</Label><Input type="number" min={1} max={5} value={form.grade} onChange={(e) => setForm({ ...form, grade: +e.target.value })} /></div>
          <div><Label>Base eff %</Label><Input type="number" value={form.base_efficiency} onChange={(e) => setForm({ ...form, base_efficiency: +e.target.value })} /></div>
          <div>
            <Label>Line</Label>
            <Select value={form.current_line_id ?? ""} onChange={(e) => setForm({ ...form, current_line_id: e.target.value ? +e.target.value : undefined })}>
              <option value="">—</option>
              {(lines.data || []).map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
            </Select>
          </div>
          <div className="md:col-span-6">
            <Button onClick={() => create.mutate(form)} disabled={!form.employee_code || !form.name}>
              {create.isPending ? "Saving…" : "Add operator"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>All operators ({operators.data?.length ?? 0})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <THead><TR>
              <TH>Code</TH><TH>Name</TH><TH>Grade</TH><TH>Base eff %</TH><TH>Line</TH>
              <TH>Skills</TH><TH>Attendance</TH>
            </TR></THead>
            <TBody>
              {(operators.data || []).map((o) => (
                <TR key={o.id}>
                  <TD className="font-mono">{o.employee_code}</TD>
                  <TD>{o.name}</TD>
                  <TD>{o.grade}</TD>
                  <TD>{o.base_efficiency}</TD>
                  <TD>{lines.data?.find((l) => l.id === o.current_line_id)?.code || "—"}</TD>
                  <TD><Badge variant="secondary">{o.skills?.length ?? 0}</Badge></TD>
                  <TD>
                    <Select
                      value={o.attendance_status}
                      onChange={(e) => update.mutate({ id: o.id, attendance_status: e.target.value as AttendanceStatus })}
                      className="h-8 w-32"
                    >
                      {ATTEND.map((s) => <option key={s}>{s}</option>)}
                    </Select>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
