"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { LoadingState } from "@/components/states/LoadingState";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  sortable?: boolean;
  /** Hide this column on mobile's stacked-card layout (e.g. a rarely-needed column). */
  hideOnMobile?: boolean;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  getRowKey: (row: T) => string;
  isLoading?: boolean;
  searchPlaceholder?: string;
  searchValue?: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyState?: ReactNode;
  /** Extra filter controls (Selects, etc.) rendered above the table, in-context (UX-008). */
  filters?: ReactNode;
}

type SortDirection = "asc" | "desc" | null;

/**
 * Data table with built-in search/filter/sort (UX-008) and a stacked-card
 * fallback below the `md` breakpoint (NFR-015: dense tables are a
 * desktop/tablet pattern, not identical-layout-everywhere).
 */
export function DataTable<T>({
  columns,
  data,
  getRowKey,
  isLoading,
  searchPlaceholder = "Search...",
  searchValue,
  onRowClick,
  emptyState,
  filters,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);

  const filtered = useMemo(() => {
    if (!query || !searchValue) return data;
    const lower = query.toLowerCase();
    return data.filter((row) => searchValue(row).toLowerCase().includes(lower));
  }, [data, query, searchValue]);

  const sorted = useMemo(() => {
    if (!sortKey || !sortDirection) return filtered;
    const column = columns.find((c) => c.key === sortKey);
    if (!column?.sortValue) return filtered;
    const sign = sortDirection === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av < bv) return -1 * sign;
      if (av > bv) return 1 * sign;
      return 0;
    });
  }, [filtered, sortKey, sortDirection, columns]);

  function toggleSort(column: DataTableColumn<T>) {
    if (!column.sortable) return;
    if (sortKey !== column.key) {
      setSortKey(column.key);
      setSortDirection("asc");
    } else if (sortDirection === "asc") {
      setSortDirection("desc");
    } else {
      setSortKey(null);
      setSortDirection(null);
    }
  }

  if (isLoading) {
    return <LoadingState variant="table" />;
  }

  if (data.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div className="flex flex-col gap-3">
      {(searchValue || filters) && (
        <div className="flex flex-wrap items-center gap-2">
          {searchValue && (
            <div className="relative flex-1 min-w-[12rem]">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          )}
          {filters}
        </div>
      )}

      {sorted.length === 0 ? (
        <p className="py-8 text-center text-body text-muted-foreground">No results match your search.</p>
      ) : (
        <>
          {/* Desktop/tablet: real table */}
          <table className="hidden w-full border-collapse text-left md:table">
            <thead>
              <tr className="border-b border-border">
                {columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className="px-3 py-2 text-caption font-medium text-muted-foreground"
                  >
                    {column.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column)}
                        className="inline-flex items-center gap-1 hover:text-foreground"
                      >
                        {column.header}
                        {sortKey === column.key ? (
                          sortDirection === "asc" ? (
                            <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : (
                            <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                          )
                        ) : (
                          <ArrowUpDown className="h-3.5 w-3.5 opacity-40" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr
                  key={getRowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    "border-b border-border last:border-0",
                    onRowClick && "cursor-pointer hover:bg-muted",
                  )}
                >
                  {columns.map((column) => (
                    <td key={column.key} className="px-3 py-2.5 text-body">
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mobile: stacked cards (NFR-015) */}
          <div className="flex flex-col gap-2 md:hidden">
            {sorted.map((row) => (
              <div
                key={getRowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                role={onRowClick ? "button" : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                className={cn(
                  "flex flex-col gap-1.5 rounded-lg border border-border bg-card p-3",
                  onRowClick &&
                    "cursor-pointer active:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                {columns
                  .filter((c) => !c.hideOnMobile)
                  .map((column) => (
                    <div key={column.key} className="flex items-center justify-between gap-2">
                      <span className="text-caption text-muted-foreground">{column.header}</span>
                      <span className="text-body">{column.render(row)}</span>
                    </div>
                  ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
