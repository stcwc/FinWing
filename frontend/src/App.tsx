import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Spinner } from "./components/ui";
import { Shell } from "./components/Shell";
import SignIn from "./pages/SignIn";
import AuthCallback from "./pages/AuthCallback";
import Onboarding from "./pages/Onboarding";
import Lenses from "./pages/Lenses";
import Summaries from "./pages/Summaries";
import Settings from "./pages/Settings";
import Feedback from "./pages/Feedback";
import Admin from "./pages/Admin";

export default function App() {
  const { user, loading } = useAuth();

  return (
    <Routes>
      <Route path="/auth/callback" element={<AuthCallback />} />
      {loading ? (
        <Route path="*" element={<Spinner label="Loading FinWing…" />} />
      ) : !user ? (
        <>
          <Route path="/signin" element={<SignIn />} />
          <Route path="*" element={<Navigate to="/signin" replace />} />
        </>
      ) : user.lensCount === 0 ? (
        <>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="*" element={<Navigate to="/onboarding" replace />} />
        </>
      ) : (
        <Route element={<Shell />}>
          <Route path="/" element={<Navigate to="/lenses" replace />} />
          <Route path="/lenses" element={<Lenses />} />
          <Route path="/summaries" element={<Summaries />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/lenses" replace />} />
        </Route>
      )}
    </Routes>
  );
}
