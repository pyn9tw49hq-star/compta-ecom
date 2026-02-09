import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import ValidationBar from "@/components/ValidationBar";
import type { ChannelStatus } from "@/lib/types";

// --- Test data (Task 4.2) ---

const shopifyComplete: ChannelStatus = {
  channelKey: "shopify",
  label: "Shopify",
  requiredCount: 3,
  uploadedRequiredCount: 3,
  isComplete: true,
};

const shopifyIncomplete: ChannelStatus = {
  channelKey: "shopify",
  label: "Shopify",
  requiredCount: 3,
  uploadedRequiredCount: 2,
  isComplete: false,
};

const decathlonComplete: ChannelStatus = {
  channelKey: "decathlon",
  label: "Décathlon",
  requiredCount: 1,
  uploadedRequiredCount: 1,
  isComplete: true,
};

const manomanoEmpty: ChannelStatus = {
  channelKey: "manomano",
  label: "ManoMano",
  requiredCount: 2,
  uploadedRequiredCount: 0,
  isComplete: false,
};

const defaultProps = {
  onGenerate: vi.fn(),
};

describe("ValidationBar", () => {
  // --- State: no-files (Task 4.3) ---

  describe("state: no-files", () => {
    it("disables the button when hasFiles is false", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={false}
          channelStatuses={[]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Générer les écritures" }),
      ).toBeDisabled();
    });

    it("shows no summary text", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={false}
          channelStatuses={[]}
          isLoading={false}
        />,
      );
      expect(screen.queryByText(/sera traité/)).not.toBeInTheDocument();
      expect(screen.queryByText(/sera ignoré/)).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Aucun canal n'est complet/),
      ).not.toBeInTheDocument();
    });
  });

  // --- State: all-complete (Task 4.4) ---

  describe("state: all-complete", () => {
    it("enables the button", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyComplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Générer les écritures" }),
      ).toBeEnabled();
    });

    it("displays all channels as treated", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyComplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      expect(screen.getByText(/Shopify sera traité/)).toBeInTheDocument();
      expect(screen.getByText(/Décathlon sera traité/)).toBeInTheDocument();
    });
  });

  // --- State: partial (Task 4.5) ---

  describe("state: partial", () => {
    it("enables the button when at least one channel is complete", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Générer les écritures" }),
      ).toBeEnabled();
    });

    it("displays complete channel as treated", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      expect(screen.getByText(/Décathlon sera traité/)).toBeInTheDocument();
    });

    it("displays incomplete channel as ignored with missing count", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      expect(screen.getByText(/Shopify sera ignoré/)).toBeInTheDocument();
      expect(screen.getByText(/1 fichier manquant/)).toBeInTheDocument();
    });
  });

  // --- State: none-complete (Task 4.6) ---

  describe("state: none-complete", () => {
    it("disables the button when no channel is complete", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Générer les écritures" }),
      ).toBeDisabled();
    });

    it("displays explanatory message", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByText(/Aucun canal n'est complet/),
      ).toBeInTheDocument();
    });

    // TEST-001: none-complete via activeChannels.length === 0
    it("reaches none-complete when hasFiles=true but no active channels (TEST-001)", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[manomanoEmpty]}
          isLoading={false}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Générer les écritures" }),
      ).toBeDisabled();
      expect(
        screen.getByText(/Aucun canal n'est complet/),
      ).toBeInTheDocument();
    });
  });

  // --- State: loading (Task 4.7) ---

  describe("state: loading", () => {
    it("disables the button when loading", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyComplete]}
          isLoading={true}
        />,
      );
      expect(
        screen.getByRole("button", { name: "Traitement en cours..." }),
      ).toBeDisabled();
    });

    it("shows spinner and loading text", () => {
      const { container } = render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyComplete]}
          isLoading={true}
        />,
      );
      expect(
        screen.getByText("Traitement en cours..."),
      ).toBeInTheDocument();
      expect(container.querySelector(".animate-spin")).toBeInTheDocument();
    });
  });

  // --- Interaction (Task 4.8) ---

  it("calls onGenerate when button is clicked", () => {
    const onGenerate = vi.fn();
    render(
      <ValidationBar
        onGenerate={onGenerate}
        hasFiles={true}
        channelStatuses={[shopifyComplete]}
        isLoading={false}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Générer les écritures" }),
    );
    expect(onGenerate).toHaveBeenCalled();
  });

  // --- French pluralisation (Task 4.9) ---

  describe("French pluralisation", () => {
    it("shows singular for 1 missing file", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[
            {
              channelKey: "manomano",
              label: "ManoMano",
              requiredCount: 2,
              uploadedRequiredCount: 1,
              isComplete: false,
            },
            decathlonComplete,
          ]}
          isLoading={false}
        />,
      );
      expect(screen.getByText(/1 fichier manquant\b/)).toBeInTheDocument();
    });

    it("shows plural for 2+ missing files", () => {
      render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[
            {
              channelKey: "shopify",
              label: "Shopify",
              requiredCount: 3,
              uploadedRequiredCount: 1,
              isComplete: false,
            },
            decathlonComplete,
          ]}
          isLoading={false}
        />,
      );
      expect(screen.getByText(/2 fichiers manquants/)).toBeInTheDocument();
    });
  });

  // --- Accessibility (Task 4.10) ---

  describe("accessibility", () => {
    it("has no axe violations for no-files state", async () => {
      const { container } = render(
        <ValidationBar
          {...defaultProps}
          hasFiles={false}
          channelStatuses={[]}
          isLoading={false}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it("has no axe violations for all-complete state", async () => {
      const { container } = render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyComplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it("has no axe violations for partial state", async () => {
      const { container } = render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete, decathlonComplete]}
          isLoading={false}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it("has no axe violations for none-complete state", async () => {
      const { container } = render(
        <ValidationBar
          {...defaultProps}
          hasFiles={true}
          channelStatuses={[shopifyIncomplete]}
          isLoading={false}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
