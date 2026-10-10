"use client";

import { Upload } from "lucide-react";
import { useState } from "react";

import { CsvImportDialog } from "@/components/common/csv-import-dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface CatalogCsvImportProps {
  label?: string;
  onImported: () => Promise<void>;
}

export function CatalogCsvImport({ label = "Import CSV", onImported }: CatalogCsvImportProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)}>
        <Upload />
        {label}
      </Button>
      <CsvImportDialog
        open={open}
        onOpenChange={setOpen}
        title="Import catalog CSV"
        description="Each row is a product. The supplier column creates suppliers, and a quantity posts an opening-balance adjustment at the given location."
        sampleCsvPath={api.products.sampleCsvHref}
        sampleFileName="catalog-sample.csv"
        onImport={(file, options) => api.products.importCsv(file, options)}
        onSuccess={onImported}
      />
    </>
  );
}
