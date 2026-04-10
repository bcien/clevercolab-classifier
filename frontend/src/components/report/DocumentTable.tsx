import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DOC_TYPE_LABELS, type ProcessedDocument } from "@/lib/types";

interface DocumentTableProps {
  documents: ProcessedDocument[];
}

function confidenceColor(c: number): string {
  if (c >= 0.9) return "bg-emerald-100 text-emerald-800";
  if (c >= 0.7) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

export function DocumentTable({ documents }: DocumentTableProps) {
  return (
    <div className="rounded-lg border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tipo</TableHead>
            <TableHead>Confianza</TableHead>
            <TableHead>Archivo original</TableHead>
            <TableHead>Archivo renombrado</TableHead>
            <TableHead>Datos extra&iacute;dos</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc, i) => (
            <TableRow key={i}>
              <TableCell className="font-medium">
                {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
              </TableCell>
              <TableCell>
                <Badge
                  variant="secondary"
                  className={confidenceColor(doc.confidence)}
                >
                  {(doc.confidence * 100).toFixed(0)}%
                </Badge>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-48 truncate">
                {doc.original_filename}
              </TableCell>
              <TableCell className="text-xs font-mono">
                {doc.renamed_filename}
              </TableCell>
              <TableCell className="text-xs max-w-64">
                <ExtractedDataSummary data={doc.extracted_data} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ExtractedDataSummary({
  data,
}: {
  data: ProcessedDocument["extracted_data"];
}) {
  const items: string[] = [];

  if (data.transport_ids.length > 0)
    items.push(`ID: ${data.transport_ids.join(", ")}`);
  if (data.container_numbers.length > 0)
    items.push(`Cont: ${data.container_numbers.join(", ")}`);
  if (data.invoice_numbers.length > 0)
    items.push(`Fact: ${data.invoice_numbers.join(", ")}`);
  if (data.consignee) items.push(`Consig: ${data.consignee}`);
  if (data.shipper) items.push(`Emb: ${data.shipper}`);

  if (items.length === 0) return <span className="text-muted-foreground">-</span>;

  return <span className="text-muted-foreground">{items.join(" | ")}</span>;
}
