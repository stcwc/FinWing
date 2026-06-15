import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { cognitoConfig } from "../config";
import { useAuth } from "../auth";
import { Spinner } from "../components/ui";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
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
      .then(() => refresh())
      .then(() => navigate("/", { replace: true }))
      .catch(() => setError("Sign-in failed. Please try again."));
  }, [navigate, refresh]);

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
