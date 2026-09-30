"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ImportCsvError, sampleCsvUrl, showApiErrorToast } from "@/lib/api";
import type { ApiImportResult } from "@/lib/api-types";

interface CsvImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  sampleCsvPath: string;
  sampleFileName: string;
  onImport: (
    file: File,
    options: { skipErrors: boolean },
  ) => Promise<ApiImportResult>;
  onSuccess?: (result: ApiImportResult) => void | Promise<void>;
}

export function CsvImportDialog({
  open,
  onOpenChange,
  title,
  description,
  sampleCsvPath,
  sampleFileName,
  onImport,
  onSuccess,
}: CsvImportDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [skipErrors, setSkipErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ApiImportResult | null>(null);

  useEffect(() => {
    if (!open) {
      setFile(null);
      setSkipErrors(false);
      setResult(null);
      setSubmitting(false);
    }
  }, [open]);

  const handleImport = async () => {
    if (!file) {
      toast.error("Choose a CSV file first.");
      return;
    }

    setSubmitting(true);
    setResult(null);
    try {
      const importResult = await onImport(file, { skipErrors });
      setResult(importResult);
      if (importResult.imported_count > 0) {
        await onSuccess?.(importResult);
        if (importResult.error_count === 0) {
          toast.success(
            importResult.imported_count === 1
              ? "Imported 1 row."
              : `Imported ${importResult.imported_count} rows.`,
          );
          onOpenChange(false);
          return;
        }
        toast.warning(
          `Imported ${importResult.imported_count} rows; ${importResult.error_count} skipped.`,
        );
        return;
      }
      toast.error("No rows were imported.");
    } catch (error) {
      if (error instanceof ImportCsvError) {
        setResult(error.result);
        return;
      }
      showApiErrorToast(error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="csv-file">CSV file</Label>
            <Input
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setResult(null);
              }}
            />
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={skipErrors}
              onChange={(event) => setSkipErrors(event.target.checked)}
              className="size-4 rounded border"
            />
            Skip rows with errors and import the rest
          </label>

          {result ? (
            <div className="space-y-2 rounded-md border p-3">
              <p className="text-sm">
                Imported {result.imported_count}
                {result.skipped_count > 0
                  ? ` · Skipped ${result.skipped_count}`
                  : ""}
                {result.error_count > 0 ? ` · Errors ${result.error_count}` : ""}
              </p>
              {result.errors.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Row</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.errors.map((error) => (
                      <TableRow key={`${error.row}-${error.message}`}>
                        <TableCell>{error.row}</TableCell>
                        <TableCell className="text-destructive">
                          {error.message}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
            </div>
          ) : null}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
          <a
            className="text-sm font-medium text-primary hover:underline"
            href={sampleCsvUrl(sampleCsvPath)}
            download={sampleFileName}
          >
            Download sample CSV
          </a>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button onClick={() => void handleImport()} disabled={submitting || !file}>
              {submitting ? "Importing…" : "Import"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
