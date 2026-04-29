import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { LoginPage } from "./pages/LoginPage";
import { Dashboard } from "./pages/Dashboard";
import { LinesPage } from "./pages/LinesPage";
import { MachinesPage } from "./pages/MachinesPage";
import { OperatorsPage } from "./pages/OperatorsPage";
import { StylesPage } from "./pages/StylesPage";
import { StyleDetailPage } from "./pages/StyleDetailPage";
import { BalanceWizard } from "./pages/BalanceWizard";
import { BalanceResultPage } from "./pages/BalanceResultPage";
import { BottleneckDashboardPage } from "./pages/BottleneckDashboard";
import { RebalanceEventPage } from "./pages/RebalanceEventPage";
import { TimeStudyPage } from "./pages/TimeStudyPage";
import { IoTPage } from "./pages/IoTPage";
import { useAuth } from "./lib/auth";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = useAuth((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Shell>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/lines" element={<LinesPage />} />
                <Route path="/machines" element={<MachinesPage />} />
                <Route path="/operators" element={<OperatorsPage />} />
                <Route path="/styles" element={<StylesPage />} />
                <Route path="/styles/:id" element={<StyleDetailPage />} />
                <Route path="/balance" element={<BalanceWizard />} />
                <Route path="/balance/runs/:id" element={<BalanceResultPage />} />
                <Route path="/bottleneck" element={<BottleneckDashboardPage />} />
                <Route path="/rebalance/events/:id" element={<RebalanceEventPage />} />
                <Route path="/time-study" element={<TimeStudyPage />} />
                <Route path="/iot" element={<IoTPage />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
            </Shell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
