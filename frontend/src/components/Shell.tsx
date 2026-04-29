import { NavLink, useNavigate } from "react-router-dom";
import { LogOut, Factory, Users, Wrench, Shirt, GitBranch, LayoutDashboard, Cog, Activity, Timer, Cpu } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/balance", label: "Balance Wizard", icon: GitBranch },
  { to: "/bottleneck", label: "Bottleneck", icon: Activity },
  { to: "/time-study", label: "Time Study", icon: Timer },
  { to: "/iot", label: "IoT", icon: Cpu },
  { to: "/styles", label: "Styles", icon: Shirt },
  { to: "/operators", label: "Operators", icon: Users },
  { to: "/machines", label: "Machines", icon: Wrench },
  { to: "/lines", label: "Lines", icon: Factory },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const { username, role, clear } = useAuth();
  const nav = useNavigate();
  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="md:w-64 shrink-0 border-b md:border-b-0 md:border-r bg-muted/30">
        <div className="px-4 py-4 flex items-center gap-2 border-b">
          <Cog className="h-5 w-5" />
          <div className="font-semibold leading-tight">
            Line Balancing
            <div className="text-xs text-muted-foreground">Apparel CMT · v0.1</div>
          </div>
        </div>
        <nav className="p-2 grid grid-cols-2 md:grid-cols-1 gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
                  isActive ? "bg-primary text-primary-foreground" : "hover:bg-accent"
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t mt-auto md:fixed md:bottom-0 md:w-64 bg-muted/30">
          <div className="text-xs text-muted-foreground">Signed in as</div>
          <div className="text-sm font-medium">{username}</div>
          <div className="text-xs text-muted-foreground mb-2">{role}</div>
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => {
              clear();
              nav("/login");
            }}
          >
            <LogOut className="h-3.5 w-3.5 mr-2" /> Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
    </div>
  );
}
