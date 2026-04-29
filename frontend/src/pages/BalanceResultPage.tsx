import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmt } from "@/lib/utils";
import { useState } from "react";
import type { BalanceResponse, StationLoad } from "@/types";

function loadColor(pct: number): string {
  // Heatmap: red >100 / amber 95–100 / green 85–95 / blue <85
  if (pct > 100) return "bg-red-500";
  if (pct >= 95) return "bg-amber-500";
  if (pct >= 85) return "bg-emerald-500";
  return "bg-sky-500";
}

export function BalanceResultPage() {
  const { id } = useParams();
  const runId = Number(id);
  const qc = useQueryClient();
  const [question, setQuestion] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.get<BalanceResponse>(`/balance/runs/${runId}`).then((r) => r.data),
  });

  const apply = useMutation({
    mutationFn: () => api.post(`/balance/runs/${runId}/apply`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["run", runId] }),
  });

  const explain = useMutation({
    mutationFn: () => api.post(`/balance/runs/${runId}/explain`, { question }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["run", runId] }),
  });

  if (isLoading || !data) return <div>Loading…</div>;

  const ops = data.station_loads;
  const maxLoad = Math.max(...ops.map((s) => s.cycle_time), 0.0001);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Balance result · Run #{data.run_id}</h1>
          <p className="text-muted-foreground text-sm">
            Solver: {data.solver} ({data.solver_status}) · Status: {data.status}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => apply.mutate()} disabled={data.status === "APPLIED"}>
            {data.status === "APPLIED" ? "Applied" : apply.isPending ? "Applying…" : "Apply to line"}
          </Button>
        </div>
      </div>

      {data.warnings?.length ? (
        <Card>
          <CardHeader><CardTitle className="text-amber-700">Solver warnings</CardTitle></CardHeader>
          <CardContent>
            <ul className="text-sm list-disc pl-5">
              {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KPI label="Takt time (min)" value={fmt(data.takt_time, 3)} />
        <KPI label="Theoretical ops" value={data.theoretical_ops} />
        <KPI label="Stations" value={data.station_loads.length} />
        <KPI label="Line efficiency" value={`${fmt(data.line_efficiency)}%`} accent={data.line_efficiency >= 85 ? "good" : "bad"} />
        <KPI label="Balance loss" value={`${fmt(data.balance_loss)}%`} accent={data.balance_loss <= 15 ? "good" : "bad"} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Station heatmap</CardTitle>
          <CardDescription>
            Bar height = cycle time vs. bottleneck. Red &gt; 100% · Amber 95–100% · Green 85–95% · Blue &lt; 85%.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-1.5 overflow-x-auto pb-2 min-h-[200px]">
            {ops.map((s) => (
              <div key={s.station} className="flex flex-col items-center gap-1 shrink-0">
                <div
                  className={`w-10 rounded-t transition ${loadColor(s.load_pct)} ${
                    s.is_bottleneck ? "ring-2 ring-red-700" : ""
                  }`}
                  style={{ height: `${Math.max(8, (s.cycle_time / maxLoad) * 180)}px` }}
                  title={`Station ${s.station}: ${fmt(s.cycle_time, 3)} min (${fmt(s.load_pct, 1)}%)`}
                />
                <div className="text-xs font-mono">{s.station}</div>
                <div className="text-[10px] text-muted-foreground w-12 truncate text-center">{s.operator_name || "—"}</div>
              </div>
            ))}
          </div>
          {data.bottleneck_station != null && (
            <p className="text-sm mt-3">
              <Badge variant="destructive">Bottleneck</Badge> Station {data.bottleneck_station}
              {data.bottleneck_operation_code ? <> · op <span className="font-mono">{data.bottleneck_operation_code}</span></> : null}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Operator-by-operator layout</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <THead><TR>
              <TH>Station</TH><TH>Operator</TH><TH>Operation</TH><TH>Machine</TH>
              <TH>SAM</TH><TH>Cycle (min)</TH><TH>Output / hr</TH>
            </TR></THead>
            <TBody>
              {data.assignments.map((a) => {
                const station = data.station_loads.find((s) => s.station === a.station);
                return (
                  <TR key={a.station + a.operation_code} className={station?.is_bottleneck ? "bg-red-50" : ""}>
                    <TD className="font-mono">{a.station}</TD>
                    <TD>{a.operator_name || "—"}</TD>
                    <TD>
                      <div className="font-mono text-xs">{a.operation_code}</div>
                      <div className="text-xs text-muted-foreground">{a.operation_description}</div>
                    </TD>
                    <TD><Badge variant="secondary">{a.machine_type}</Badge></TD>
                    <TD>{fmt(a.sam, 3)}</TD>
                    <TD className="font-mono">{fmt(a.cycle_time, 3)}</TD>
                    <TD>{a.expected_output ?? "—"}</TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI explanation & what-if</CardTitle>
          <CardDescription>Powered by Claude. Ask follow-up questions about this layout.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.explanation ? (
            <pre className="whitespace-pre-wrap text-sm bg-muted/40 p-3 rounded border">{data.explanation}</pre>
          ) : (
            <p className="text-muted-foreground text-sm">No explanation generated yet.</p>
          )}
          <div className="flex gap-2">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What if Asha is absent? How can we hit 80/hr?"
            />
            <Button onClick={() => explain.mutate()} disabled={explain.isPending}>
              {explain.isPending ? "Asking Claude…" : "Ask"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function KPI({ label, value, accent }: { label: string; value: number | string; accent?: "good" | "bad" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div
          className={`text-2xl font-semibold ${
            accent === "good" ? "text-emerald-600" : accent === "bad" ? "text-red-600" : ""
          }`}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
