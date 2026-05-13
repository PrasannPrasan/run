import { useState } from "react";

export function EnrichForm({
  onSubmit,
  disabled,
}: {
  onSubmit: (linkedinUrl: string) => Promise<void> | void;
  disabled?: boolean;
}) {
  const [url, setUrl] = useState("");

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!url.trim()) return;
        await onSubmit(url.trim());
      }}
      style={{ display: "flex", gap: 8 }}
    >
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://www.linkedin.com/in/..."
        style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db" }}
      />
      <button
        disabled={disabled}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #111827",
          background: disabled ? "#6b7280" : "#111827",
          color: "white",
          fontWeight: 600,
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        {disabled ? "Running..." : "Enrich"}
      </button>
    </form>
  );
}

