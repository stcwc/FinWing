import { hostedUiSignInUrl } from "../config";

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35.5 24 35.5c-6.3 0-11.5-5.2-11.5-11.5S17.7 12.5 24 12.5c2.9 0 5.5 1.1 7.5 2.9l5.7-5.7C33.6 6.1 29.1 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.3-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 12.5 24 12.5c2.9 0 5.5 1.1 7.5 2.9l5.7-5.7C33.6 6.1 29.1 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2c-2 1.4-4.5 2.2-7.2 2.2-5.3 0-9.7-3.1-11.3-7.5l-6.5 5C9.6 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.6l6.2 5.2C41.4 35.4 44 30.1 44 24c0-1.3-.1-2.3-.4-3.5z" />
    </svg>
  );
}

export default function SignIn() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-ink-50 to-ink-100 px-4">
      <div className="card w-full max-w-sm p-8 text-center">
        <img src="/finwing-logo.png" alt="FinWing" className="mx-auto mb-3 h-11 w-auto" />
        <p className="mt-2 text-sm text-ink-400">
          Your financial news, gathered, filtered, and summarized — so you keep track
          without the doom-scroll.
        </p>
        <a
          href={hostedUiSignInUrl("Google")}
          className="btn-outline mt-6 w-full"
        >
          <GoogleIcon /> Continue with Google
        </a>
        <div className="my-3 flex items-center gap-3 text-xs text-ink-400">
          <span className="h-px flex-1 bg-ink-200" />
          or
          <span className="h-px flex-1 bg-ink-200" />
        </div>
        <a href={hostedUiSignInUrl()} className="btn-primary w-full">
          Sign in with email
        </a>
        <p className="mt-4 text-xs text-ink-400">
          By continuing you agree this tool provides information only, not financial
          advice.
        </p>
      </div>
    </div>
  );
}
