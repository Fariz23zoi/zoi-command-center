/** Memotong jawaban yang datang bertahap menjadi kalimat, agar ZOI bisa mulai bicara sebelum jawaban selesai. */
const END = /[.!?…]+["')\]]*(\s+|$)|\n+/g;
export const MAX_CHUNK = 280;

export class SentenceSplitter {
  private buffer = "";

  feed(text: string): string[] {
    this.buffer += text;
    const out: string[] = [];
    let match: RegExpExecArray | null;
    let start = 0;
    END.lastIndex = 0;
    while ((match = END.exec(this.buffer)) !== null) {
      if (match.index + match[0].length === this.buffer.length && !/\s$/.test(match[0])) break; // tanda baca di ujung: tunggu
      const end = match.index + match[0].length;
      push(out, this.buffer.slice(start, end));
      start = end;
    }
    this.buffer = this.buffer.slice(start);
    while (this.buffer.length > MAX_CHUNK) {
      // Kalimat sangat panjang tanpa titik: potong di koma/spasi terakhir sebelum batas.
      const cut = Math.max(this.buffer.lastIndexOf(",", MAX_CHUNK), this.buffer.lastIndexOf(" ", MAX_CHUNK));
      const at = cut > MAX_CHUNK / 2 ? cut + 1 : MAX_CHUNK;
      push(out, this.buffer.slice(0, at));
      this.buffer = this.buffer.slice(at);
    }
    return out;
  }

  flush(): string[] {
    const out: string[] = [];
    push(out, this.buffer);
    this.buffer = "";
    return out;
  }
}

function push(out: string[], raw: string) {
  const text = raw.replace(/\s+/g, " ").trim();
  if (/[\p{L}\p{N}]/u.test(text)) out.push(text);
}

/** Label [MOCK] tidak dibacakan; tanda markdown sederhana dibuang. */
export function speakable(text: string): string {
  return text.replace(/\[MOCK\]\s*/g, "").replace(/[*_`#>]+/g, "").trim();
}
