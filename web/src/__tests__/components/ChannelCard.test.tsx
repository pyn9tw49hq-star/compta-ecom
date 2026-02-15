import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { ShoppingBag, Wrench } from "lucide-react";
import ChannelCard from "@/components/ChannelCard";
import type { ChannelMeta } from "@/lib/channels";
import type { FileSlotConfig, UploadedFile } from "@/lib/types";

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

const shopifyMeta: ChannelMeta = {
  label: "Shopify",
  icon: ShoppingBag,
  color: "green",
  badgeClass: "bg-green-100 text-green-800 border-green-300 hover:bg-green-100",
};

const shopifyFiles: FileSlotConfig[] = [
  {
    key: "sales",
    pattern: "Ventes Shopify*.csv",
    patternHuman: '"Ventes Shopify [...].csv"',
    required: true,
    regex: /^Ventes Shopify.*\.csv$/i,
  },
  {
    key: "transactions",
    pattern: "Transactions Shopify*.csv",
    patternHuman: '"Transactions Shopify [...].csv"',
    required: true,
    regex: /^Transactions Shopify.*\.csv$/i,
  },
  {
    key: "payouts",
    pattern: "Détails versements*.csv",
    patternHuman: '"Détails versements [...].csv"',
    required: true,
    regex: /^D[ée]tails versements.*\.csv$/i,
  },
  {
    key: "payout_details",
    pattern: "Detail transactions par versements*.csv",
    patternHuman: '"Detail transactions par versements [...].csv"',
    required: false,
    regex: /^Detail transactions par versements.*\.csv$/i,
    multi: true,
  },
];

const manomanoMeta: ChannelMeta = {
  label: "ManoMano",
  icon: Wrench,
  color: "blue",
  badgeClass: "bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-100",
};

const manomanoFiles: FileSlotConfig[] = [
  {
    key: "ca",
    pattern: "CA Manomano*.csv",
    patternHuman: '"CA Manomano [...].csv"',
    required: true,
    regex: /^CA Manomano.*\.csv$/i,
  },
  {
    key: "payouts",
    pattern: "Detail versement Manomano*.csv",
    patternHuman: '"Detail versement Manomano [...].csv"',
    required: true,
    regex: /^Detail versement Manomano.*\.csv$/i,
  },
  {
    key: "order_details",
    pattern: "Detail commandes manomano*.csv",
    patternHuman: '"Detail commandes manomano [...].csv"',
    required: true,
    regex: /^Detail commandes manomano.*\.csv$/i,
  },
];

describe("ChannelCard", () => {
  it("displays Complet badge when all required files are provided", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify Jan.csv", "shopify"),
      createUploadedFile("Transactions Shopify Jan.csv", "shopify"),
      createUploadedFile("Détails versements Jan.csv", "shopify"),
    ];

    render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.getByText("Complet")).toBeInTheDocument();
    expect(screen.getByText("3 / 3 obligatoires")).toBeInTheDocument();
  });

  it("displays Incomplet badge and inline help when canal is incomplete", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify Jan.csv", "shopify"),
    ];

    render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.getByText("Incomplet")).toBeInTheDocument();
    expect(screen.getByText("1 / 3 obligatoires")).toBeInTheDocument();
    // Inline help message — proper French pluralization
    expect(
      screen.getByText(/Il manque 2 fichiers obligatoires/),
    ).toBeInTheDocument();
    // MANQUANT badges for missing required slots
    expect(screen.getAllByText("MANQUANT")).toHaveLength(2);
  });

  it("displays no status badge when canal is empty (inactive)", () => {
    render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={[]}
        isExpanded={false}
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.getByText("Shopify")).toBeInTheDocument();
    // Inactive format: "X obligatoires + Y optionnel" (wireframe 4.1)
    expect(screen.getByText("3 obligatoires + 1 optionnel")).toBeInTheDocument();
    expect(screen.queryByText("Complet")).not.toBeInTheDocument();
    expect(screen.queryByText("Incomplet")).not.toBeInTheDocument();
  });

  it("displays correct counter for ManoMano (3 required files)", () => {
    const files: UploadedFile[] = [
      createUploadedFile("CA Manomano 2026.csv", "manomano"),
    ];

    render(
      <ChannelCard
        channelKey="manomano"
        meta={manomanoMeta}
        expectedFiles={manomanoFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(screen.getByText("1 / 3 obligatoires")).toBeInTheDocument();
  });

  it("has aria-expanded attribute matching isExpanded prop", () => {
    const { rerender } = render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={[]}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    const trigger = screen.getByRole("button", { name: /shopify/i });
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    rerender(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={[]}
        isExpanded={false}
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("renders dashed separator between required and optional slots (Shopify)", () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify Jan.csv", "shopify"),
      createUploadedFile("Transactions Shopify Jan.csv", "shopify"),
      createUploadedFile("Détails versements Jan.csv", "shopify"),
    ];

    const { container } = render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    const separator = container.querySelector("hr.border-dashed");
    expect(separator).toBeInTheDocument();
  });

  it("has no axe violations (complete state)", async () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify Jan.csv", "shopify"),
      createUploadedFile("Transactions Shopify Jan.csv", "shopify"),
      createUploadedFile("Détails versements Jan.csv", "shopify"),
    ];

    const { container } = render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations (incomplete state)", async () => {
    const files: UploadedFile[] = [
      createUploadedFile("Ventes Shopify Jan.csv", "shopify"),
    ];

    const { container } = render(
      <ChannelCard
        channelKey="shopify"
        meta={shopifyMeta}
        expectedFiles={shopifyFiles}
        uploadedFiles={files}
        isExpanded
        onToggle={vi.fn()}
        onRemoveFile={vi.fn()}
      />,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
