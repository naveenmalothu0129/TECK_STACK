// A clickable citation number. Clicking it opens the source page with the quote highlighted.
export default function CitationTag({ cite, onOpen }) {
  if (!cite) return null;
  const fromRegistry = cite.doc_id === "REGISTRY";
  return (
    <button
      type="button"
      className={`cite ${cite.checked ? "" : "unchecked"} ${fromRegistry ? "registry" : ""}`}
      onClick={() => onOpen(cite.n)}
      title={`${cite.source}\n"${cite.quote}"${cite.checked ? "" : `\nNot verified: ${cite.problem}`}`}
      aria-label={`Citation ${cite.n}: ${cite.source}`}
    >
      {cite.n}
    </button>
  );
}
