import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Square, Save, Trash2, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmt } from "@/lib/utils";
import type { Operator, Style, StyleDetail, TimeStudy, TimeStudyAggregate } from "@/types";

/**
 * Mobile-friendly time-study capture with built-in stopwatch.
 * Tap the big button to start/stop; "Lap" stores a sample. When ready, save.
 */
export function TimeStudyPage() {
  const qc = useQueryClient();
  const styles = useQuery({ queryKey: ["styles"], queryFn: () => api.get<Style[]>("/styles").then((r) => r.data) });
  const operators = useQuery({ queryKey: ["operators"], queryFn: () => api.get<Operator[]>("/operators").then((r) => r.data) });

  const [styleId, setStyleId] = useState<number | "">("");
  const [opId, setOpId] = useState<number | "">("");
  const [operatorId, setOperatorId] = useState<number | "">("");
  const [rating, setRating] = useState(100);
  const [allowance, setAllowance] = useState(15);
  const [note, setNote] = useState("");
  const [samples, setSamples] = useState<number[]>([]); // seconds

  const styleDetail = useQuery({
    enabled: styleId !== "",
    queryKey: ["style-detail", styleId],
    queryFn: () => api.get<StyleDetail>(`/styles/${styleId}`).then((r) => r.data),
  });

  // Stopwatch
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0); // ms since start
  const startedAt = useRef<number | null>(null);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      if (startedAt.current) setElapsed(Date.now() - startedAt.current);
    }, 100);
    return () => clearInterval(id);
  }, [running]);

  const start = () => { startedAt.current = Date.now(); setElapsed(0); setRunning(true); };
  const lap = () => {
    if (!running || !startedAt.current) return;
    const sec = (Date.now() - startedAt.current) / 1000;
    setSamples((s) => [...s, +sec.toFixed(2)]);
    startedAt.current = Date.now();
    setElapsed(0);
  };
  const stop = () => { setRunning(false); };

  const save = useMutation({
    mutationFn: async () => {
      if (samples.length === 0 || !opId) throw new Error("No samples or no operation");
      // Save mean sample with sample_size — server captures the SAM.
      const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
      const { data } = await api.post<TimeStudy>("/time-studies", {
        operation_id: opId,
        operator_id: operatorId || null,
        cycle_seconds: avg,
        rating, allowance,
        sample_size: samples.length,
        note: note || null,
      });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-studies"] });
      setSamples([]);
      setNote("");
    },
  });

  const recent = useQuery({
    enabled: opId !== "",
    queryKey: ["time-studies", opId],
    queryFn: () => api.get<TimeStudy[]>(`/time-studies?operation_id=${opId}&limit=20`).then((r) => r.data),
  });

  const aggregate = useQuery({
    enabled: styleId !== "",
    queryKey: ["ts-agg", styleId],
    queryFn: () => api.get<TimeStudyAggregate[]>(`/time-studies/aggregate?style_id=${styleId}`).then((r) => r.data),
  });

  const op = styleDetail.data?.operations.find((o) => o.id === opId);
  const avgSec = samples.length ? samples.reduce((a, b) => a + b, 0) / samples.length : 0;
  const previewSAM = avgSec > 0 ? (avgSec / 60) * (rating / 100) * (1 + allowance / 100) : 0;

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold">Time study</h1>

      <Card>
        <CardHeader>
          <CardTitle>Pick operation</CardTitle>
          <CardDescription>Choose a style and the operation you're timing.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div>
            <Label>Style</Label>
            <Select value={styleId} onChange={(e) => { setStyleId(e.target.value ? +e.target.value : ""); setOpId(""); }}>
              <option value="">Select style…</option>
              {(styles.data || []).map((s) => <option key={s.id} value={s.id}>{s.style_code}</option>)}
            </Select>
          </div>
          <div>
            <Label>Operation</Label>
            <Select value={opId} onChange={(e) => setOpId(e.target.value ? +e.target.value : "")}>
              <option value="">Select op…</option>
              {(styleDetail.data?.operations || []).map((o) => (
                <option key={o.id} value={o.id}>{o.op_code} — {o.description}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Operator</Label>
            <Select value={operatorId} onChange={(e) => setOperatorId(e.target.value ? +e.target.value : "")}>
              <option value="">— optional —</option>
              {(operators.data || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Stopwatch */}
      <Card>
        <CardHeader><CardTitle>Stopwatch</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="text-center">
            <div className="text-6xl font-mono tabular-nums">
              {(elapsed / 1000).toFixed(1)}
              <span className="text-2xl text-muted-foreground ml-1">s</span>
            </div>
            {op && (
              <div className="text-xs text-muted-foreground mt-1">
                Standard SAM: <span className="font-mono">{fmt(op.sam, 3)}</span> min ({fmt(op.sam * 60, 1)}s)
              </div>
            )}
          </div>
          <div className="flex justify-center gap-2 flex-wrap">
            {!running ? (
              <Button size="lg" onClick={start} disabled={!opId}>
                <Play className="h-4 w-4 mr-2" /> Start
              </Button>
            ) : (
              <>
                <Button size="lg" variant="secondary" onClick={lap}>
                  <Plus className="h-4 w-4 mr-2" /> Lap
                </Button>
                <Button size="lg" variant="destructive" onClick={stop}>
                  <Square className="h-4 w-4 mr-2" /> Stop
                </Button>
              </>
            )}
          </div>
          {samples.length > 0 && (
            <div className="space-y-1">
              <div className="text-sm flex items-center justify-between">
                <span className="text-muted-foreground">Samples ({samples.length})</span>
                <button className="text-xs text-destructive flex items-center gap-1" onClick={() => setSamples([])}>
                  <Trash2 className="h-3 w-3" /> Clear
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                {samples.map((s, i) => (
                  <Badge key={i} variant="outline" className="font-mono">{s.toFixed(2)}s</Badge>
                ))}
              </div>
              <div className="text-sm">
                Avg cycle: <span className="font-mono">{avgSec.toFixed(2)}</span> s ·
                Captured SAM (preview): <span className="font-mono">{previewSAM.toFixed(3)}</span> min
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Rating · allowance · note</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <div><Label>Rating %</Label><Input type="number" value={rating} onChange={(e) => setRating(+e.target.value)} /></div>
          <div><Label>Allowance %</Label><Input type="number" value={allowance} onChange={(e) => setAllowance(+e.target.value)} /></div>
          <div className="md:col-span-2"><Label>Note</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional remarks" /></div>
          <div className="md:col-span-4">
            <Button onClick={() => save.mutate()} disabled={save.isPending || samples.length === 0 || !opId}>
              <Save className="h-4 w-4 mr-2" /> {save.isPending ? "Saving…" : "Save time study"}
            </Button>
            {save.error && <span className="text-destructive text-sm ml-3">{(save.error as any).message || "Failed"}</span>}
            {save.isSuccess && <span className="text-emerald-600 text-sm ml-3">Saved.</span>}
          </div>
        </CardContent>
      </Card>

      {/* Recent captures with deviation flags */}
      {opId !== "" && (
        <Card>
          <CardHeader><CardTitle>Recent captures · {op?.op_code}</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <THead><TR><TH>When</TH><TH>Cycle (s)</TH><TH>SAM</TH><TH>Standard</TH><TH>Δ%</TH><TH>n</TH></TR></THead>
              <TBody>
                {(recent.data || []).map((r) => (
                  <TR key={r.id}>
                    <TD className="text-xs">{new Date(r.captured_at).toLocaleString()}</TD>
                    <TD>{fmt(r.cycle_seconds, 2)}</TD>
                    <TD>{fmt(r.captured_sam || 0, 3)}</TD>
                    <TD>{fmt(r.standard_sam || 0, 3)}</TD>
                    <TD className={Math.abs(r.deviation_pct || 0) >= 10 ? "text-red-600 font-medium" : ""}>
                      {fmt(r.deviation_pct || 0, 1)}%
                    </TD>
                    <TD>{r.sample_size}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Style-level aggregate */}
      {aggregate.data && aggregate.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Style aggregate (captured vs standard)</CardTitle>
            <CardDescription>Operations flagged when avg deviates ≥ 10% from standard.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <THead><TR><TH>Op</TH><TH>Std</TH><TH>Avg</TH><TH>Min</TH><TH>Max</TH><TH>n</TH><TH>Δ%</TH><TH>Flag</TH></TR></THead>
              <TBody>
                {aggregate.data.map((a) => (
                  <TR key={a.operation_id}>
                    <TD className="font-mono">{a.operation_code}</TD>
                    <TD>{fmt(a.standard_sam, 3)}</TD>
                    <TD>{fmt(a.captured_avg, 3)}</TD>
                    <TD>{fmt(a.captured_min, 3)}</TD>
                    <TD>{fmt(a.captured_max, 3)}</TD>
                    <TD>{a.sample_count}</TD>
                    <TD>{fmt(a.deviation_pct, 1)}%</TD>
                    <TD>
                      <Badge variant={a.flag === "ok" ? "success" : a.flag === "high" ? "destructive" : "warning"}>
                        {a.flag}
                      </Badge>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
