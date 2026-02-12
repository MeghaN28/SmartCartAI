/**
 * Remove markdown formatting so chat and suggestion tab show plain text (no **, #, etc.)
 */
export function stripMarkdown(text) {
  if (text == null || typeof text !== 'string') return text;
  let s = text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^#+\s*/gm, '')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/_([^_]+)_/g, '$1');
  return s.trim();
}
