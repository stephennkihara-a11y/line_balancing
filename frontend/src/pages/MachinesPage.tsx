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
import type { Line, Machine, MachineStatus, MachineType } from "@/types";

const MACHINE_TYPES: MachineType[] = ["SNLS", "OL", "FOA", "BARTACK", "BUTTON", "BUTTONHOLE", "IRON", "MANUAL"];
const STATUSES: MachineStatus[] = ["WORKING", "IDLE", "BREAKDOWN", "MAINTENANCE"];

export function MachinesPage() {
  const qc = useQueryClient();
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });
  const machines = useQuery({
    queryKey: ["machines"], queryFn: () => api.get<Machine[]>("/machines").then((r) => r.data),
  });
  const [form, setForm] = useState({
    machine_code: "", type: "SNLS" as MachineType, line_id: undefined as number | undefined,
    status: "IDLE" as MachineStatus, notes: "",
  });
  const create = useMutation({
    mutationFn: (p: typeof form) => api.post("/machines", p).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["machines"] }),
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: number; status: MachineStatus }) =>
      api.put(`/machines/${id}`, { status }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["machines"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Machines</h1>
      <Card>
        <CardHeader><CardTitle>Add machine</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div><Label>Code</Label><Input value={form.machine_code} onChange={(e) => setForm({ ...form, machine_code: e.target.value })} /></div>
          <div>
            <Label>Type</Label>
            <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as MachineType })}>
              {MACHINE_TYPES.map((t) => <option key={t}>{t}</option>)}
            </Select>
          </div>
          <div>
            <Label>Line</Label>
            <Select value={form.line_id ?? ""} onChange={(e) => setForm({ ...form, line_id: e.target.value ? +e.target.value : undefined })}>
              <option value="">— unassigned —</option>
              {(lines.data || []).map((l) => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}
            </Select>
          </div>
          <div>
            <Label>Status</Label>
            <Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as MachineStatus })}>
              {STATUSES.map((s) => <option key={s}>{s}</option>)}
            </Select>
          </div>
          <div className="md:col-span-5">
            <Button onClick={() => create.mutate(form)} disabled={!form.machine_code}>
              {create.isPending ? "Saving…" : "Add machine"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>All machines ({machines.data?.length ?? 0})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <THead><TR><TH>Code</TH><TH>Type</TH><TH>Line</TH><TH>Status</TH><TH>Action</TH></TR></THead>
            <TBody>
              {(machines.data || []).map((m) => (
                <TR key={m.id}>
                  <TD className="font-mono">{m.machine_code}</TD>
                  <TD><Badge variant="secondary">{m.type}</Badge></TD>
                  <TD>{lines.data?.find((l) => l.id === m.line_id)?.code || "—"}</TD>
                  <TD>
                    <Badge variant={m.status === "BREAKDOWN" ? "destructive" : m.status === "WORKING" ? "success" : "outline"}>
                      {m.status}
                    </Badge>
                  </TD>
                  <TD>
                    <Select
                      value={m.status}
                      onChange={(e) => update.mutate({ id: m.id, status: e.target.value as MachineStatus })}
                      className="h-8 w-40"
                    >
                      {STATUSES.map((s) => <option key={s}>{s}</option>)}
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
