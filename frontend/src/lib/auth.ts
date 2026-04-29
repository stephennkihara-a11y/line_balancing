import { create } from "zustand";

type Role = "ADMIN" | "PRODUCTION_MANAGER" | "SUPERVISOR" | "IE" | "OPERATOR";

interface AuthState {
  token: string | null;
  username: string | null;
  role: Role | null;
  setAuth: (t: { token: string; username: string; role: Role }) => void;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  token: localStorage.getItem("token"),
  username: localStorage.getItem("username"),
  role: localStorage.getItem("role") as Role | null,
  setAuth: ({ token, username, role }) => {
    localStorage.setItem("token", token);
    localStorage.setItem("username", username);
    localStorage.setItem("role", role);
    set({ token, username, role });
  },
  clear: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    set({ token: null, username: null, role: null });
  },
}));
