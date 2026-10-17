/** Avoid repeating the reader title without changing the saved Markdown. */
export function reportBodyForReader(markdown: string): string {
  const lines = markdown.replace(/\r/g, '').split('\n');
  const firstContent = () => lines.findIndex(line => line.trim().length > 0);
  let index = firstContent();
  const title = index < 0 ? null : lines[index].match(/^\s*#\s+(.+?)\s*#*\s*$/);
  if (title && /^annual\s+(?:self[-\s]+)?review\b/i.test(title[1])) {
    lines.splice(index, 1);
    index = firstContent();
  }
  // The visible document header also names the required opening section.
  if (index >= 0 && /^\s*##\s+Annual Review Summary\s*#*\s*$/i.test(lines[index])) lines.splice(index, 1);
  return lines.join('\n').trimStart();
}
