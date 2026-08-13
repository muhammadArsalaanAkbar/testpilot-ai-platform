import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { DataTable, type DataTableColumn } from "@/components/DataTable";

interface Row {
  id: string;
  title: string;
  priority: number;
}

const rows: Row[] = [
  { id: "1", title: "Login form validates email", priority: 2 },
  { id: "2", title: "Checkout accepts valid card", priority: 1 },
  { id: "3", title: "Search returns matching results", priority: 3 },
];

const columns: DataTableColumn<Row>[] = [
  { key: "title", header: "Title", render: (r) => r.title },
  {
    key: "priority",
    header: "Priority",
    render: (r) => String(r.priority),
    sortable: true,
    sortValue: (r) => r.priority,
  },
];

function renderTable() {
  render(
    <DataTable
      columns={columns}
      data={rows}
      getRowKey={(r) => r.id}
      searchValue={(r) => r.title}
      searchPlaceholder="Search test cases"
    />,
  );
  // The component renders both a desktop <table> and a mobile stacked-card
  // list simultaneously, toggling visibility via CSS breakpoints — jsdom
  // does not evaluate media queries, so both are present in the DOM at
  // once. Scope assertions to the desktop table to avoid ambiguous matches.
  return screen.getAllByRole("table")[0]!;
}

describe("DataTable", () => {
  it("renders every row initially", () => {
    const table = renderTable();
    expect(within(table).getAllByRole("row")).toHaveLength(rows.length + 1); // + header row
  });

  it("filters rows in-context via the search box (UX-008)", async () => {
    const table = renderTable();
    const search = screen.getByLabelText("Search test cases");
    await userEvent.type(search, "checkout");
    expect(within(table).getByText("Checkout accepts valid card")).toBeInTheDocument();
    expect(within(table).queryByText("Login form validates email")).not.toBeInTheDocument();
  });

  it("shows a no-results message when the search matches nothing", async () => {
    renderTable();
    await userEvent.type(screen.getByLabelText("Search test cases"), "nonexistent");
    expect(screen.getByText("No results match your search.")).toBeInTheDocument();
  });

  it("sorts by a sortable column when its header is activated", async () => {
    const table = renderTable();
    const sortButton = within(table).getByRole("button", { name: /Priority/ });
    await userEvent.click(sortButton);
    const cells = within(table).getAllByRole("row").slice(1); // skip header row
    const firstRowText = within(cells[0]!).getAllByRole("cell")[1]?.textContent;
    expect(firstRowText).toBe("1"); // ascending: lowest priority value first
  });
});
