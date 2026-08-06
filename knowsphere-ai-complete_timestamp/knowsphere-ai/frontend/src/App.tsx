import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { LoginPage } from "@/pages/LoginPage";

// Phase 6 performance: route-level code splitting. Each dashboard page
// (several of which pull in recharts, a non-trivial dependency) is only
// fetched when its route is actually visited, not bundled into the
// initial page load everyone pays for just to log in and chat.
const DashboardHomePage = lazy(() => import("@/pages/DashboardHomePage").then((m) => ({ default: m.DashboardHomePage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const ProviderManagementPage = lazy(() => import("@/pages/ProviderManagementPage").then((m) => ({ default: m.ProviderManagementPage })));
const LangSmithSettingsPage = lazy(() => import("@/pages/LangSmithSettingsPage").then((m) => ({ default: m.LangSmithSettingsPage })));
const DocumentsPage = lazy(() => import("@/pages/DocumentsPage").then((m) => ({ default: m.DocumentsPage })));
const ChatPage = lazy(() => import("@/pages/ChatPage").then((m) => ({ default: m.ChatPage })));
const RetrievalDashboardPage = lazy(() => import("@/pages/RetrievalDashboardPage").then((m) => ({ default: m.RetrievalDashboardPage })));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })));
const KnowledgeIntelligencePage = lazy(() => import("@/pages/KnowledgeIntelligencePage").then((m) => ({ default: m.KnowledgeIntelligencePage })));
const SystemMonitoringPage = lazy(() => import("@/pages/SystemMonitoringPage").then((m) => ({ default: m.SystemMonitoringPage })));
const AuditLogPage = lazy(() => import("@/pages/AuditLogPage").then((m) => ({ default: m.AuditLogPage })));
const NotificationsPage = lazy(() => import("@/pages/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const AdminUsersPage = lazy(() => import("@/pages/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));

function PageFallback() {
  return <div className="flex h-full items-center justify-center text-sm text-[#6B6558]">Loading…</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path="/" element={<DashboardHomePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/settings" element={<SettingsPage />} />

                <Route element={<ProtectedRoute allowedRoles={["admin", "manager"]} />}>
                  <Route path="/analytics" element={<AnalyticsPage />} />
                </Route>

                <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                  <Route path="/settings/providers" element={<ProviderManagementPage />} />
                  <Route path="/settings/langsmith" element={<LangSmithSettingsPage />} />
                  <Route path="/retrieval-dashboard" element={<RetrievalDashboardPage />} />
                  <Route path="/knowledge-intelligence" element={<KnowledgeIntelligencePage />} />
                  <Route path="/system-monitoring" element={<SystemMonitoringPage />} />
                  <Route path="/audit-log" element={<AuditLogPage />} />
                  <Route path="/notifications" element={<NotificationsPage />} />
                  <Route path="/admin/users" element={<AdminUsersPage />} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
