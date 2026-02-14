import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import FileSlot from "@/components/FileSlot";
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

describe("FileSlot", () => {
  it("renders the filled variant with filename, size, and remove button", () => {
    const uploaded = createUploadedFile("Ventes Shopify Janvier.csv", "shopify", 2048);
    const onRemove = vi.fn();

    render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={uploaded}
        showMissingWarning={false}
        onRemoveFile={onRemove}
      />,
    );

    expect(screen.getByText("Ventes Shopify Janvier.csv")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Retirer Ventes Shopify Janvier.csv"),
    ).toBeInTheDocument();
  });

  it("renders the empty-required variant with MANQUANT badge when showMissingWarning is true", () => {
    render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={null}
        showMissingWarning
      />,
    );

    expect(
      screen.getByText('"Ventes Shopify [...].csv"'),
    ).toBeInTheDocument();
    expect(screen.getByText("MANQUANT")).toBeInTheDocument();
  });

  it("renders the empty-required variant with obligatoire badge when showMissingWarning is false", () => {
    render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={null}
        showMissingWarning={false}
      />,
    );

    expect(
      screen.getByText('"Ventes Shopify [...].csv"'),
    ).toBeInTheDocument();
    expect(screen.getByText("obligatoire")).toBeInTheDocument();
  });

  it("renders the empty-optional variant with optionnel badge", () => {
    render(
      <FileSlot
        slotKey="payout_details"
        pattern="Detail transactions par versements*.csv"
        patternHuman={'"Detail transactions par versements [...].csv"'}
        isRequired={false}
        matchedFile={null}
        showMissingWarning={false}
      />,
    );

    expect(
      screen.getByText('"Detail transactions par versements [...].csv"'),
    ).toBeInTheDocument();
    expect(screen.getByText("optionnel")).toBeInTheDocument();
  });

  it("calls onRemoveFile when the remove button is clicked", () => {
    const uploaded = createUploadedFile("Ventes Shopify.csv", "shopify");
    const onRemove = vi.fn();

    render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={uploaded}
        showMissingWarning={false}
        onRemoveFile={onRemove}
      />,
    );

    fireEvent.click(screen.getByLabelText("Retirer Ventes Shopify.csv"));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("has no axe violations (filled variant)", async () => {
    const uploaded = createUploadedFile("Ventes Shopify.csv", "shopify");
    const { container } = render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={uploaded}
        showMissingWarning={false}
        onRemoveFile={vi.fn()}
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations (empty-required variant)", async () => {
    const { container } = render(
      <FileSlot
        slotKey="sales"
        pattern="Ventes Shopify*.csv"
        patternHuman={'"Ventes Shopify [...].csv"'}
        isRequired
        matchedFile={null}
        showMissingWarning
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations (empty-optional variant)", async () => {
    const { container } = render(
      <FileSlot
        slotKey="payout_details"
        pattern="Detail transactions par versements*.csv"
        patternHuman={'"Detail transactions par versements [...].csv"'}
        isRequired={false}
        matchedFile={null}
        showMissingWarning={false}
      />,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
