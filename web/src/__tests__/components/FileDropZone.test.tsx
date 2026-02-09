import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { axe } from "vitest-axe";
import FileDropZone from "@/components/FileDropZone";

function createMockFile(name: string, size = 1024): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type: "text/csv" });
}

/** Simulate file selection via the hidden input. */
function addFilesViaInput(files: File[]) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  // Shadow the native read-only getter so the handler reads our files
  Object.defineProperty(input, "files", {
    value: files,
    configurable: true,
  });
  fireEvent.change(input);
}

describe("FileDropZone", () => {
  it("renders the drop zone with browse text", () => {
    render(<FileDropZone onFilesChange={vi.fn()} />);

    expect(screen.getByText(/glissez-déposez/i)).toBeInTheDocument();
    expect(screen.getByText("Parcourir")).toBeInTheDocument();
  });

  it("adds files via file input and displays them with channel badge", () => {
    const onFilesChange = vi.fn();
    render(<FileDropZone onFilesChange={onFilesChange} />);

    const file = createMockFile("Ventes Shopify Janvier.csv", 2048);
    act(() => addFilesViaInput([file]));

    expect(screen.getByText("Ventes Shopify Janvier.csv")).toBeInTheDocument();
    expect(screen.getByText("Shopify")).toBeInTheDocument();
    expect(onFilesChange).toHaveBeenCalledTimes(1);
    expect(onFilesChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ channel: "shopify" }),
      ])
    );
  });

  it("displays 'Canal inconnu' for unrecognized files", () => {
    render(<FileDropZone onFilesChange={vi.fn()} />);

    act(() => addFilesViaInput([createMockFile("random.csv")]));

    expect(screen.getByText("Canal inconnu")).toBeInTheDocument();
  });

  it("removes a file when clicking the remove button", () => {
    const onFilesChange = vi.fn();
    render(<FileDropZone onFilesChange={onFilesChange} />);

    act(() => addFilesViaInput([createMockFile("Decathlon export.csv")]));

    expect(screen.getByText("Decathlon export.csv")).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByLabelText("Retirer Decathlon export.csv"));
    });

    expect(screen.queryByText("Decathlon export.csv")).not.toBeInTheDocument();
    expect(onFilesChange).toHaveBeenCalledTimes(2);
    expect(onFilesChange).toHaveBeenLastCalledWith([]);
  });

  it("detects multiple channel types", () => {
    render(<FileDropZone onFilesChange={vi.fn()} />);

    act(() =>
      addFilesViaInput([
        createMockFile("Ventes Shopify.csv"),
        createMockFile("CA Manomano 2026.csv"),
        createMockFile("Leroy Merlin mars.csv"),
      ])
    );

    expect(screen.getAllByText("Shopify")).toHaveLength(1);
    expect(screen.getAllByText("ManoMano")).toHaveLength(1);
    expect(screen.getAllByText("Leroy Merlin")).toHaveLength(1);
  });

  it("has no axe accessibility violations (empty state)", async () => {
    const { container } = render(<FileDropZone onFilesChange={vi.fn()} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe accessibility violations (with files)", async () => {
    const { container } = render(<FileDropZone onFilesChange={vi.fn()} />);

    act(() =>
      addFilesViaInput([
        createMockFile("Ventes Shopify.csv"),
        createMockFile("random.csv"),
      ])
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("opens file picker on Enter key", () => {
    render(<FileDropZone onFilesChange={vi.fn()} />);

    const dropZone = screen.getByRole("button", { name: /zone de dépôt/i });
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(dropZone, { key: "Enter" });

    expect(clickSpy).toHaveBeenCalled();
  });

  it("opens file picker on Space key", () => {
    render(<FileDropZone onFilesChange={vi.fn()} />);

    const dropZone = screen.getByRole("button", { name: /zone de dépôt/i });
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(dropZone, { key: " " });

    expect(clickSpy).toHaveBeenCalled();
  });
});
