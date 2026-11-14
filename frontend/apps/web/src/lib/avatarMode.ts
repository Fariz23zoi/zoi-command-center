import type { AvatarRenderMode } from "@zoi/avatar";

/**
 * Mode avatar efektif.
 *  - ZOI_AVATAR_MODE=2d (server) memaksa 2D — untuk mesin lemah (profil lite).
 *  - Selain itu preferensi pengguna dipakai; preferensi "auto" mengikuti nilai server.
 */
export function effectiveAvatarMode(server: AvatarRenderMode | undefined, preference: AvatarRenderMode | undefined): AvatarRenderMode {
  if (server === "2d") return "2d";
  if (!preference || preference === "auto") return server ?? "auto";
  return preference;
}
