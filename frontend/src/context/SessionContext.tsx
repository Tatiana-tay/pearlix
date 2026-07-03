import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { demoSessionStorageKey, demoSessionUsers, defaultDemoUser, legacyDemoSessionStorageKey } from "../data/mockSession";
import type { Role, User } from "../types/models";
import { loadMockUsers } from "../utils/mockClinicState";

interface SessionContextValue {
  currentUser: User;
  demoUsers: typeof demoSessionUsers;
  loginAsUser: (user: User) => User;
  loginAsRole: (role: Role) => User;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

const isRole = (value: string | null): value is Role => value === "Admin" || value === "Staff" || value === "Doctor";

const getInitialUser = () => {
  if (typeof window === "undefined") {
    return defaultDemoUser;
  }

  window.localStorage.removeItem(legacyDemoSessionStorageKey);
  const storedRole = window.localStorage.getItem(demoSessionStorageKey);
  if (!isRole(storedRole)) {
    window.localStorage.setItem(demoSessionStorageKey, defaultDemoUser.role);
    return defaultDemoUser;
  }

  return loadMockUsers().find((user) => user.role === storedRole && user.status === "Active") ??
    demoSessionUsers.find((demoUser) => demoUser.role === storedRole)?.user ??
    defaultDemoUser;
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<User>(getInitialUser);

  const value = useMemo<SessionContextValue>(() => ({
    currentUser,
    demoUsers: demoSessionUsers,
    loginAsUser: (user) => {
      window.localStorage.setItem(demoSessionStorageKey, user.role);
      setCurrentUser(user);
      return user;
    },
    loginAsRole: (role) => {
      const nextUser = loadMockUsers().find((user) => user.role === role && user.status === "Active") ??
        demoSessionUsers.find((demoUser) => demoUser.role === role)?.user ??
        defaultDemoUser;
      window.localStorage.setItem(demoSessionStorageKey, role);
      setCurrentUser(nextUser);
      return nextUser;
    },
    logout: () => {
      window.localStorage.removeItem(demoSessionStorageKey);
      window.localStorage.removeItem(legacyDemoSessionStorageKey);
      setCurrentUser(defaultDemoUser);
    },
  }), [currentUser]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}
