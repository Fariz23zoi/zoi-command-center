import { api, type ProductionPackage } from "@zoi/api-client";
import { FolderKanban } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorText } from "../lib/youtube";
import { Badge, Card, EmptyState } from "../ui";

/** Projects: paket produksi nyata yang tersimpan di ZOI (bukan daftar contoh). */
export function ProjectsPage() {
  const [items, setItems] = useState<ProductionPackage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.production.packages().then((r) => setItems(r.items)).catch((e) => setError(errorText(e, "Proyek tidak dapat dimuat.")));
  }, []);
  return (
    <section className="page" data-testid="projects-page">
      <h1>Projects</h1>
      <p className="muted">Paket produksi video yang kamu buat dari naskah. Kelola lengkapnya di <Link to="/production">Content Production</Link>.</p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {items && items.length === 0 && (
        <Card><EmptyState icon={FolderKanban} title="Belum ada proyek"
          action={<Link className="dash-cta" to="/script">Tulis naskah</Link>}>Proyek muncul setelah naskah diubah menjadi paket produksi.</EmptyState></Card>
      )}
      <div className="proj-grid">
        {items?.map((p) => (
          <Card key={p.id} title={p.judul}>
            <p className="muted">{p.beats} adegan · rasio {p.rasio} · {new Date(p.created * 1000).toLocaleDateString("id-ID")}</p>
            <p>{p.mock && <Badge tone="warn">MOCK</Badge>} {p.narration ? <Badge tone="ok">Narasi siap</Badge> : <Badge>Belum ada narasi</Badge>}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
