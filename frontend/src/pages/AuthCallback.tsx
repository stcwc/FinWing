import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { cognitoConfig } from "../config";
import { Spinner } from "../components/ui";

export default function AuthCallback() {
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
      setError("No authorization code returned.");
      return;
    }
    api
      .post("/auth/callback", { code, redirectUri: cognitoConfig.redirectUri })
      // Hard reload so the app remounts with the session cookie present and a
      // single, authoritative profile fetch — avoids racing the provider's
      // initial (cookie-less) refresh, which could clobber the signed-in state.
      .then(() => window.location.replace("/"))
      .catch(() => setError("Sign-in failed. Please try again."));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="card max-w-sm p-8 text-center">
          <p className="text-sm text-ink-800">{error}</p>
          <a href="/signin" className="btn-primary mt-4">
            Back to sign in
          </a>
        </div>
      </div>
    );
  }
  return <Spinner label="Signing you in…" />;
}
