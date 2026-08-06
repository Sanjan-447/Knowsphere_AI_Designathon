import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import * as notificationsApi from "@/api/notifications";

interface NavItem {
  to: string;
  label: string;
  roles: string[];
  badge?: boolean;
}

const WORKSPACE_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", roles: ["admin", "manager", "employee"] },
  { to: "/chat", label: "Ask Knowsphere", roles: ["admin", "manager", "employee"] },
  { to: "/documents", label: "Documents", roles: ["admin", "manager", "employee"] },
  { to: "/analytics", label: "Analytics", roles: ["admin", "manager"] },
];

const ADMIN_ITEMS: NavItem[] = [
  { to: "/knowledge-intelligence", label: "Knowledge intelligence", roles: ["admin"] },
  { to: "/retrieval-dashboard", label: "Retrieval dashboard", roles: ["admin"] },
  { to: "/system-monitoring", label: "System monitoring", roles: ["admin"] },
  { to: "/audit-log", label: "Audit log", roles: ["admin"] },
  { to: "/notifications", label: "Notifications", roles: ["admin"], badge: true },
  { to: "/admin/users", label: "User management", roles: ["admin"] },
  { to: "/settings/providers", label: "Provider settings", roles: ["admin"] },
  { to: "/settings/langsmith", label: "LangSmith observability", roles: ["admin"] },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (user?.role !== "admin") return;
    notificationsApi.listNotifications(true).then((d) => setUnreadCount(d.unread_count)).catch(() => {});
  }, [user]);

  function renderGroup(items: NavItem[], title?: string) {
    const visible = items.filter((item) => !user || item.roles.includes(user.role));
    if (visible.length === 0) return null;
    return (
      <div className="mb-2">
        {title && <div className="px-5 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-white/30">{title}</div>}
        {visible.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center justify-between border-l-[3px] px-5 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "border-gold bg-gold/10 text-paper"
                  : "border-transparent text-white/60 hover:bg-white/5 hover:text-paper"
              }`
            }
          >
            <span>{item.label}</span>
            {item.badge && unreadCount > 0 && (
              <span className="rounded-full bg-danger px-1.5 py-0.5 text-[10px] text-white">{unreadCount}</span>
            )}
          </NavLink>
        ))}
      </div>
    );
  }

  return (
    <aside className="flex h-screen w-60 flex-shrink-0 flex-col overflow-y-auto bg-ink py-6 text-paper">
      <div className="border-b border-white/10 px-5 pb-5">
        <div className="font-display text-xl font-semibold">
          Knowsphere<span className="text-gold"> AI</span>
        </div>
        <div className="mt-1 text-[10px] tracking-wide text-white/50">
          Enterprise knowledge assistant
        </div>
      </div>

      <nav className="mt-3 flex-1">
        {renderGroup(WORKSPACE_ITEMS)}
        {renderGroup(ADMIN_ITEMS, "Administration")}
      </nav>

      <div className="border-t border-white/10 px-5 pt-4">
        <div className="mb-3 text-xs text-white/70">
          <div className="font-medium text-paper">{user?.display_name}</div>
          <div className="text-white/40">{user?.role}</div>
        </div>
        <button
          onClick={() => logout()}
          className="w-full rounded border border-white/15 py-2 text-xs font-medium text-white/70 transition-colors hover:bg-white/5 hover:text-paper"
        >
          Log out
        </button>
      </div>
    </aside>
  );
}
