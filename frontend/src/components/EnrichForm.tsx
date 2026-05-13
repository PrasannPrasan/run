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
      className="lookup-form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!url.trim()) return;
        await onSubmit(url.trim());
      }}
    >
      <label>
        <span>LinkedIn profile URL</span>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.linkedin.com/in/profile-name/"
        />
      </label>
      <button className="primary-button" disabled={disabled} type="submit">
        {disabled ? "Running" : "Enrich"}
      </button>
    </form>
  );
}
