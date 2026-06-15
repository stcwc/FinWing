import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, ApiError } from "./api/client";
import { UserProfile } from "./api/types";

interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  isAdmin: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      // /users/me returns the profile, creating it on first sign-in.
      const profile = await api.post<UserProfile>("/users/me");
      setUser(profile);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null);
      else if (e instanceof ApiError && e.code === "USER_CAP") setUser(null);
      else setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await api.post("/auth/logout");
    setUser(null);
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, isAdmin: user?.role === "admin", refresh, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
