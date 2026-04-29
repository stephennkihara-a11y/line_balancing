import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import type { BalanceRunSummary, Line, Operator, Style } from "@/types";
import { fmt } from "@/lib/utils";

export function Dashboard() {
  const styles = useQuery({ queryKey: ["styles"], queryFn: () => api.get<Style[]>("/styles").then((r) => r.data) });
  const operators = useQuery({
    queryKey: ["operators"],
    queryFn: () => api.get<Operator[]>("/operators").then((r) => r.data),
  });
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<BalanceRunSummary[]>("/balance/runs").then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-muted-foreground text-sm">Master data and recent balance runs.</p>
        </div>
        <Link to="/balance">
          <Button>Start a balance</Button>
        </Link>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI label="Styles" value={styles.data?.length ?? "—"} />
        <KPI label="Operators" value={operators.data?.length ?? "—"} />
        <KPI label="Lines" value={lines.data?.length ?? "—"} />
        <KPI label="Recent runs" value={runs.data?.length ?? "—"} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent balance runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.data && runs.data.length > 0 ? (
            <div className="divide-y">
              {runs.data.map((r) => (
                <Link
                  key={r.id}
                  to={`/balance/runs/${r.id}`}
                  className="flex items-center justify-between py-2 hover:bg-muted/40 px-2 rounded"
                >
                  <div>
                    <div className="font-medium">Run #{r.id} · target {r.target_output_hour}/hr</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()} · {r.status}
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    <div>Eff: <span className="font-mono">{fmt(Number(r.line_efficiency || 0))}%</span></div>
                    <div className="text-xs text-muted-foreground">Loss: {fmt(Number(r.balance_loss || 0))}%</div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No runs yet — start one from the Balance Wizard.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function KPI({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}
