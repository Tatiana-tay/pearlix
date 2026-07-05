import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  getCurrentUser,
  login as requestLogin,
  logout as requestLogout,
  type LoginRequestDTO,
} from "../api/auth";
import { isApiError } from "../api/errors";
import type { User } from "../types/models";

export const authAccessTokenStorageKey = "dentalcare.auth.accessToken";
export const authRefreshTokenStorageKey = "dentalcare.auth.refreshToken";
export const authUserStorageKey = "dentalcare.auth.user";

const legacyDemoStorageKeys = ["dentalcare.demoLoginRole", "dentalcare.demoRole"];

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface StoredAuthSession {
  accessToken: string;
  refreshToken: string;
  user: User;
}

type AuthUserLike = Omit<User, "id"> & { id: number | string };

interface SessionState {
  accessToken: string | null;
  authError: string;
  authStatus: AuthStatus;
  currentUser: User | null;
  refreshToken: string | null;
}

interface SessionContextValue extends SessionState {
  clearSession: (message?: string) => void;
  isAuthenticated: boolean;
  login: (credentials: LoginRequestDTO) => Promise<User>;
  logout: () => Promise<void>;
}

interface SessionProviderProps {
  children: ReactNode;
  validateStoredSession?: boolean;
}

const emptySession: SessionState = {
  accessToken: null,
  authError: "",
  authStatus: "unauthenticated",
  currentUser: null,
  refreshToken: null,
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children, validateStoredSession = true }: SessionProviderProps) {
  const [session, setSession] = useState<SessionState>(() => {
    const storedSession = loadStoredSession();
    if (!storedSession) {
      return emptySession;
    }

    return {
      accessToken: storedSession.accessToken,
      authError: "",
      authStatus: validateStoredSession ? "loading" : "authenticated",
      currentUser: storedSession.user,
      refreshToken: storedSession.refreshToken,
    };
  });

  const clearSession = useCallback((message = "") => {
    clearStoredSession();
    setSession({ ...emptySession, authError: message });
  }, []);

  useEffect(() => {
    if (!validateStoredSession) {
      return;
    }

    const storedSession = loadStoredSession();
    if (!storedSession) {
      setSession((current) => current.authStatus === "loading" ? emptySession : current);
      return;
    }

    let cancelled = false;
    getCurrentUser(storedSession.accessToken)
      .then((backendUser) => {
        if (cancelled) {
          return;
        }
        const user = normalizeUser(backendUser);
        persistSession({
          accessToken: storedSession.accessToken,
          refreshToken: storedSession.refreshToken,
          user,
        });
        setSession({
          accessToken: storedSession.accessToken,
          authError: "",
          authStatus: "authenticated",
          currentUser: user,
          refreshToken: storedSession.refreshToken,
        });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        clearStoredSession();
        setSession({
          ...emptySession,
          authError: getReadableAuthError(error, "Your session has expired. Please sign in again."),
        });
      });

    return () => {
      cancelled = true;
    };
  }, [validateStoredSession]);

  const login = useCallback(async (credentials: LoginRequestDTO) => {
    setSession((current) => ({ ...current, authError: "" }));
    try {
      const response = await requestLogin(credentials);
      const accessToken = response.accessToken || response.access;
      const refreshToken = response.refreshToken || response.refresh;

      if (!accessToken || !refreshToken) {
        throw new Error("The backend login response did not include auth tokens.");
      }
      const user = normalizeUser(response.user);
      if (user.status !== "Active") {
        throw new Error("This account is inactive. Contact an administrator to reactivate access.");
      }
      if (response.mustChangePassword || user.mustChangePassword) {
        throw new Error("This account must change password before continuing. Use the reset password flow.");
      }

      const nextSession = { accessToken, refreshToken, user };
      persistSession(nextSession);
      setSession({
        accessToken,
        authError: "",
        authStatus: "authenticated",
        currentUser: user,
        refreshToken,
      });
      return user;
    } catch (error) {
      const message = getReadableAuthError(error, "Unable to log in with the provided credentials.");
      clearStoredSession();
      setSession({ ...emptySession, authError: message });
      throw new Error(message);
    }
  }, []);

  const logout = useCallback(async () => {
    const token = session.accessToken;
    clearStoredSession();
    setSession(emptySession);

    if (!token) {
      return;
    }

    try {
      await requestLogout(token);
    } catch (error) {
      setSession({
        ...emptySession,
        authError: getReadableAuthError(error, "Signed out locally. Backend logout could not be confirmed."),
      });
    }
  }, [session.accessToken]);

  const value = useMemo<SessionContextValue>(() => ({
    ...session,
    clearSession,
    isAuthenticated: session.authStatus === "authenticated" && Boolean(session.currentUser),
    login,
    logout,
  }), [clearSession, login, logout, session]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}

export function useCurrentUser() {
  const { currentUser } = useSession();
  if (!currentUser) {
    throw new Error("useCurrentUser must be used after authentication.");
  }
  return currentUser;
}

function loadStoredSession(): StoredAuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  legacyDemoStorageKeys.forEach((key) => window.localStorage.removeItem(key));

  const accessToken = window.localStorage.getItem(authAccessTokenStorageKey);
  const refreshToken = window.localStorage.getItem(authRefreshTokenStorageKey);
  const rawUser = window.localStorage.getItem(authUserStorageKey);
  if (!accessToken || !refreshToken || !rawUser) {
    clearStoredSession();
    return null;
  }

  try {
    const user = JSON.parse(rawUser) as unknown;
    if (!isStoredUser(user)) {
      clearStoredSession();
      return null;
    }
    return { accessToken, refreshToken, user: normalizeUser(user) };
  } catch {
    clearStoredSession();
    return null;
  }
}

function persistSession(session: StoredAuthSession) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(authAccessTokenStorageKey, session.accessToken);
  window.localStorage.setItem(authRefreshTokenStorageKey, session.refreshToken);
  window.localStorage.setItem(authUserStorageKey, JSON.stringify(session.user));
  legacyDemoStorageKeys.forEach((key) => window.localStorage.removeItem(key));
}

function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(authAccessTokenStorageKey);
  window.localStorage.removeItem(authRefreshTokenStorageKey);
  window.localStorage.removeItem(authUserStorageKey);
  legacyDemoStorageKeys.forEach((key) => window.localStorage.removeItem(key));
}

function getReadableAuthError(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 401) {
      return error.message || fallback;
    }
    if (error.status === 403) {
      return error.message || "This account does not have access.";
    }
    return error.message || fallback;
  }

  if (error instanceof TypeError) {
    return "Cannot reach the backend. Make sure the backend server is running and try again.";
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }

  return fallback;
}

function normalizeUser(user: AuthUserLike): User {
  return {
    ...user,
    id: String(user.id),
    phone: user.phone ?? "",
  };
}

function isStoredUser(value: unknown): value is AuthUserLike {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }

  const user = value as Partial<User>;
  return (
    (typeof user.id === "string" || typeof user.id === "number") &&
    typeof user.username === "string" &&
    typeof user.email === "string" &&
    typeof user.phone === "string" &&
    typeof user.fullName === "string" &&
    (user.role === "Admin" || user.role === "Staff" || user.role === "Doctor") &&
    (user.status === "Active" || user.status === "Inactive") &&
    typeof user.createdAt === "string" &&
    typeof user.mustChangePassword === "boolean"
  );
}
