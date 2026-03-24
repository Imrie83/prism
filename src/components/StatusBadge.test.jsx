import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge from "./StatusBadge.jsx";

describe("StatusBadge", () => {
  it("should render 'new' status correctly", () => {
    render(<StatusBadge status="new" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("should render 'pending' status with 'Unscanned' label", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("Unscanned")).toBeInTheDocument();
  });

  it("should render 'queued' status", () => {
    render(<StatusBadge status="queued" />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });

  it("should render 'scanning' status", () => {
    render(<StatusBadge status="scanning" />);
    expect(screen.getByText("Scanning")).toBeInTheDocument();
  });

  it("should render 'scanned' status", () => {
    render(<StatusBadge status="scanned" />);
    expect(screen.getByText("Scanned")).toBeInTheDocument();
  });

  it("should render 'emailed' status", () => {
    render(<StatusBadge status="emailed" />);
    expect(screen.getByText("Emailed")).toBeInTheDocument();
  });

  it("should render 'skipped' status", () => {
    render(<StatusBadge status="skipped" />);
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("should fallback to 'new' for unknown status", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("should apply correct styling for status colors", () => {
    const { container: newContainer } = render(<StatusBadge status="new" />);
    const { container: scannedContainer } = render(<StatusBadge status="scanned" />);
    const { container: emailedContainer } = render(<StatusBadge status="emailed" />);

    const newBadge = newContainer.querySelector("span");
    const scannedBadge = scannedContainer.querySelector("span");
    const emailedBadge = emailedContainer.querySelector("span");

    expect(newBadge).toHaveStyle({ color: "var(--blue)" });
    expect(scannedBadge).toHaveStyle({ color: "var(--green)" });
    expect(emailedBadge).toHaveStyle({ color: "var(--accent)" });
  });

  it("should have correct background colors per status", () => {
    const { container: newContainer } = render(<StatusBadge status="new" />);
    const { container: pendingContainer } = render(<StatusBadge status="pending" />);

    const newBadge = newContainer.querySelector("span");
    const pendingBadge = pendingContainer.querySelector("span");

    // Check that the style attribute contains the expected CSS variable
    expect(newBadge.style.background).toContain("var(--blue-glow)");
    expect(pendingBadge.style.background).toContain("var(--surface)");
  });

  it("should render with correct styling", () => {
    const { container } = render(<StatusBadge status="new" />);
    const badge = container.querySelector("span");

    // Check styling values directly on the style object
    expect(badge.style.fontSize).toBe("10px");
    expect(badge.style.fontWeight).toBe("700");
    expect(badge.style.borderRadius).toBe("99px");
    expect(badge.style.whiteSpace).toBe("nowrap");
  });
});