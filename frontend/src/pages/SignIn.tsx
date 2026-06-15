import { hostedUiSignInUrl } from "../config";

export default function SignIn() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-ink-50 to-ink-100 px-4">
      <div className="card w-full max-w-sm p-8 text-center">
        <div className="mb-2 text-3xl text-wing-600">◆</div>
        <h1 className="text-2xl font-semibold tracking-tight">FinWing</h1>
        <p className="mt-2 text-sm text-ink-400">
          Your financial news, gathered, filtered, and summarized — so you keep track
          without the doom-scroll.
        </p>
        <a href={hostedUiSignInUrl()} className="btn-primary mt-6 w-full">
          Sign in
        </a>
        <p className="mt-4 text-xs text-ink-400">
          Sign in with Google or email. By continuing you agree this tool provides
          information only, not financial advice.
        </p>
      </div>
    </div>
  );
}
