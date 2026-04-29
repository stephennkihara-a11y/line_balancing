import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmt } from "@/lib/utils";
import type { Style } from "@/types";

export function StylesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["styles"], queryFn: () => api.get<Style[]>("/styles").then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Styles</h1>
      <Card>
        <CardHeader><CardTitle>All styles</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? "Loading…" : (
            <Table>
              <THead><TR><TH>Code</TH><TH>Name</TH><TH>Garment</TH><TH>Total SAM (min)</TH><TH /></TR></THead>
              <TBody>
                {(data || []).map((s) => (
                  <TR key={s.id}>
                    <TD className="font-mono">{s.style_code}</TD>
                    <TD>{s.name}</TD>
                    <TD>{s.garment_type || "—"}</TD>
                    <TD>{fmt(Number(s.total_sam || 0), 3)}</TD>
                    <TD><Link to={`/styles/${s.id}`} className="text-primary underline-offset-4 hover:underline">Open</Link></TD>
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
