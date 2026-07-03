import { mockUsers } from "./mockUsers";
import type { Role, User } from "../types/models";

export interface DemoSessionUser {
  label: string;
  description: string;
  role: Role;
  user: User;
}

const findDemoUser = (role: Role, preferredUsername?: string) => {
  const preferred = preferredUsername
    ? mockUsers.find((user) => user.username === preferredUsername && user.status === "Active")
    : undefined;
  return preferred ?? mockUsers.find((user) => user.role === role && user.status === "Active") ?? mockUsers[0];
};

export const demoSessionUsers: DemoSessionUser[] = [
  {
    label: "Admin",
    description: "Administrator",
    role: "Admin",
    user: findDemoUser("Admin"),
  },
  {
    label: "Staff",
    description: "Reception / Staff",
    role: "Staff",
    user: findDemoUser("Staff", "olivia.frontdesk"),
  },
  {
    label: "Doctor",
    description: "Doctor",
    role: "Doctor",
    user: findDemoUser("Doctor", "michael.martinez"),
  },
];

export const demoSessionStorageKey = "dentalcare.demoLoginRole";
export const legacyDemoSessionStorageKey = "dentalcare.demoRole";
export const defaultDemoUser = demoSessionUsers[0].user;

export const mockSession = {
  currentUser: defaultDemoUser,
};
