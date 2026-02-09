import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import UnmatchedFilesPanel from "@/components/UnmatchedFilesPanel";
import { CHANNEL_CONFIGS } from "@/lib/channels";
import type { UploadedFile, ChannelConfig, FileSlotConfig } from "@/lib/types";

// --- Helpers ---

function createMockFile(name: string, size = 1024): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type: "text/csv" });
}

function createUploadedFile(
  name: string,
  channel: string | null,
  size = 1024,
): UploadedFile {
  return { file: createMockFile(name, size), channel };
}

// --- Test data ---

const channelConfig: ChannelConfig[] = CHANNEL_CONFIGS;

// Missing slot: Shopify payouts (index 2 in CHANNEL_CONFIGS[0].files)
const missingSlots: { channel: string; slot: FileSlotConfig }[] = [
  { channel: "shopify", slot: CHANNEL_CONFIGS[0].files[2] },
];

const fileWithSuggestion = createUploadedFile(
  "export_shopify_payouts.csv",
  null,
);
const fileWithoutSuggestion = createUploadedFile("données.csv", null);

const defaultProps = {
  channelConfig,
  missingSlots,
  onRemoveFile: vi.fn(),
  onOpenHelp: vi.fn(),
};

describe("UnmatchedFilesPanel", () => {
  // --- Rendering tests (Task 3.4) ---

  it("returns null when unmatchedFiles is empty", () => {
    const { container } = render(
      <UnmatchedFilesPanel {...defaultProps} unmatchedFiles={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("displays singular header for 1 file", () => {
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    expect(screen.getByText("1 fichier non reconnu")).toBeInTheDocument();
  });

  it("displays plural header for 3 files", () => {
    const files = [
      fileWithSuggestion,
      fileWithoutSuggestion,
      createUploadedFile("autre.csv", null),
    ];
    render(
      <UnmatchedFilesPanel {...defaultProps} unmatchedFiles={files} />,
    );
    expect(screen.getByText("3 fichiers non reconnus")).toBeInTheDocument();
  });

  it("displays the filename", () => {
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    expect(
      screen.getByText("export_shopify_payouts.csv"),
    ).toBeInTheDocument();
  });

  it("renders FileQuestion icons with aria-hidden", () => {
    const { container } = render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    const hiddenSvgs = container.querySelectorAll('svg[aria-hidden="true"]');
    expect(hiddenSvgs.length).toBeGreaterThanOrEqual(1);
  });

  // --- Suggestion tests (Task 3.5) ---

  it("displays suggestion when available", () => {
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    expect(screen.getByText(/Suggestion/)).toBeInTheDocument();
    expect(screen.getByText(/Détails versements/)).toBeInTheDocument();
  });

  it("displays complete suggestion message with channel label", () => {
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    expect(screen.getByText(/renommez-le en/)).toBeInTheDocument();
    expect(
      screen.getByText(/pour qu'il soit reconnu comme fichier Shopify/),
    ).toBeInTheDocument();
  });

  it("displays generic message when no suggestion", () => {
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithoutSuggestion]}
      />,
    );
    expect(
      screen.getByText("Ce fichier ne correspond à aucun format connu."),
    ).toBeInTheDocument();
  });

  // --- Interaction tests (Task 3.6) ---

  it("calls onRemoveFile with index 0 on first remove button click", () => {
    const onRemoveFile = vi.fn();
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        onRemoveFile={onRemoveFile}
        unmatchedFiles={[fileWithSuggestion, fileWithoutSuggestion]}
      />,
    );
    const buttons = screen.getAllByText("Retirer");
    fireEvent.click(buttons[0]);
    expect(onRemoveFile).toHaveBeenCalledWith(0);
  });

  it("calls onRemoveFile with index 1 on second remove button click", () => {
    const onRemoveFile = vi.fn();
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        onRemoveFile={onRemoveFile}
        unmatchedFiles={[fileWithSuggestion, fileWithoutSuggestion]}
      />,
    );
    const buttons = screen.getAllByText("Retirer");
    fireEvent.click(buttons[1]);
    expect(onRemoveFile).toHaveBeenCalledWith(1);
  });

  it("calls onOpenHelp when help link is clicked", () => {
    const onOpenHelp = vi.fn();
    render(
      <UnmatchedFilesPanel
        {...defaultProps}
        onOpenHelp={onOpenHelp}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    fireEvent.click(
      screen.getByText("Voir les formats de noms attendus"),
    );
    expect(onOpenHelp).toHaveBeenCalled();
  });

  // --- SPEC-001: Amber classes on container ---

  it("applies amber border class to the container", () => {
    const { container } = render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion]}
      />,
    );
    expect(container.querySelector(".border-amber-300")).toBeInTheDocument();
  });

  // --- Accessibility test (Task 3.7) ---

  it("has no axe accessibility violations", async () => {
    const { container } = render(
      <UnmatchedFilesPanel
        {...defaultProps}
        unmatchedFiles={[fileWithSuggestion, fileWithoutSuggestion]}
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
