import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PaginationFooter from "./PaginationFooter.jsx";

describe("PaginationFooter", () => {
  const defaultProps = {
    page: 1,
    totalPages: 5,
    total: 100,
    perPage: 20,
    onPage: vi.fn(),
  };

  it("should not render when totalPages <= 1", () => {
    const { container } = render(
      <PaginationFooter {...defaultProps} totalPages={1} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("should display correct range for first page", () => {
    render(<PaginationFooter {...defaultProps} page={1} />);

    expect(screen.getByText("1-20 of 100")).toBeInTheDocument();
  });

  it("should display correct range for middle page", () => {
    render(<PaginationFooter {...defaultProps} page={3} />);

    expect(screen.getByText("41-60 of 100")).toBeInTheDocument();
  });

  it("should display correct range for last page", () => {
    render(<PaginationFooter {...defaultProps} page={5} />);

    expect(screen.getByText("81-100 of 100")).toBeInTheDocument();
  });

  it("should display 'All' when perPage is 0", () => {
    render(<PaginationFooter {...defaultProps} perPage={0} />);

    expect(screen.getByText("All 100")).toBeInTheDocument();
  });

  it("should call onPage when clicking page numbers", () => {
    const onPage = vi.fn();
    render(<PaginationFooter {...defaultProps} onPage={onPage} />);

    fireEvent.click(screen.getByText("3"));

    expect(onPage).toHaveBeenCalledWith(3);
  });

  it("should call onPage when clicking next button", () => {
    const onPage = vi.fn();
    render(<PaginationFooter {...defaultProps} page={1} onPage={onPage} />);

    const buttons = screen.getAllByRole("button");
    // Last button is next (ChevronRight)
    const nextBtn = buttons[buttons.length - 1];

    fireEvent.click(nextBtn);

    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("should call onPage when clicking prev button", () => {
    const onPage = vi.fn();
    render(<PaginationFooter {...defaultProps} page={2} onPage={onPage} />);

    const buttons = screen.getAllByRole("button");
    // First button is prev (ChevronLeft)
    const prevBtn = buttons[0];

    fireEvent.click(prevBtn);

    expect(onPage).toHaveBeenCalledWith(1);
  });

  it("should disable prev button on first page", () => {
    render(<PaginationFooter {...defaultProps} page={1} />);

    const buttons = screen.getAllByRole("button");
    const prevBtn = buttons[0];

    expect(prevBtn).toBeDisabled();
  });

  it("should disable next button on last page", () => {
    render(<PaginationFooter {...defaultProps} page={5} />);

    const buttons = screen.getAllByRole("button");
    const nextBtn = buttons[buttons.length - 1];

    expect(nextBtn).toBeDisabled();
  });

  it("should highlight current page", () => {
    render(<PaginationFooter {...defaultProps} page={3} />);

    const pageButtons = screen.getAllByRole("button").slice(1, -1); // Exclude prev/next

    expect(pageButtons[2]).toHaveStyle({
      background: "var(--blue-glow)",
      fontWeight: "700",
    });
  });

  it("should show windowed page numbers for many pages", () => {
    render(<PaginationFooter {...defaultProps} totalPages={20} page={10} />);

    // Should show window around current page (pages 7-13)
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("11")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
  });

  it("should show first pages when near start", () => {
    render(<PaginationFooter {...defaultProps} totalPages={20} page={2} />);

    // Should show pages 1-7
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("should show last pages when near end", () => {
    render(<PaginationFooter {...defaultProps} totalPages={20} page={19} />);

    // Should show pages 14-20
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("should show all pages when totalPages <= 7", () => {
    render(<PaginationFooter {...defaultProps} totalPages={5} />);

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});