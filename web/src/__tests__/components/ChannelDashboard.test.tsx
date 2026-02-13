import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import ChannelDashboard from "@/components/ChannelDashboard";
import { CHANNEL_CONFIGS } from "@/lib/channels";
import type { UploadedFile } from "@/lib/types";

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

describe("ChannelDashboard", () => {
  it("sorts active channels before inactive channels", () => {
    const files: UploadedFile[] = [
      createUploadedFile("CA Manomano 2026.csv", "manomano"),
    ];

    render(
      <ChannelDashboard
        files={files}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    // ManoMano should be before the "non utilisés" separator
    const allText = document.body.textContent ?? "";
    const manomanoPos = allText.indexOf("ManoMano");
    const separatorPos = allText.indexOf("non utilisés");

    expect(manomanoPos).toBeLessThan(separatorPos);
  });

  it("displays 'non utilisés' separator when there are active and inactive channels", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
    ];

    render(
      <ChannelDashboard
        files={files}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.getByText("non utilisés")).toBeInTheDocument();
  });

  it("does not display separator when all channels are empty (initial state)", () => {
    render(
      <ChannelDashboard
        files={[]}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.queryByText("non utilisés")).not.toBeInTheDocument();
  });

  it("toggles all channels with the Tout déplier/replier button", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
    ];

    render(
      <ChannelDashboard
        files={files}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    // Initial state: "Tout déplier" because not all are expanded
    const toggleBtn = screen.getByRole("button", { name: /tout déplier/i });
    expect(toggleBtn).toBeInTheDocument();

    // Click to expand all
    fireEvent.click(toggleBtn);

    // Now should say "Tout replier"
    expect(screen.getByRole("button", { name: /tout replier/i })).toBeInTheDocument();

    // Click to collapse all
    fireEvent.click(screen.getByRole("button", { name: /tout replier/i }));

    // Back to "Tout déplier"
    expect(screen.getByRole("button", { name: /tout déplier/i })).toBeInTheDocument();
  });

  it("classifies 'Ventes Shopify.csv' into the sales slot of Shopify", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
    ];

    render(
      <ChannelDashboard
        files={files}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    // The file should appear inside the Shopify channel card
    expect(screen.getByText("Ventes Shopify.csv")).toBeInTheDocument();
    // Shopify uses fileGroups — header shows group labels
    expect(screen.getByText("Mode complet / Mode avoirs")).toBeInTheDocument();
  });

  it("has no axe violations (empty state)", async () => {
    const { container } = render(
      <ChannelDashboard
        files={[]}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations (with files)", async () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
      createUploadedFile("CA Manomano 2026.csv", "manomano"),
    ];

    const { container } = render(
      <ChannelDashboard
        files={files}
        channelConfig={CHANNEL_CONFIGS}
        onRemoveFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
