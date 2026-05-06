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

const DAY_MS = 24 * 60 * 60 * 1000;
const SOON_DUE_DAYS = 30;
const OVERDUE_DAYS = 60;


function relativeMaintenance(at: string | null): { label: string; tone: "ok" | "warn" | "danger" | "muted" } {
  if (!at) return { label: "Never", tone: "muted" };
  const diffDays = Math.floor((Date.now() - new Date(at).getTime()) / DAY_MS);
  const date = new Date(at).toLocaleDateString();
  if (diffDays < 1) return { label: `Today · ${date}`, tone: "ok" };
  if (diffDays < SOON_DUE_DAYS) return { label: `${diffDays}d ago · ${date}`, tone: "ok" };
  if (diffDays < OVERDUE_DAYS) return { label: `${diffDays}d ago · ${date}`, tone: "warn" };
  return { label: `${diffDays}d ago · ${date}`, tone: "danger" };
}


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

  type UpdatePayload =
    | { id: number; status: MachineStatus }
    | { id: number; last_maintenance_at: string | null };
  const update = useMutation({
    mutationFn: (payload: UpdatePayload) => {
      const { id, ...body } = payload;
      return api.put(`/machines/${id}`, body).then((r) => r.data);
    },
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
            <THead>
              <TR>
                <TH>Code</TH>
                <TH>Type</TH>
                <TH>Line</TH>
                <TH>Status</TH>
                <TH>Action</TH>
                <TH>Last maintenance</TH>
              </TR>
            </THead>
            <TBody>
              {(machines.data || []).map((m) => {
                const rel = relativeMaintenance(m.last_maintenance_at);
                const datePart = m.last_maintenance_at?.slice(0, 10) ?? "";
                return (
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
                    <TD>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            rel.tone === "danger" ? "destructive" :
                            rel.tone === "warn" ? "warning" :
                            rel.tone === "ok" ? "success" : "outline"
                          }
                          className="whitespace-nowrap"
                        >
                          {rel.label}
                        </Badge>
                        <Input
                          type="date"
                          className="h-8 w-36"
                          value={datePart}
                          onChange={(e) => {
                            const v = e.target.value;
                            update.mutate({
                              id: m.id,
                              last_maintenance_at: v ? new Date(v).toISOString() : null,
                            });
                          }}
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8"
                          onClick={() =>
                            update.mutate({ id: m.id, last_maintenance_at: new Date().toISOString() })
                          }
                          title="Record service today"
                        >
                          Today
                        </Button>
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
