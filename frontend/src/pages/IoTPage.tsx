import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { Line, MachineUtilisation } from "@/types";
import { fmt } from "@/lib/utils";

export function IoTPage() {
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data) });
  const [lineId, setLineId] = useState<number | "">("");
  const [minutes, setMinutes] = useState(60);

  const util = useQuery({
    queryKey: ["util", lineId, minutes],
    queryFn: () => {
      const params = new URLSearchParams();
      if (lineId !== "") params.set("line_id", String(lineId));
      params.set("minutes", String(minutes));
      return api.get<MachineUtilisation[]>(`/iot/utilisation?${params}`).then((r) => r.data);
    },
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Machine utilisation (IoT)</h1>
          <p className="text-muted-foreground text-sm">Live running % from telemetry over the selected window.</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <Label>Line</Label>
            <Select value={lineId} onChange={(e) => setLineId(e.target.value ? +e.target.value : "")}>
              <option value="">All</option>
              {(lines.data || []).map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
            </Select>
          </div>
          <div>
            <Label>Window (min)</Label>
            <Select value={minutes} onChange={(e) => setMinutes(+e.target.value)}>
              {[15, 30, 60, 120, 240, 480, 1440].map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Machines ({util.data?.length ?? 0})</CardTitle>
          <CardDescription>
            Send telemetry: <code>POST /api/iot/telemetry</code> with
            <code> {`{ events: [{machine_code, is_running, rpm?}] }`}</code>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Code</TH><TH>Type</TH><TH>Line</TH>
                <TH>Samples</TH><TH>Running %</TH><TH>Avg RPM</TH>
                <TH>Last seen</TH><TH>State</TH>
              </TR>
            </THead>
            <TBody>
              {(util.data || []).map((m) => (
                <TR key={m.machine_id}>
                  <TD className="font-mono">{m.machine_code}</TD>
                  <TD><Badge variant="secondary">{m.type}</Badge></TD>
                  <TD>{lines.data?.find((l) => l.id === m.line_id)?.code || "—"}</TD>
                  <TD>{m.sample_count}</TD>
                  <TD>
                    <div className="w-32 bg-muted rounded h-2 overflow-hidden">
                      <div
                        className={m.running_pct >= 70 ? "bg-emerald-500 h-full" : m.running_pct >= 40 ? "bg-amber-500 h-full" : "bg-red-500 h-full"}
                        style={{ width: `${Math.min(100, m.running_pct)}%` }}
                      />
                    </div>
                    <span className="text-xs ml-2">{fmt(m.running_pct, 1)}%</span>
                  </TD>
                  <TD>{m.avg_rpm ?? "—"}</TD>
                  <TD className="text-xs">{m.last_seen ? new Date(m.last_seen).toLocaleString() : "—"}</TD>
                  <TD>
                    <Badge variant={m.last_state === "RUNNING" ? "success" : "outline"}>{m.last_state}</Badge>
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
