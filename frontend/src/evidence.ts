const whitespace = (text: string) => text.replace(/\s+/g, ' ').trim();
const stopWords = new Set('a an and are as at be been being but by can did do does for from had has have he her his i in into is it its my of on or our she that the their them they this to was we were which will with you your'.split(' '));
const tokens = (text: string) => new Set((text.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []).filter(token => !stopWords.has(token)).slice(0, 64));
const metadata = /^(?:date|author|project|status|prepared by|document id|file name|page)\s*:/i;
const limit = (text: string, max = 300) => {
  if (text.length <= max) return text;
  const cutoff = text.lastIndexOf(' ', max - 1);
  return `${text.slice(0, cutoff > max * .6 ? cutoff : max - 1).trimEnd()}…`;
};

/** A display-only, contiguous excerpt. The full literal quote remains untouched. */
export function evidencePreview(quote: string, claim = ''): { text: string; shortened: boolean } {
  const full = whitespace(quote);
  const claimText = whitespace(claim);
  const lines = quote.slice(0, 60_000).replace(/\r/g, '').split('\n');
  const contentLines = lines.filter((line, index) => {
    const text = line.trim();
    if (metadata.test(text)) return false;
    const next = lines.slice(index + 1).find(value => value.trim())?.trim();
    return !(text && text.length < 120 && !/[.!?]$/.test(text) && next && metadata.test(next));
  });
  const clean = whitespace(contentLines.join('\n'));
  if (full.length <= 300 && clean && full.includes(clean)) return { text: clean, shortened: clean !== full };
  const parts = contentLines.join('\n').split(/\n\s*\n/);
  const sentences = parts.flatMap(part => whitespace(part).match(/[^.!?]+(?:[.!?]+(?=\s|$)|$)/g) || []).map(whitespace).filter(sentence => sentence.length >= 30 && !metadata.test(sentence) && full.includes(sentence)).slice(0, 240);
  const plainLines = contentLines.map(whitespace).filter(line => line.length >= 30 && !metadata.test(line));
  const candidates = sentences.length ? sentences : plainLines.length ? plainLines.slice(0, 240) : [full];
  let selected = -1;
  if (claimText.length >= 24 && claimText.length <= 300 && !/\b(?:date|author|project|status)\s*:/i.test(claimText)) {
    selected = candidates.findIndex(sentence => sentence.includes(claimText));
    if (selected < 0 && full.includes(claimText)) return { text: limit(claimText), shortened: true };
  }
  if (selected < 0) {
    const wanted = tokens(claimText);
    let best = -Infinity;
    candidates.forEach((sentence, index) => {
      const present = tokens(sentence);
      let match = 0;
      wanted.forEach(token => { if (present.has(token)) match += /^\d/.test(token) ? 3 : 1; });
      const score = match / Math.max(1, Math.sqrt(present.size));
      if (score > best) { best = score; selected = index; }
    });
  }
  let excerpt = candidates[Math.max(0, selected)];
  // Keep an immediately adjacent limitation when it fits; never join distant claims.
  const next = candidates[selected + 1];
  if (next && /\b(?:pilot|team|not|below|target|causal|limited|only|proposed)\b/i.test(next) && excerpt.length + next.length < 300 && full.includes(`${excerpt} ${next}`)) excerpt += ` ${next}`;
  return { text: limit(excerpt), shortened: true };
}

export const normalizedEvidenceText = whitespace;
