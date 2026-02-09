import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import ThemeToggle from "@/components/ThemeToggle";

const mockSetTheme = vi.fn();
let mockResolvedTheme = "light";
let mockTheme = "system";

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: mockTheme,
    resolvedTheme: mockResolvedTheme,
    setTheme: mockSetTheme,
  }),
}));

/**
 * Opens the DropdownMenu by dispatching pointer events
 * (Radix UI DropdownMenuTrigger listens to pointerdown, not click).
 */
async function openDropdown() {
  const button = screen.getByRole("button", { name: /Changer le thème/i });
  fireEvent.pointerDown(button, { button: 0, pointerType: "mouse" });
  await waitFor(() => {
    expect(screen.getByText("Clair")).toBeInTheDocument();
  });
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResolvedTheme = "light";
    mockTheme = "system";
  });

  it("renders theme toggle button", () => {
    render(<ThemeToggle />);

    expect(
      screen.getByRole("button", { name: /Changer le thème/i })
    ).toBeInTheDocument();
  });

  it("opens dropdown with three options", async () => {
    render(<ThemeToggle />);

    await openDropdown();

    expect(screen.getByText("Clair")).toBeInTheDocument();
    expect(screen.getByText("Sombre")).toBeInTheDocument();
    expect(screen.getByText("Système")).toBeInTheDocument();
  });

  it("calls setTheme('light') when clicking Clair", async () => {
    render(<ThemeToggle />);

    await openDropdown();
    fireEvent.click(screen.getByText("Clair"));

    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });

  it("calls setTheme('dark') when clicking Sombre", async () => {
    render(<ThemeToggle />);

    await openDropdown();
    fireEvent.click(screen.getByText("Sombre"));

    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("calls setTheme('system') when clicking Système", async () => {
    render(<ThemeToggle />);

    await openDropdown();
    fireEvent.click(screen.getByText("Système"));

    expect(mockSetTheme).toHaveBeenCalledWith("system");
  });

  it("shows Moon icon when resolved theme is dark", () => {
    mockResolvedTheme = "dark";
    mockTheme = "dark";

    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: /Changer le thème/i });
    expect(button.querySelector("svg")).toBeInTheDocument();
  });

  it("has no axe accessibility violations", async () => {
    const { container } = render(<ThemeToggle />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
