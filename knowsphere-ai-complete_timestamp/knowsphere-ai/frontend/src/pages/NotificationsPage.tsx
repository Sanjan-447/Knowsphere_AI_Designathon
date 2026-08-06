import { useEffect, useState } from "react";
import * as notificationsApi from "@/api/notifications";
import type { NotificationEntry } from "@/types";

const SEVERITY_STYLES: Record<string, string> = {
  info: "border-l-teal",
  warning: "border-l-gold",
  error: "border-l-danger",
};

export function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    try {
      const data = await notificationsApi.listNotifications(unreadOnly);
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadOnly]);

  async function handleMarkRead(id: number) {
    await notificationsApi.markNotificationRead(id);
    await load();
  }

  async function handleMarkAllRead() {
    await notificationsApi.markAllNotificationsRead();
    await load();
  }

  async function handleScanExpired() {
    setScanning(true);
    try {
      const result = await notificationsApi.checkExpiredDocuments(365);
      setBanner(`Scan complete — ${result.created} new notification(s) created.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setScanning(false);
      setTimeout(() => setBanner(null), 4000);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Notifications</h1>
          <p className="mt-1 text-sm text-[#6B6558]">{unreadCount} unread</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleScanExpired} disabled={scanning} className="rounded border border-rule px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim disabled:opacity-50">
            {scanning ? "Scanning…" : "Scan for expired documents"}
          </button>
          <button onClick={handleMarkAllRead} className="rounded border border-rule px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim">
            Mark all read
          </button>
        </div>
      </div>

      {banner && <div className="mb-4 rounded border border-teal/30 bg-teal/5 px-3 py-2 text-sm text-teal">{banner}</div>}
      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      <label className="mb-4 flex items-center gap-2 text-xs text-[#6B6558]">
        <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
        Show unread only
      </label>

      {isLoading ? (
        <p className="text-sm text-[#6B6558]">Loading…</p>
      ) : notifications.length === 0 ? (
        <p className="rounded border border-dashed border-rule bg-white/60 px-4 py-8 text-center text-sm text-[#6B6558]">
          No notifications.
        </p>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`flex items-start justify-between gap-3 rounded border border-rule border-l-4 bg-white px-4 py-3 ${SEVERITY_STYLES[n.severity]} ${n.is_read ? "opacity-60" : ""}`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-ink">{n.title}</span>
                  <span className="rounded bg-paper-dim px-1.5 py-0.5 text-[10px] uppercase text-[#6B6558]">{n.notification_type}</span>
                </div>
                {n.message && <p className="mt-0.5 text-xs text-[#6B6558]">{n.message}</p>}
                <p className="mt-1 text-[11px] text-[#6B6558]">{new Date(n.created_at).toLocaleString()}</p>
              </div>
              {!n.is_read && (
                <button onClick={() => handleMarkRead(n.id)} className="flex-shrink-0 text-xs text-teal hover:underline">
                  Mark read
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
