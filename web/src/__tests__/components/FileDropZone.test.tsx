import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import FileDropZone from "@/components/FileDropZone";
import type { UploadedFile } from "@/lib/types";

function createMockFile(name: string, size = 1024): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type: "text/csv" });
}

function createUploadedFile(
  name: string,
  channel: string | null,
): UploadedFile {
  return { file: createMockFile(name), channel };
}

/** Simulate file selection via the hidden input. */
function addFilesViaInput(files: File[]) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  Object.defineProperty(input, "files", {
    value: files,
    configurable: true,
  });
  fireEvent.change(input);
}

const defaultProps = {
  files: [] as UploadedFile[],
  onAddFiles: vi.fn(),
};

describe("FileDropZone", () => {
  it("renders the drop zone with browse text", () => {
    render(<FileDropZone {...defaultProps} />);

    expect(screen.getByText(/glissez-déposez/i)).toBeInTheDocument();
    expect(screen.getByText("Parcourir")).toBeInTheDocument();
  });

  it("adds files via file input and calls onAddFiles", () => {
    const onAddFiles = vi.fn();
    render(<FileDropZone files={[]} onAddFiles={onAddFiles} />);

    const file = createMockFile("Ventes Shopify Janvier.csv", 2048);
    addFilesViaInput([file]);

    expect(onAddFiles).toHaveBeenCalledTimes(1);
    expect(onAddFiles).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ channel: "shopify" }),
      ])
    );
  });

  it("shows counter when files prop is provided", () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify Janvier.csv", "shopify"),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/1 fichier déposé/)).toBeInTheDocument();
  });

  it("shows unrecognized count in counter", () => {
    const filesWithData = [createUploadedFile("random.csv", null)];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/1 non reconnu/)).toBeInTheDocument();
  });

  it("counts multiple files correctly", () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
      createUploadedFile("CA Manomano 2026.csv", "manomano"),
      createUploadedFile("Leroy Merlin mars.csv", "leroy_merlin"),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/3 fichiers déposés/)).toBeInTheDocument();
  });

  it("has no axe accessibility violations (empty state)", async () => {
    const { container } = render(<FileDropZone {...defaultProps} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe accessibility violations (with files)", async () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
      createUploadedFile("random.csv", null),
    ];
    const { container } = render(
      <FileDropZone files={filesWithData} onAddFiles={vi.fn()} />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("opens file picker on Enter key", () => {
    render(<FileDropZone {...defaultProps} />);

    const dropZone = screen.getByRole("button", { name: /zone de dépôt/i });
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(dropZone, { key: "Enter" });

    expect(clickSpy).toHaveBeenCalled();
  });

  it("opens file picker on Space key", () => {
    render(<FileDropZone {...defaultProps} />);

    const dropZone = screen.getByRole("button", { name: /zone de dépôt/i });
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(dropZone, { key: " " });

    expect(clickSpy).toHaveBeenCalled();
  });

  it("displays enriched welcome text", () => {
    render(<FileDropZone {...defaultProps} />);

    expect(screen.getByText(/Fichiers acceptés/)).toBeInTheDocument();
    expect(screen.getByText(/identifiés automatiquement/)).toBeInTheDocument();
  });

  it("does not display counter when no files", () => {
    render(<FileDropZone {...defaultProps} />);

    expect(screen.queryByText(/déposé/)).not.toBeInTheDocument();
  });

  it("does not display file list after upload", () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows plural counter", () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
      createUploadedFile("CA Manomano.csv", "manomano"),
      createUploadedFile("Decathlon test.csv", "decathlon"),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/3 fichiers déposés/)).toBeInTheDocument();
  });

  it("shows singular counter", () => {
    const filesWithData = [
      createUploadedFile("Ventes Shopify.csv", "shopify"),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/1 fichier déposé/)).toBeInTheDocument();
  });

  it("shows unrecognized plural", () => {
    const filesWithData = [
      createUploadedFile("unknown1.csv", null),
      createUploadedFile("unknown2.csv", null),
      createUploadedFile("unknown3.csv", null),
    ];
    render(<FileDropZone files={filesWithData} onAddFiles={vi.fn()} />);

    expect(screen.getByText(/3 non reconnus/)).toBeInTheDocument();
  });
});
