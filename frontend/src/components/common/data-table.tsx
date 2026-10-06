"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface DataTableColumn<T> {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: DataTableColumn<T>[];
  searchPlaceholder?: string;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  getRowId: (row: T) => string;
  pageSize?: number;
  emptyState?: ReactNode;
  toolbar?: ReactNode;
  onRowClick?: (row: T) => void;
  selectedRowId?: string;
  hideSearch?: boolean;
}

export function DataTable<T>({
  data,
  columns,
  searchPlaceholder = "Search…",
  searchValue,
  onSearchChange,
  getRowId,
  pageSize = 10,
  emptyState,
  toolbar,
  onRowClick,
  selectedRowId,
  hideSearch = false,
}: DataTableProps<T>) {
  const [internalSearch, setInternalSearch] = useState("");
  const [page, setPage] = useState(0);

  const query = searchValue ?? internalSearch;
  const handleSearchChange = onSearchChange ?? setInternalSearch;

  const filteredData = useMemo(() => {
    if (!query.trim()) return data;
    const lower = query.toLowerCase();
    return data.filter((row) =>
      JSON.stringify(row).toLowerCase().includes(lower),
    );
  }, [data, query]);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const pageData = filteredData.slice(
    currentPage * pageSize,
    currentPage * pageSize + pageSize,
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {!hideSearch ? (
          <div className="relative w-full sm:max-w-sm">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => {
                setPage(0);
                handleSearchChange(event.target.value);
              }}
              placeholder={searchPlaceholder}
              className="pl-8"
            />
          </div>
        ) : null}
        {toolbar ? (
          <div className={`flex flex-wrap gap-2 ${hideSearch ? "w-full justify-end" : ""}`}>
            {toolbar}
          </div>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column.id} className={column.className}>
                  {column.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-32">
                  {emptyState ?? (
                    <p className="text-center text-sm text-muted-foreground">
                      No results found.
                    </p>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              pageData.map((row) => (
                <TableRow
                  key={getRowId(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  data-state={selectedRowId === getRowId(row) ? "selected" : undefined}
                  className={cn(onRowClick && "cursor-pointer")}
                >
                  {columns.map((column) => (
                    <TableCell key={column.id} className={column.className}>
                      {column.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {filteredData.length > pageSize ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <p>
            Showing {currentPage * pageSize + 1}–
            {Math.min((currentPage + 1) * pageSize, filteredData.length)} of{" "}
            {filteredData.length}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              disabled={currentPage === 0}
              onClick={() => setPage((value) => value - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft />
            </Button>
            <span>
              Page {currentPage + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((value) => value + 1)}
              aria-label="Next page"
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
