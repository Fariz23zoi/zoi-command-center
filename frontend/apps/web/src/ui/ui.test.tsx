import { render, screen } from "@testing-library/react";
import { Eye, Inbox } from "lucide-react";
import { describe, expect, it } from "vitest";

import { EmptyState, StatCard } from ".";

describe("design system", () => {
  it("StatCard tanpa data menampilkan tanda kosong, bukan angka contoh", () => {
    render(<StatCard label="Total Views" icon={Eye} value={null} delta={{ text: "+5%", up: true }} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText(/\+5%/)).not.toBeInTheDocument();
  });

  it("StatCard dengan data menampilkan nilai dan perubahan", () => {
    render(<StatCard label="Subscribers" icon={Eye} value="1.204" delta={{ text: "+2%", up: true }} />);
    expect(screen.getByText("1.204")).toBeInTheDocument();
    expect(screen.getByText(/\+2%/)).toBeInTheDocument();
  });

  it("EmptyState menampilkan judul dan aksi", () => {
    render(<EmptyState icon={Inbox} title="Belum terhubung" action={<button type="button">Hubungkan</button>} />);
    expect(screen.getByText("Belum terhubung")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hubungkan" })).toBeInTheDocument();
  });
});
