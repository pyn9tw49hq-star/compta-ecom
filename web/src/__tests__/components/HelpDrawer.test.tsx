import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import HelpDrawer from "@/components/HelpDrawer";

describe("HelpDrawer", () => {
  // --- Rendering tests (AC: 13) ---

  it("displays title when open", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(
      screen.getByText("Comment nommer vos fichiers")
    ).toBeInTheDocument();
  });

  it("does not render content when closed", () => {
    render(<HelpDrawer isOpen={false} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByText("Comment nommer vos fichiers")
    ).not.toBeInTheDocument();
  });

  it("displays all 4 channels", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    // QA TEST-001: use original labels, not uppercase (CSS text-transform not reflected in jsdom)
    expect(screen.getByText("Shopify")).toBeInTheDocument();
    expect(screen.getByText("ManoMano")).toBeInTheDocument();
    expect(screen.getByText("Décathlon")).toBeInTheDocument();
    expect(screen.getByText("Leroy Merlin")).toBeInTheDocument();
  });

  it("displays Shopify file patterns", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    // Patterns appear in channel section + examples section — use getAllByText
    expect(screen.getAllByText(/Ventes Shopify/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Transactions Shopify/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/versements/).length).toBeGreaterThanOrEqual(1);
  });

  it("displays mode explanation for Shopify", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(
      screen.getByText(/Choisissez l'un des modes suivants/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/un seul mode à la fois/)
    ).toBeInTheDocument();
  });

  it("displays Shopify mode count (2 modes)", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText(/2 modes/)).toBeInTheDocument();
  });

  it("displays Décathlon file count singular (1 fichier)", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    // Both Décathlon and Leroy Merlin have "1 fichier" (singular)
    const matches = screen.getAllByText(/1 fichier\b/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  // --- Static content tests (AC: 13) ---

  it("displays examples section", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(
      screen.getByText("Exemples de noms valides")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ventes Shopify Janv 2026\.csv/)
    ).toBeInTheDocument();
  });

  it("displays tip section", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(screen.getByText("Astuce")).toBeInTheDocument();
    expect(
      screen.getByText(/pas obligé de traiter tous les canaux/)
    ).toBeInTheDocument();
  });

  it("displays placeholder explanation", () => {
    render(<HelpDrawer isOpen={true} onOpenChange={vi.fn()} />);

    expect(
      screen.getByText(/texte optionnel/)
    ).toBeInTheDocument();
  });

  // --- Interaction test ---

  it("calls onOpenChange(false) when close button is clicked", () => {
    const onOpenChange = vi.fn();
    render(<HelpDrawer isOpen={true} onOpenChange={onOpenChange} />);

    const closeButton = screen.getByRole("button", { name: /close/i });
    fireEvent.click(closeButton);

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  // --- Accessibility test (AC: 14) ---

  it("has no axe accessibility violations", async () => {
    const { container } = render(
      <HelpDrawer isOpen={true} onOpenChange={vi.fn()} />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
