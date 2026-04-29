import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { BalanceResponse, Line, Operator, Style } from "@/types";

export function BalanceWizard() {
  const nav = useNavigate();
  const styles = useQuery({ queryKey: ["styles"], queryFn: () => api.get<Style[]>("/styles").then((r) => r.data) });
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });
  const operators = useQuery({
    queryKey: ["operators"], queryFn: () => api.get<Operator[]>("/operators").then((r) => r.data),
  });

  const [styleId, setStyleId] = useState<number | "">("");
  const [lineId, setLineId] = useState<number | "">("");
  const [target, setTarget] = useState(60);
  const [workingMins, setWorkingMins] = useState(480);
  const [explain, setExplain] = useState(true);
  const [selectedOps, setSelectedOps] = useState<Set<number>>(new Set());

  const presentOps = (operators.data || []).filter((o) => o.attendance_status === "PRESENT");
  const opsForLine = lineId ? presentOps.filter((o) => o.current_line_id === lineId || o.current_line_id == null) : presentOps;

  const run = useMutation({
    mutationFn: () =>
      api.post<BalanceResponse>("/balance/run", {
        style_id: styleId, line_id: lineId,
        target_output_hour: target, working_minutes: workingMins,
        available_operator_ids: selectedOps.size > 0 ? Array.from(selectedOps) : undefined,
        explain,
      }).then((r) => r.data),
    onSuccess: (data) => nav(`/balance/runs/${data.run_id}`),
  });

  const toggleOp = (id: number) => {
    const next = new Set(selectedOps);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedOps(next);
  };

  const canRun = styleId !== "" && lineId !== "" && target > 0;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Balance Wizard</h1>
      <Card>
        <CardHeader>
          <CardTitle>1 · Run inputs</CardTitle>
          <CardDescription>Choose style, line, target output and working minutes.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <Label>Style</Label>
            <Select value={styleId} onChange={(e) => setStyleId(e.target.value ? +e.target.value : "")}>
              <option value="">Select style…</option>
              {(styles.data || []).map((s) => <option key={s.id} value={s.id}>{s.style_code} — {s.name}</option>)}
            </Select>
          </div>
          <div>
            <Label>Line</Label>
            <Select value={lineId} onChange={(e) => setLineId(e.target.value ? +e.target.value : "")}>
              <option value="">Select line…</option>
              {(lines.data || []).map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
            </Select>
          </div>
          <div>
            <Label>Target output / hour</Label>
            <Input type="number" min={1} value={target} onChange={(e) => setTarget(+e.target.value)} />
          </div>
          <div>
            <Label>Working minutes / day</Label>
            <Input type="number" min={60} value={workingMins} onChange={(e) => setWorkingMins(+e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2 · Operators ({selectedOps.size > 0 ? `${selectedOps.size} selected` : "all available"})</CardTitle>
          <CardDescription>
            Leave all unselected to use every <em>PRESENT</em> operator on the chosen line. Click rows to override.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 max-h-72 overflow-auto">
            {opsForLine.map((o) => (
              <label
                key={o.id}
                className={`flex items-start gap-2 px-2 py-1.5 rounded border cursor-pointer text-sm ${
                  selectedOps.has(o.id) ? "bg-primary/10 border-primary" : ""
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={selectedOps.has(o.id)}
                  onChange={() => toggleOp(o.id)}
                />
                <div className="leading-tight">
                  <div className="font-medium">{o.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {o.employee_code} · G{o.grade} · {o.base_efficiency}% · {o.skills.length} skills
                  </div>
                </div>
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>3 · Run</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-3 items-center">
          <label className="text-sm flex items-center gap-2">
            <input type="checkbox" checked={explain} onChange={(e) => setExplain(e.target.checked)} />
            Generate Claude explanation
          </label>
          <Button onClick={() => run.mutate()} disabled={!canRun || run.isPending}>
            {run.isPending ? "Solving…" : "Solve and view layout"}
          </Button>
          {run.error && (
            <span className="text-destructive text-sm">
              {(run.error as any).response?.data?.detail || "Solver failed"}
            </span>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
