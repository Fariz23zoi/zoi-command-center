/* global console */
// Salin aset avatar dari paket npm ke public/avatar-assets agar di-host sendiri (tanpa CDN).
// Dijalankan otomatis sebelum `dev` dan `build`. Versi paket dikunci di packages/avatar/package.json.
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const target = join(here, "..", "public", "avatar-assets");
// Resolusi dari paket @zoi/avatar (pemilik dependensi). pathToFileURL agar aman di Windows.
const parent = pathToFileURL(join(here, "..", "..", "..", "packages", "avatar", "package.json")).href;
const resolve = (spec) => fileURLToPath(import.meta.resolve(spec, parent));

const model = resolve("@interviewflowai/talking-avatar/viseme-model.bin");
const files = {
  "viseme-model.bin": model,
  "female.glb": resolve("@interviewflowai/talking-avatar/avatars/female.glb"),
  "male.glb": resolve("@interviewflowai/talking-avatar/avatars/male.glb"),
  "LICENSE-rocketbox.txt": resolve("@interviewflowai/talking-avatar/avatars/LICENSE"),
  "LICENSE-talking-avatar.txt": join(dirname(model), "..", "LICENSE"),
};

mkdirSync(target, { recursive: true });
for (const [name, source] of Object.entries(files)) copyFileSync(source, join(target, name));
const version = JSON.parse(readFileSync(join(dirname(model), "..", "package.json"), "utf8")).version;
console.log(`[avatar] ${Object.keys(files).length} aset talking-avatar ${version} disalin ke public/avatar-assets`);
