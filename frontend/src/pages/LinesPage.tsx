import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import type { Line } from "@/types";

export function LinesPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["lines"], queryFn: () => api.get<Line[]>("/lines").then((r) => r.data),
  });
  const [form, setForm] = useState({ code: "", name: "", capacity: 30, working_minutes: 480 });
  const create = useMutation({
    mutationFn: (payload: typeof form) => api.post<Line>("/lines", payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lines"] });
      setForm({ code: "", name: "", capacity: 30, working_minutes: 480 });
    },
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Lines</h1>
      <Card>
        <CardHeader><CardTitle>Add a line</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div><Label>Code</Label><Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
          <div className="md:col-span-2"><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><Label>Capacity</Label><Input type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: +e.target.value })} /></div>
          <div><Label>Working min/day</Label><Input type="number" value={form.working_minutes} onChange={(e) => setForm({ ...form, working_minutes: +e.target.value })} /></div>
          <div className="md:col-span-5">
            <Button onClick={() => create.mutate(form)} disabled={!form.code || !form.name}>
              {create.isPending ? "Saving…" : "Add line"}
            </Button>
            {create.error && <span className="text-destructive text-sm ml-3">{(create.error as any).response?.data?.detail || "Failed"}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>All lines</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? "Loading…" : (
            <Table>
              <THead><TR><TH>Code</TH><TH>Name</TH><TH>Capacity</TH><TH>Working min</TH><TH>Active</TH></TR></THead>
              <TBody>
                {(data || []).map((l) => (
                  <TR key={l.id}>
                    <TD className="font-mono">{l.code}</TD>
                    <TD>{l.name}</TD>
                    <TD>{l.capacity}</TD>
                    <TD>{l.working_minutes}</TD>
                    <TD>{l.is_active ? "Yes" : "No"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
