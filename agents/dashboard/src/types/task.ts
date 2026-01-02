export interface SmartTask {
  id: string;
  userId: number;
  content: string;
  type: "task" | "note" | "idea" | "link" | "quote";
  status: "inbox" | "active" | "done" | "archived";
  tags: string[];
  project?: string;
  priority?: "p1" | "p2" | "p3" | "p4";
  dueDate?: string; // ISO string
  dueTime?: string; // HH:mm format
  reminderOffset?: number;
  recurrence?: string;
  estimatedDuration?: number;
  energyLevel?: "high" | "medium" | "low";
  context?: string;
  blockedBy: string[];
  googleEventId?: string;
  googleTaskId?: string;
  appleUid?: string;
  autoCreated: boolean;
  sourceMessageId?: number;
  confidenceScore?: number;
  createdAt: string; // ISO string
  updatedAt: string; // ISO string
  completedAt?: string; // ISO string
}

export interface TelegramUser {
  id: number;
  first_name: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export interface SyncStatus {
  google_calendar: "connected" | "disconnected" | "error";
  google_tasks: "connected" | "disconnected" | "error";
  apple_caldav: "connected" | "disconnected" | "error";
  pending_conflicts: number;
  last_sync?: string; // ISO string
}
