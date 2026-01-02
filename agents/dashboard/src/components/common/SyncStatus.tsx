import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Cloud, CloudOff, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { SyncStatus as SyncStatusType } from "@/types/task";

export function SyncStatus() {
  const { data: status } = useQuery<SyncStatusType>({
    queryKey: ["sync-status"],
    queryFn: () => apiClient.getSyncStatus(),
    refetchInterval: 30000, // Every 30 seconds
  });

  if (!status) return null;

  const connected =
    status.google_calendar === "connected" ||
    status.google_tasks === "connected" ||
    status.apple_caldav === "connected";

  const hasErrors =
    status.google_calendar === "error" ||
    status.google_tasks === "error" ||
    status.apple_caldav === "error";

  return (
    <div className="flex items-center gap-2">
      {hasErrors ? (
        <Badge variant="destructive" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          Sync Error
        </Badge>
      ) : connected ? (
        <Badge variant="outline" className="text-green-600 gap-1">
          <Cloud className="h-3 w-3" />
          Synced
        </Badge>
      ) : (
        <Badge variant="outline" className="text-gray-400 gap-1">
          <CloudOff className="h-3 w-3" />
          Offline
        </Badge>
      )}

      {status.pending_conflicts > 0 && (
        <Badge variant="destructive">
          {status.pending_conflicts} conflicts
        </Badge>
      )}
    </div>
  );
}
