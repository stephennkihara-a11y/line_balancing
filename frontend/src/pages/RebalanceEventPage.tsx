import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmt } from "@/lib/utils";
import type { RebalanceDiff } from "@/types";

export function RebalanceEventPage() {
  const { id } = useParams();
  const eventId = Number(id);
  const qc = useQueryClient();

  // List endpoint returns summary; we re-issue propose data via decide as a no-op
  // For simplicity we accept a fresh propose via the dashboard. Here we let user
  // accept/reject; the event row stores enough for an after-the-fact display.
  const { data: events } = useQuery({
    queryKey: ["events"],
    queryFn: () => api.get<any[]>("/rebalance/events?limit=200").then((r) => r.data),
  });
  const ev = (events || []).find((e) => e.id === eventId);

  // We fetched the new run's full layout to render the diff
  const newRun = useQuery({
    enabled: !!ev?.new_run_id,
    queryKey: ["run", ev?.new_run_id],
    queryFn: () => api.get(`/balance/runs/${ev!.new_run_id}`).then((r) => r.data),
  });
  const prevRun = useQuery({
    enabled: !!ev?.previous_run_id,
    queryKey: ["run", ev?.previous_run_id],
    queryFn: () => api.get(`/balance/runs/${ev!.previous_run_id}`).then((r) => r.data),
  });

  const decide = useMutation({
    mutationFn: (accepted: boolean) =>
      api.post<RebalanceDiff>(`/rebalance/events/${eventId}/decide`, { accepted }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["dash"] });
    },
  });

  if (!ev) return <p>Loading event…</p>;

  const prev = prevRun.data?.assignments || [];
  const next = newRun.data?.assignments || [];

  const byStationPrev = new Map<number, any[]>();
  prev.forEach((a: any) => {
    const arr = byStationPrev.get(a.station) || [];
    arr.push(a);
    byStationPrev.set(a.station, arr);
  });
  const byStationNext = new Map<number, any[]>();
  next.forEach((a: any) => {
    const arr = byStationNext.get(a.station) || [];
    arr.push(a);
    byStationNext.set(a.station, arr);
  });
  const allStations = Array.from(new Set([...byStationPrev.keys(), ...byStationNext.keys()])).sort((a, b) => a - b);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Re-balance · Event #{ev.id}</h1>
          <p className="text-muted-foreground text-sm">
            <Badge variant="warning" className="mr-2">{ev.trigger}</Badge>
            {new Date(ev.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/balance/runs/${ev.new_run_id}`}>
            <Button variant="outline">Open new run</Button>
          </Link>
          {ev.accepted == null && (
            <>
              <Button variant="destructive" onClick={() => decide.mutate(false)} disabled={decide.isPending}>Reject</Button>
              <Button onClick={() => decide.mutate(true)} disabled={decide.isPending}>{decide.isPending ? "Applying…" : "Accept & apply"}</Button>
            </>
          )}
          {ev.accepted === true && <Badge variant="success">Accepted</Badge>}
          {ev.accepted === false && <Badge variant="destructive">Rejected</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI label="Eff before" value={`${fmt(ev.eff_before || 0)}%`} />
        <KPI label="Eff after" value={`${fmt(ev.eff_after || 0)}%`} accent={(ev.eff_after || 0) >= (ev.eff_before || 0) ? "good" : "bad"} />
        <KPI label="Δ output / hr" value={ev.delta_output > 0 ? `+${ev.delta_output}` : `${ev.delta_output}`} accent={ev.delta_output >= 0 ? "good" : "bad"} />
        <KPI label="Stations" value={allStations.length} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Before vs After by station</CardTitle>
          <CardDescription>Highlighted rows show changed assignments.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <THead><TR>
              <TH>Station</TH>
              <TH>Operator (before)</TH><TH>Ops (before)</TH><TH>Cycle</TH>
              <TH>Operator (after)</TH><TH>Ops (after)</TH><TH>Cycle</TH>
            </TR></THead>
            <TBody>
              {allStations.map((st) => {
                const a = byStationPrev.get(st) || [];
                const b = byStationNext.get(st) || [];
                const opA = a[0]?.operator_name || "—";
                const opB = b[0]?.operator_name || "—";
                const codesA = a.map((x: any) => x.operation_code).join(", ");
                const codesB = b.map((x: any) => x.operation_code).join(", ");
                const cycA = a.reduce((s: number, x: any) => s + x.cycle_time, 0);
                const cycB = b.reduce((s: number, x: any) => s + x.cycle_time, 0);
                const changed = opA !== opB || codesA !== codesB;
                return (
                  <TR key={st} className={changed ? "bg-amber-50" : ""}>
                    <TD className="font-mono">{st}</TD>
                    <TD>{opA}</TD><TD className="text-xs font-mono">{codesA || "—"}</TD>
                    <TD>{fmt(cycA, 3)}</TD>
                    <TD>{opB}</TD><TD className="text-xs font-mono">{codesB || "—"}</TD>
                    <TD>{fmt(cycB, 3)}</TD>
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

function KPI({ label, value, accent }: { label: string; value: number | string; accent?: "good" | "bad" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`text-2xl font-semibold ${accent === "good" ? "text-emerald-600" : accent === "bad" ? "text-red-600" : ""}`}>{value}</div>
      </CardContent>
    </Card>
  );
}
