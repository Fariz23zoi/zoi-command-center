import type { MenuItem } from "../menu";

/** Halaman fitur yang belum dibangun. Tidak menampilkan angka, grafik, atau data contoh apa pun. */
export function NotYetAvailable({ item }: { item: MenuItem }) {
  return (
    <section className="page not-ready" data-testid="not-yet-available">
      <h1>{item.label}</h1>
      <p className="tag-phase">Belum tersedia — dijadwalkan Phase {item.phase}</p>
      <p>{item.description}</p>
      <p className="muted">
        Halaman ini sengaja kosong. ZOI tidak menampilkan data contoh agar tidak ada angka yang terlihat seperti
        data asli.
      </p>
    </section>
  );
}
