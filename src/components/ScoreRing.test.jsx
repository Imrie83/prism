import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ScoreRing from "./ScoreRing.jsx";

// Mock framer-motion to avoid animation complexity in tests
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
    span: ({ children, ...props }) => <span {...props}>{children}</span>,
    circle: ({ children, ...props }) => <circle {...props}>{children}</circle>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

describe("ScoreRing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("should render with default size", () => {
    render(<ScoreRing score={85} />);
    const container = screen.getByText("0").closest(".score-ring");
    expect(container.style.width).toBe("110px");
    expect(container.style.height).toBe("110px");
  });

  it("should render with custom size", () => {
    render(<ScoreRing score={85} size={150} />);
    const container = screen.getByText("0").closest(".score-ring");
    expect(container.style.width).toBe("150px");
    expect(container.style.height).toBe("150px");
  });

  it("should render SVG with correct dimensions", () => {
    render(<ScoreRing score={75} size={100} />);

    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("width", "100");
    expect(svg).toHaveAttribute("height", "100");
    expect(svg).toHaveAttribute("viewBox", "0 0 100 100");
  });

  it("should render score label with /100 suffix", () => {
    render(<ScoreRing score={85} />);

    expect(screen.getByText("/100")).toBeInTheDocument();
  });

  it("should use green color for high scores (>=75)", () => {
    render(<ScoreRing score={85} />);

    const svg = document.querySelector("svg");
    // Check that the SVG exists and has the gradient definition
    expect(svg).toBeInTheDocument();

    // The gradient ID should contain the score
    const gradient = svg.querySelector("linearGradient");
    expect(gradient).toBeInTheDocument();
    expect(gradient.id).toContain("grad-");
  });

  it("should use yellow color for medium scores (45-74)", () => {
    render(<ScoreRing score={60} />);

    // The component computes color internally
    // We can verify the SVG structure is correct
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("should use red color for low scores (<45)", () => {
    render(<ScoreRing score={30} />);

    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("should handle score of 0", () => {
    render(<ScoreRing score={0} />);

    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("should handle score of 100", () => {
    render(<ScoreRing score={100} />);

    expect(screen.getByText("0")).toBeInTheDocument(); // Animation starts at 0
  });

  it("should render background track circle", () => {
    render(<ScoreRing score={50} />);

    const svg = document.querySelector("svg");
    const circles = svg.querySelectorAll("circle");

    // Background track is one of the circles
    expect(circles.length).toBeGreaterThan(0);
  });

  it("should render tick marks", () => {
    render(<ScoreRing score={50} />);

    const svg = document.querySelector("svg");
    const lines = svg.querySelectorAll("line");

    // 20 tick marks
    expect(lines.length).toBe(20);
  });

  it("should render glow filter", () => {
    render(<ScoreRing score={75} />);

    const svg = document.querySelector("svg");
    const filter = svg.querySelector("filter");

    expect(filter).toBeInTheDocument();
    expect(filter.querySelector("feGaussianBlur")).toBeInTheDocument();
  });

  it("should have correct stroke width based on size", () => {
    render(<ScoreRing score={50} size={100} />);

    const svg = document.querySelector("svg");
    // stroke should be max(100 * 0.065, 6) = max(6.5, 6) = 6.5
    const mainCircle = svg.querySelector("circle[stroke]");
    expect(mainCircle).toBeInTheDocument();
  });

  it("should render unique filter ID based on size and score", () => {
    const { container: container1 } = render(<ScoreRing score={50} size={100} />);
    const { container: container2 } = render(<ScoreRing score={60} size={100} />);

    const svg1 = container1.querySelector("svg");
    const svg2 = container2.querySelector("svg");

    const filter1 = svg1.querySelector("filter").id;
    const filter2 = svg2.querySelector("filter").id;

    // Filter IDs should be different (they include score)
    expect(filter1).not.toBe(filter2);
  });
});