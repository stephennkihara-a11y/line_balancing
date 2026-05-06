import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { fmt } from "@/lib/utils";
import type { BalanceResponse, Line, Operator, Style } from "@/types";

interface Suggestion {
  style_id: number;
  line_id: number;
  total_sam_min: number;
  operators_used: number;
  efficiency_pct: number;
  working_minutes: number;
  suggested_output_hour: number;
  suggested_output_day: number;
  takt_time_min: number;
  theoretical_operators_at_target: number | null;
  bottleneck_op_min: number | null;
  bottleneck_op_code: string | null;
  notes: string[];
}

const EFF_PRESETS: { label: string; value: number; hint: string }[] = [
  { label: "Ramp-up", value: 55, hint: "First weeks of a new style" },
  { label: "Established", value: 80, hint: "Industry standard for a settled line" },
  { label: "World-class", value: 90, hint: "Sustained on benchmark factories" },
];

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

  // Suggestion controls
  const selectedLine = useMemo(
    () => lines.data?.find((l) => l.id === lineId) || null,
    [lines.data, lineId],
  );
  const [plannedOperators, setPlannedOperators] = useState<number>(30);
  const [efficiency, setEfficiency] = useState<number>(80);

  // When the line changes, default the planned-operator count to the line's
  // declared capacity and the working-minutes-per-day to the line's value.
  useEffect(() => {
    if (selectedLine) {
      setPlannedOperators(selectedLine.capacity || 30);
      setWorkingMins(selectedLine.working_minutes || 480);
    }
  }, [selectedLine]);

  const presentOps = (operators.data || []).filter((o) => o.attendance_status === "PRESENT");
  const opsForLine = lineId ? presentOps.filter((o) => o.current_line_id === lineId || o.current_line_id == null) : presentOps;

  // Live suggestion
  const suggestion = useQuery<Suggestion>({
    enabled: styleId !== "" && lineId !== "" && plannedOperators > 0 && efficiency > 0,
    queryKey: ["suggestion", styleId, lineId, plannedOperators, efficiency, workingMins, target],
    queryFn: () =>
      api.post<Suggestion>("/balance/suggest", {
        style_id: styleId,
        line_id: lineId,
        operators: plannedOperators,
        efficiency_pct: efficiency,
        working_minutes: workingMins,
        target_output_hour: target,
      }).then((r) => r.data),
  });

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

  const applySuggestion = () => {
    if (suggestion.data) setTarget(suggestion.data.suggested_output_hour);
  };

  const canRun = styleId !== "" && lineId !== "" && target > 0;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Balance Wizard</h1>

      <Card>
        <CardHeader>
          <CardTitle>1 · Pick style and line</CardTitle>
          <CardDescription>
            The line's planned operator count below defaults to the line's
            declared capacity — change it to a different staffing scenario
            and watch the suggested output update.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>Style</Label>
            <Select value={styleId} onChange={(e) => setStyleId(e.target.value ? +e.target.value : "")}>
              <option value="">Select style…</option>
              {(styles.data || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.style_code} — {s.name}
                  {s.total_sam ? ` · ${(+s.total_sam).toFixed(2)} min SAM` : ""}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Line</Label>
            <Select value={lineId} onChange={(e) => setLineId(e.target.value ? +e.target.value : "")}>
              <option value="">Select line…</option>
              {(lines.data || []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.code} — {l.name} (capacity {l.capacity})
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Suggestion engine ----------------------------------------- */}
      <Card className="border-primary/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> 2 · Suggested output (industrial garment)
          </CardTitle>
          <CardDescription>
            Computes <code>output/hr ≈ (operators × 60 × efficiency) / total SAM</code>
            and caps it by the heaviest single operation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <Label>Planned operators on the line</Label>
              <Input type="number" min={1} value={plannedOperators} onChange={(e) => setPlannedOperators(+e.target.value)} />
              {selectedLine && (
                <p className="text-xs text-muted-foreground mt-1">
                  Line capacity is set to <span className="font-mono">{selectedLine.capacity}</span> in master data.
                </p>
              )}
            </div>
            <div>
              <Label>Industrial garment efficiency</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="range"
                  min={30}
                  max={100}
                  value={efficiency}
                  onChange={(e) => setEfficiency(+e.target.value)}
                  className="flex-1"
                />
                <span className="text-sm font-mono w-12 text-right">{efficiency}%</span>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {EFF_PRESETS.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setEfficiency(p.value)}
                    title={p.hint}
                    className={`text-xs rounded border px-2 py-0.5 ${
                      efficiency === p.value ? "bg-primary text-primary-foreground" : "bg-muted/50"
                    }`}
                  >
                    {p.label} {p.value}%
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label>Working minutes / day</Label>
              <Input type="number" min={60} value={workingMins} onChange={(e) => setWorkingMins(+e.target.value)} />
            </div>
          </div>

          {suggestion.data ? (
            <div className="rounded-md border bg-muted/40 p-3 space-y-2">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <Stat label="Total SAM" value={`${fmt(suggestion.data.total_sam_min, 2)} min`} />
                <Stat
                  label="Suggested output"
                  value={`${suggestion.data.suggested_output_hour}/hr`}
                  accent="good"
                />
                <Stat label="Per shift" value={`${suggestion.data.suggested_output_day} pcs`} />
                <Stat label="Takt time" value={`${fmt(suggestion.data.takt_time_min, 3)} min`} />
              </div>
              {suggestion.data.bottleneck_op_code && (
                <div className="text-xs">
                  Heaviest single op:{" "}
                  <Badge variant="secondary" className="font-mono">{suggestion.data.bottleneck_op_code}</Badge>{" "}
                  at {fmt(suggestion.data.bottleneck_op_min || 0, 3)} min
                  &nbsp;→ ceiling ≈ {Math.floor(60 / (suggestion.data.bottleneck_op_min || 1))}/hr.
                </div>
              )}
              <ul className="text-sm list-disc pl-5 space-y-0.5">
                {suggestion.data.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button size="sm" onClick={applySuggestion} variant="default">
                  Use {suggestion.data.suggested_output_hour}/hr as target
                </Button>
                {suggestion.data.theoretical_operators_at_target != null && (
                  <span className="text-xs text-muted-foreground">
                    To hit {target}/hr you'd need ≈{" "}
                    <span className="font-mono">{suggestion.data.theoretical_operators_at_target}</span> operators.
                  </span>
                )}
              </div>
            </div>
          ) : suggestion.isLoading && styleId !== "" && lineId !== "" ? (
            <p className="text-sm text-muted-foreground">Computing suggestion…</p>
          ) : (
            <p className="text-sm text-muted-foreground">Pick a style and line to see a suggestion.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3 · Confirm target</CardTitle>
          <CardDescription>
            The solver minimises the bottleneck cycle time to hit this target.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>Target output / hour</Label>
            <Input type="number" min={1} value={target} onChange={(e) => setTarget(+e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            4 · Operators ({selectedOps.size > 0 ? `${selectedOps.size} selected` : "all available"})
          </CardTitle>
          <CardDescription>
            Leave all unselected to use every <em>PRESENT</em> operator on the chosen line.
            Click rows to override; the suggestion above uses the planned count, not this list.
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
        <CardHeader><CardTitle>5 · Run</CardTitle></CardHeader>
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

function Stat({ label, value, accent }: { label: string; value: string; accent?: "good" }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-xl font-semibold ${accent === "good" ? "text-emerald-600" : ""}`}>{value}</div>
    </div>
  );
}
