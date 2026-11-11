import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, onSessionEnd, tokens } from "@/api/client";
import type { AuthResponse, User } from "@/api/types";

type Ctx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (u: User) => void;
};
const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => !!tokens.access || !!tokens.refresh);

  useEffect(() => {
    if (!loading) return;
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  useEffect(() => onSessionEnd(logout), [logout]);

  const finish = (r: AuthResponse) => {
    tokens.set(r.tokens.access_token, r.tokens.refresh_token);
    qc.clear();
    setUser(r.user);
  };
  const value = useMemo<Ctx>(
    () => ({
      user,
      loading,
      setUser,
      logout,
      login: async (email, password) => finish(await api<AuthResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false })),
      register: async (name, email, password) =>
        finish(await api<AuthResponse>("/auth/register", { method: "POST", body: { name, email, password }, auth: false })),
    }),
    [user, loading, logout], // eslint-disable-line react-hooks/exhaustive-deps
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
