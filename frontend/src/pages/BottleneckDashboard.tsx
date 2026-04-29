import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmt } from "@/lib/utils";
import type {
  BottleneckDashboard, HourlyProduction, Line, RebalanceCheck, RebalanceDiff,
} from "@/types";

function loadColor(pct: number) {
  if (pct > 100) return "bg-red-500";
  if (pct >= 95) return "bg-amber-500";
  if (pct >= 85) return "bg-emerald-500";
  return "bg-sky-500";
}

export function BottleneckDashboardPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });
  const [lineId, setLineId] = useState<number | "">("");

  const dash = useQuery({
    enabled: lineId !== "",
    queryKey: ["dash", lineId],
    queryFn: () => api.get<BottleneckDashboard>(`/dashboard/bottleneck?line_id=${lineId}`).then((r) => r.data),
    refetchInterval: 30_000,
  });
  const trig = useQuery({
    enabled: lineId !== "",
    queryKey: ["check", lineId],
    queryFn: () => api.get<RebalanceCheck>(`/rebalance/check?line_id=${lineId}`).then((r) => r.data),
    refetchInterval: 30_000,
  });
  const hourly = useQuery({
    enabled: lineId !== "",
    queryKey: ["hourly", lineId],
    queryFn: () => api.get<HourlyProduction[]>(`/production/hourly?line_id=${lineId}&limit=12`).then((r) => r.data),
    refetchInterval: 30_000,
  });

  const propose = useMutation({
    mutationFn: () =>
      api.post<RebalanceDiff>("/rebalance/propose", {
        line_id: lineId, trigger: trig.data?.trigger || "MANUAL", explain: true,
      }).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["dash", lineId] });
      nav(`/rebalance/events/${data.event_id}`);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-semibold">Bottleneck dashboard</h1>
        <div className="flex items-center gap-2">
          <Label className="text-sm">Line</Label>
          <Select value={lineId} onChange={(e) => setLineId(e.target.value ? +e.target.value : "")} className="w-48">
            <option value="">Select…</option>
            {(lines.data || []).map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
          </Select>
        </div>
      </div>

      {lineId === "" ? (
        <p className="text-muted-foreground">Pick a line to view its current state.</p>
      ) : dash.isLoading ? (
        <p>Loading…</p>
      ) : !dash.data?.run_id ? (
        <p className="text-muted-foreground">No active balance run on this line yet — start one from the Balance Wizard.</p>
      ) : (
        <>
          {/* Trigger banner */}
          {trig.data?.triggered && (
            <Card className="border-amber-500/60 bg-amber-50">
              <CardHeader>
                <CardTitle className="text-amber-900">Re-balance suggested</CardTitle>
                <CardDescription className="text-amber-800">
                  Trigger: <Badge variant="warning">{trig.data.trigger}</Badge>
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-start gap-4">
                <ul className="text-sm list-disc pl-5">
                  {trig.data.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                <Button onClick={() => propose.mutate()} disabled={propose.isPending}>
                  {propose.isPending ? "Proposing…" : "Propose new balance"}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <KPI label="Line efficiency" value={`${fmt(dash.data.line_efficiency || 0)}%`} accent={(dash.data.line_efficiency || 0) >= 85 ? "good" : "bad"} />
            <KPI label="Balance loss" value={`${fmt(dash.data.balance_loss || 0)}%`} accent={(dash.data.balance_loss || 0) <= 15 ? "good" : "bad"} />
            <KPI label="Target / hr" value={dash.data.target_output_hour ?? "—"} />
            <KPI label="WIP alerts" value={dash.data.wip_alerts.length} accent={dash.data.wip_alerts.length ? "bad" : "good"} />
            <KPI label="Last hour" value={dash.data.last_hour ? `${dash.data.last_hour.actual}/${dash.data.last_hour.target}` : "—"} />
          </div>

          {/* Heatmap */}
          <Card>
            <CardHeader>
              <CardTitle>Station heatmap</CardTitle>
              <CardDescription>
                Red &gt;100% · Amber 95–100% · Green 85–95% · Blue &lt;85%. Bottleneck has a red ring.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-1.5 overflow-x-auto pb-2 min-h-[220px]">
                {dash.data.heat.map((s) => (
                  <div key={s.station} className="flex flex-col items-center gap-1 shrink-0">
                    <div
                      className={`w-10 rounded-t transition ${loadColor(s.load_pct)} ${s.is_bottleneck ? "ring-2 ring-red-700" : ""}`}
                      style={{ height: `${Math.max(8, s.load_pct * 1.8)}px` }}
                      title={`Station ${s.station}: ${fmt(s.cycle_time, 3)} min (${fmt(s.load_pct, 1)}%)`}
                    />
                    {s.wip_units != null && (
                      <Badge variant={s.wip_units >= (s.wip_threshold || 0) ? "destructive" : "outline"} className="text-[10px]">
                        WIP {s.wip_units}
                      </Badge>
                    )}
                    <div className="text-xs font-mono">{s.station}</div>
                    <div className="text-[10px] text-muted-foreground w-12 truncate text-center">{s.operator_name || "—"}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Root causes */}
          {dash.data.root_causes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Root-cause analysis</CardTitle>
                <CardDescription>Heuristic suggestions for the bottleneck station.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {dash.data.root_causes.map((rc, i) => (
                    <div key={i} className="border rounded-md p-3">
                      <Badge variant="secondary" className="mb-1 capitalize">{rc.cause.replace("_", " ")}</Badge>
                      <div className="text-sm">{rc.detail}</div>
                      <div className="text-sm text-muted-foreground italic mt-1">→ {rc.suggestion}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Hourly production capture */}
          <HourlyCapture lineId={lineId as number} runId={dash.data.run_id!} target={dash.data.target_output_hour ?? 60} hourly={hourly.data || []} />

          {/* WIP capture */}
          <WIPCapture runId={dash.data.run_id!} stations={dash.data.heat.map((h) => h.station)} />
        </>
      )}
    </div>
  );
}

function KPI({ label, value, accent }: { label: string; value: number | string; accent?: "good" | "bad" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`text-2xl font-semibold ${accent === "good" ? "text-emerald-600" : accent === "bad" ? "text-red-600" : ""}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function HourlyCapture({ lineId, runId, target, hourly }: { lineId: number; runId: number; target: number; hourly: HourlyProduction[] }) {
  const qc = useQueryClient();
  const [hour, setHour] = useState(1);
  const [actual, setActual] = useState(0);
  const [t, setT] = useState(target);
  const post = useMutation({
    mutationFn: () =>
      api.post("/production/hourly", { line_id: lineId, run_id: runId, hour_slot: hour, target: t, actual }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hourly", lineId] });
      qc.invalidateQueries({ queryKey: ["check", lineId] });
      qc.invalidateQueries({ queryKey: ["dash", lineId] });
      setActual(0);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hourly production</CardTitle>
        <CardDescription>Capture each hour's count to drive the deviation trigger.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <div><Label>Hour</Label><Input type="number" min={1} max={24} value={hour} onChange={(e) => setHour(+e.target.value)} /></div>
          <div><Label>Target</Label><Input type="number" value={t} onChange={(e) => setT(+e.target.value)} /></div>
          <div><Label>Actual</Label><Input type="number" value={actual} onChange={(e) => setActual(+e.target.value)} /></div>
          <div className="md:col-span-2 flex items-end">
            <Button onClick={() => post.mutate()} disabled={post.isPending}>{post.isPending ? "Saving…" : "Add hour"}</Button>
          </div>
        </div>
        <Table>
          <THead><TR><TH>Captured</TH><TH>Hour</TH><TH>Target</TH><TH>Actual</TH><TH>Δ%</TH></TR></THead>
          <TBody>
            {hourly.map((h) => {
              const dev = h.target ? ((h.actual - h.target) / h.target) * 100 : 0;
              return (
                <TR key={h.id}>
                  <TD className="text-xs">{new Date(h.captured_at).toLocaleString()}</TD>
                  <TD>{h.hour_slot}</TD>
                  <TD>{h.target}</TD>
                  <TD>{h.actual}</TD>
                  <TD className={Math.abs(dev) > 15 ? "text-red-600 font-medium" : ""}>{fmt(dev, 1)}%</TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function WIPCapture({ runId, stations }: { runId: number; stations: number[] }) {
  const qc = useQueryClient();
  const [station, setStation] = useState(stations[0] ?? 1);
  const [wip, setWip] = useState(0);
  const [threshold, setThreshold] = useState(25);
  const post = useMutation({
    mutationFn: () => api.post("/production/wip", { run_id: runId, station, wip_units: wip, threshold }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dash"] });
      setWip(0);
    },
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>WIP capture</CardTitle>
        <CardDescription>Recorded WIP shows on the heatmap and triggers alerts when ≥ threshold.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <div>
          <Label>Station</Label>
          <Select value={station} onChange={(e) => setStation(+e.target.value)}>
            {stations.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </div>
        <div><Label>WIP units</Label><Input type="number" value={wip} onChange={(e) => setWip(+e.target.value)} /></div>
        <div><Label>Threshold</Label><Input type="number" value={threshold} onChange={(e) => setThreshold(+e.target.value)} /></div>
        <div className="md:col-span-2 flex items-end">
          <Button onClick={() => post.mutate()} disabled={post.isPending}>{post.isPending ? "Saving…" : "Save WIP"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}
