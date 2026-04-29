import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fmt } from "@/lib/utils";
import { useRef, useState } from "react";
import type { StyleDetail } from "@/types";

export function StyleDetailPage() {
  const { id } = useParams();
  const styleId = Number(id);
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const { data: style, isLoading } = useQuery({
    queryKey: ["style", styleId],
    queryFn: () => api.get<StyleDetail>(`/styles/${styleId}`).then((r) => r.data),
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/imports/operation-bulletin/${styleId}`, fd);
      return data;
    },
    onSuccess: () => {
      setUploadMsg("Imported successfully");
      qc.invalidateQueries({ queryKey: ["style", styleId] });
    },
    onError: (e: any) => setUploadMsg(e.response?.data?.detail || "Import failed"),
  });

  if (isLoading || !style) return <div>Loading…</div>;

  // Build successor map for display
  const succMap = new Map<number, number[]>();
  style.precedence.forEach((p) => {
    if (!succMap.has(p.predecessor_id)) succMap.set(p.predecessor_id, []);
    succMap.get(p.predecessor_id)!.push(p.successor_id);
  });

  const opByCode = new Map(style.operations.map((o) => [o.id, o.op_code]));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{style.name}</h1>
        <p className="text-muted-foreground text-sm">{style.style_code} · {style.garment_type}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI label="Operations" value={style.operations.length} />
        <KPI label="Total SAM (min)" value={fmt(Number(style.total_sam || 0), 3)} />
        <KPI label="Precedence edges" value={style.precedence.length} />
        <KPI label="Sections" value={new Set(style.operations.map((o) => o.section)).size} />
      </div>

      <Card>
        <CardHeader><CardTitle>Import operation bulletin</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            <Input type="file" accept=".csv,.xlsx,.xls" ref={fileRef} />
            <Button
              onClick={() => {
                const f = fileRef.current?.files?.[0];
                if (f) upload.mutate(f);
              }}
              disabled={upload.isPending}
            >
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            CSV columns: <code>op_code, sequence, description, sam, machine_type, skill_level, section, predecessors</code>.
            Existing operations will be replaced.
          </p>
          {uploadMsg && <p className="text-sm">{uploadMsg}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Operations</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <THead><TR>
              <TH>Seq</TH><TH>Code</TH><TH>Description</TH><TH>SAM</TH>
              <TH>Machine</TH><TH>Skill</TH><TH>Section</TH><TH>Successors</TH>
            </TR></THead>
            <TBody>
              {style.operations.map((o) => (
                <TR key={o.id}>
                  <TD>{o.sequence}</TD>
                  <TD className="font-mono">{o.op_code}</TD>
                  <TD>{o.description}</TD>
                  <TD>{fmt(o.sam, 3)}</TD>
                  <TD><Badge variant="secondary">{o.machine_type}</Badge></TD>
                  <TD>{o.skill_level}</TD>
                  <TD>{o.section || "—"}</TD>
                  <TD className="text-xs">
                    {(succMap.get(o.id) || []).map((sid) => opByCode.get(sid)).filter(Boolean).join(", ") || "—"}
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

function KPI({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}
