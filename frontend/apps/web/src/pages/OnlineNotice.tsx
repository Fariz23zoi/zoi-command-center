import { useApp } from "../stores/appStore";

/** Pemberitahuan jujur di mode online: fitur ini berjalan di laptop, bukan di server. */
export function OnlineNotice({ feature }: { feature: string }) {
  const online = useApp((s) => s.config?.online);
  if (!online) return null;
  return (
    <p className="notice warn" data-testid="online-notice">
      {feature} hanya berjalan di laptop (mode local), tidak di server online ini. Pengaturan di bawah tetap
      ditampilkan apa adanya.
    </p>
  );
}
