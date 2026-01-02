# Phase 4: Web Dashboard

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 1](phase-01-core-foundation.md), [Phase 2](phase-02-smart-features.md), [Phase 3](phase-03-calendar-sync.md)
- **Research**: [Brainstorm](../reports/brainstorm-260101-1736-smart-task-management.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2026-01-01 |
| Priority | P2 |
| Effort | 6h |
| Status | pending |

React SPA with multi-view task management (list, kanban, calendar, timeline). Telegram Login authentication, real-time Firebase sync.

## Key Decisions (from Brainstorm)

1. **Tech Stack**: React 18 + TypeScript + Vite + Tailwind + shadcn/ui
2. **State**: TanStack Query (server state) + Zustand (client state)
3. **Calendar View**: react-big-calendar
4. **Drag-drop**: @hello-pangea/dnd for Kanban
5. **Auth**: Telegram Login Widget → Firebase Custom Token
6. **Hosting**: Vercel (free tier)

## Requirements

1. Telegram Login Widget integration
2. Real-time Firebase Firestore listeners
3. Four views: List, Kanban, Calendar, Timeline
4. Task CRUD with optimistic updates
5. Sync status indicator (from Phase 3)
6. Mobile-responsive design
7. Dark mode support

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PHASE 4 ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  React SPA (Vercel)                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                                                                      ││
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    ││
│  │  │ List View  │  │  Kanban    │  │ Calendar   │  │ Timeline   │    ││
│  │  │            │  │            │  │            │  │            │    ││
│  │  │ • Filters  │  │ • Columns  │  │ • Month    │  │ • Gantt    │    ││
│  │  │ • Sort     │  │ • Drag/drop│  │ • Week     │  │ • Deps     │    ││
│  │  │ • Bulk     │  │ • Status   │  │ • Day      │  │ • Due bars │    ││
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    ││
│  │                                                                      ││
│  │  ┌─────────────────────────────────────────────────────────────────┐││
│  │  │ Common: TaskCard, TaskForm, QuickAdd, Filters, SyncStatus       │││
│  │  └─────────────────────────────────────────────────────────────────┘││
│  │                                                                      ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                         State Layer                                  ││
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      ││
│  │  │  TanStack Query │  │     Zustand     │  │   Firebase SDK  │      ││
│  │  │  (Server State) │  │  (Client State) │  │  (Real-time)    │      ││
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘      ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                              │                                           │
│                              ▼                                           │
│  Firebase Firestore ←──── Telegram Login ────► Modal API                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
dashboard/                    # New repo or agents/dashboard/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── TaskCard.tsx
│   │   │   ├── TaskForm.tsx
│   │   │   ├── QuickAdd.tsx
│   │   │   ├── Filters.tsx
│   │   │   └── SyncStatus.tsx
│   │   ├── views/
│   │   │   ├── ListView.tsx
│   │   │   ├── KanbanView.tsx
│   │   │   ├── CalendarView.tsx
│   │   │   └── TimelineView.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       ├── Header.tsx
│   │       └── ViewSwitcher.tsx
│   ├── hooks/
│   │   ├── useTasks.ts
│   │   ├── useAuth.ts
│   │   └── useRealtime.ts
│   ├── lib/
│   │   ├── firebase.ts
│   │   ├── api.ts
│   │   └── telegram.ts
│   ├── stores/
│   │   ├── viewStore.ts
│   │   └── filterStore.ts
│   ├── types/
│   │   └── task.ts
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Implementation Steps

### 1. Project Scaffold (1h)

1.1. Initialize project:
```bash
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install

# Core dependencies
npm install @tanstack/react-query zustand firebase

# UI
npm install tailwindcss postcss autoprefixer
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu
npm install class-variance-authority clsx tailwind-merge
npm install lucide-react

# Views
npm install react-big-calendar @hello-pangea/dnd date-fns

# Dev
npm install -D @types/react-big-calendar
```

1.2. Configure Tailwind + shadcn/ui:
```bash
npx tailwindcss init -p
npx shadcn@latest init
npx shadcn@latest add button card dialog input textarea badge
```

1.3. Firebase configuration:
```typescript
// src/lib/firebase.ts
import { initializeApp } from "firebase/app";
import { getFirestore, collection, onSnapshot } from "firebase/firestore";
import { getAuth, signInWithCustomToken } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

export const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
export const auth = getAuth(app);
```

### 2. Telegram Login (1h)

2.1. Telegram Login Widget component:
```typescript
// src/components/TelegramLogin.tsx
import { useEffect, useRef } from "react";

interface TelegramUser {
  id: number;
  first_name: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

interface Props {
  botName: string;
  onAuth: (user: TelegramUser) => void;
}

export function TelegramLogin({ botName, onAuth }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Inject Telegram widget script
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botName);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    script.async = true;

    // Global callback
    (window as any).onTelegramAuth = (user: TelegramUser) => {
      onAuth(user);
    };

    containerRef.current?.appendChild(script);

    return () => {
      delete (window as any).onTelegramAuth;
    };
  }, [botName, onAuth]);

  return <div ref={containerRef} />;
}
```

2.2. Auth hook with Firebase custom token:
```typescript
// src/hooks/useAuth.ts
import { useState, useEffect } from "react";
import { auth } from "@/lib/firebase";
import { signInWithCustomToken, onAuthStateChanged, User } from "firebase/auth";

interface TelegramUser {
  id: number;
  first_name: string;
  hash: string;
  auth_date: number;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const loginWithTelegram = async (telegramUser: TelegramUser) => {
    // Call backend to verify and get Firebase custom token
    const response = await fetch(`${import.meta.env.VITE_API_URL}/auth/telegram`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(telegramUser),
    });

    const { customToken } = await response.json();
    await signInWithCustomToken(auth, customToken);
  };

  const logout = () => auth.signOut();

  return { user, loading, loginWithTelegram, logout };
}
```

2.3. Backend endpoint for Telegram auth verification:
```python
# api/routes/auth.py (Modal backend)
import hmac
import hashlib

@router.post("/auth/telegram")
async def telegram_auth(data: TelegramAuthData):
    """Verify Telegram login and return Firebase custom token."""
    # Verify hash
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    secret = hashlib.sha256(bot_token.encode()).digest()

    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.dict().items())
        if k != "hash"
    )

    expected_hash = hmac.new(
        secret, check_string.encode(), hashlib.sha256
    ).hexdigest()

    if data.hash != expected_hash:
        raise HTTPException(401, "Invalid hash")

    # Check auth_date is recent (within 1 day)
    if time.time() - data.auth_date > 86400:
        raise HTTPException(401, "Auth expired")

    # Create Firebase custom token
    custom_token = firebase_auth.create_custom_token(str(data.id))

    return {"customToken": custom_token.decode()}
```

### 3. Task Data Layer (1.5h)

3.1. TypeScript types:
```typescript
// src/types/task.ts
export interface SmartTask {
  id: string;
  userId: number;
  content: string;
  type: "task" | "note" | "idea" | "link" | "quote";
  status: "inbox" | "active" | "done" | "archived";
  tags: string[];
  project?: string;
  priority?: "p1" | "p2" | "p3" | "p4";
  dueDate?: Date;
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
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
}
```

3.2. TanStack Query hooks:
```typescript
// src/hooks/useTasks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { collection, query, where, orderBy, onSnapshot, addDoc, updateDoc, deleteDoc, doc } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "./useAuth";
import { SmartTask } from "@/types/task";

export function useTasks(filters?: { status?: string; type?: string }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Real-time subscription
  useEffect(() => {
    if (!user) return;

    const tasksRef = collection(db, "pkm_items", user.uid, "items");
    let q = query(tasksRef, orderBy("createdAt", "desc"));

    if (filters?.status) {
      q = query(q, where("status", "==", filters.status));
    }

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const tasks = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      })) as SmartTask[];

      queryClient.setQueryData(["tasks", filters], tasks);
    });

    return unsubscribe;
  }, [user, filters, queryClient]);

  return useQuery({
    queryKey: ["tasks", filters],
    queryFn: () => [] as SmartTask[], // Initial, populated by subscription
    enabled: !!user,
    staleTime: Infinity, // Never stale, real-time updates
  });
}

export function useCreateTask() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (task: Partial<SmartTask>) => {
      const tasksRef = collection(db, "pkm_items", user!.uid, "items");
      const docRef = await addDoc(tasksRef, {
        ...task,
        userId: parseInt(user!.uid),
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      return docRef.id;
    },
    onMutate: async (newTask) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ["tasks"] });
      const previous = queryClient.getQueryData(["tasks"]);

      queryClient.setQueryData(["tasks"], (old: SmartTask[] = []) => [
        { ...newTask, id: "temp-" + Date.now() },
        ...old,
      ]);

      return { previous };
    },
    onError: (err, newTask, context) => {
      queryClient.setQueryData(["tasks"], context?.previous);
    },
  });
}

export function useUpdateTask() {
  const { user } = useAuth();

  return useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<SmartTask> }) => {
      const taskRef = doc(db, "pkm_items", user!.uid, "items", id);
      await updateDoc(taskRef, { ...updates, updatedAt: new Date() });
    },
  });
}
```

### 4. View Components (2h)

4.1. List View:
```typescript
// src/components/views/ListView.tsx
import { useTasks, useUpdateTask } from "@/hooks/useTasks";
import { TaskCard } from "@/components/common/TaskCard";
import { QuickAdd } from "@/components/common/QuickAdd";
import { Filters } from "@/components/common/Filters";

export function ListView() {
  const { data: tasks, isLoading } = useTasks();
  const updateTask = useUpdateTask();

  const handleComplete = (id: string) => {
    updateTask.mutate({ id, updates: { status: "done", completedAt: new Date() } });
  };

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-4">
      <Filters />
      <QuickAdd />

      <div className="space-y-2">
        {tasks?.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onComplete={() => handleComplete(task.id)}
          />
        ))}
      </div>
    </div>
  );
}
```

4.2. Kanban View:
```typescript
// src/components/views/KanbanView.tsx
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import { useTasks, useUpdateTask } from "@/hooks/useTasks";
import { TaskCard } from "@/components/common/TaskCard";

const COLUMNS = [
  { id: "inbox", title: "Inbox" },
  { id: "active", title: "Active" },
  { id: "done", title: "Done" },
];

export function KanbanView() {
  const { data: tasks } = useTasks();
  const updateTask = useUpdateTask();

  const handleDragEnd = (result: any) => {
    if (!result.destination) return;

    const taskId = result.draggableId;
    const newStatus = result.destination.droppableId;

    updateTask.mutate({ id: taskId, updates: { status: newStatus } });
  };

  const getTasksByStatus = (status: string) =>
    tasks?.filter((t) => t.status === status) || [];

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-4 h-full">
        {COLUMNS.map((column) => (
          <Droppable key={column.id} droppableId={column.id}>
            {(provided) => (
              <div
                ref={provided.innerRef}
                {...provided.droppableProps}
                className="w-80 bg-gray-100 dark:bg-gray-800 rounded-lg p-4"
              >
                <h3 className="font-semibold mb-4">{column.title}</h3>
                <div className="space-y-2">
                  {getTasksByStatus(column.id).map((task, index) => (
                    <Draggable key={task.id} draggableId={task.id} index={index}>
                      {(provided) => (
                        <div
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                        >
                          <TaskCard task={task} compact />
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </div>
              </div>
            )}
          </Droppable>
        ))}
      </div>
    </DragDropContext>
  );
}
```

4.3. Calendar View:
```typescript
// src/components/views/CalendarView.tsx
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { useTasks } from "@/hooks/useTasks";
import "react-big-calendar/lib/css/react-big-calendar.css";

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales: {},
});

export function CalendarView() {
  const { data: tasks } = useTasks();

  const events = tasks
    ?.filter((t) => t.dueDate)
    .map((task) => ({
      id: task.id,
      title: task.content,
      start: new Date(task.dueDate!),
      end: new Date(task.dueDate!),
      allDay: !task.dueTime,
      resource: task,
    })) || [];

  return (
    <div className="h-[600px]">
      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        views={["month", "week", "day"]}
        defaultView="month"
        onSelectEvent={(event) => {
          // Open task detail modal
        }}
      />
    </div>
  );
}
```

4.4. Sync Status component:
```typescript
// src/components/common/SyncStatus.tsx
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Cloud, CloudOff, RefreshCw } from "lucide-react";

export function SyncStatus() {
  const { data: status } = useQuery({
    queryKey: ["sync-status"],
    queryFn: async () => {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/sync/status`);
      return res.json();
    },
    refetchInterval: 30000, // Every 30 seconds
  });

  if (!status) return null;

  const connected =
    status.google_calendar === "connected" ||
    status.google_tasks === "connected" ||
    status.apple_caldav === "connected";

  return (
    <div className="flex items-center gap-2">
      {connected ? (
        <Badge variant="outline" className="text-green-600">
          <Cloud className="w-3 h-3 mr-1" />
          Synced
        </Badge>
      ) : (
        <Badge variant="outline" className="text-gray-400">
          <CloudOff className="w-3 h-3 mr-1" />
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
```

### 5. Deploy to Vercel (0.5h)

5.1. Environment variables:
```env
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=xxx
VITE_API_URL=https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
VITE_TELEGRAM_BOT_NAME=ai4u_now_bot
```

5.2. Vercel configuration:
```json
// vercel.json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "routes": [
    { "handle": "filesystem" },
    { "src": "/(.*)", "dest": "/index.html" }
  ]
}
```

5.3. Deploy:
```bash
npm install -g vercel
vercel --prod
```

## Todo List

- [ ] Initialize Vite + React + TypeScript project
- [ ] Configure Tailwind + shadcn/ui
- [ ] Set up Firebase SDK
- [ ] Build Telegram Login component
- [ ] Create auth verification endpoint in Modal
- [ ] Build TanStack Query hooks for tasks
- [ ] Implement real-time Firestore subscription
- [ ] Create TaskCard and TaskForm components
- [ ] Build ListView component
- [ ] Build KanbanView with drag-drop
- [ ] Build CalendarView with react-big-calendar
- [ ] Build TimelineView (optional, can defer)
- [ ] Add SyncStatus indicator
- [ ] Implement dark mode toggle
- [ ] Mobile responsive testing
- [ ] Deploy to Vercel

## Success Criteria

1. Telegram Login works end-to-end
2. Real-time updates < 1 second latency
3. Drag-drop in Kanban updates Firebase correctly
4. Calendar view shows all tasks with due dates
5. Initial load < 2 seconds
6. Works on mobile (responsive)

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Telegram widget blocked | High | Low | Fallback to manual auth link |
| Firebase real-time costs | Medium | Medium | Limit listeners, batch updates |
| react-big-calendar perf | Medium | Low | Virtualize, limit date range |
| Drag-drop conflicts | Medium | Low | Optimistic + retry on error |

## Security Considerations

1. Telegram login hash verification on backend only
2. Firebase rules restrict access to user's own data
3. API URL not hardcoded in production build
4. CORS configured for dashboard domain only

## Next Steps

After Phase 4 complete:
1. User testing with real Telegram accounts
2. Performance profiling
3. Consider PWA for offline support
4. Future: React Native mobile app

## Unresolved Questions

1. Should we create separate repo or subfolder in agents?
2. Domain: tasks.ai4u.now or app.ai4u.now?
3. Should Timeline view be MVP or deferred?
4. PWA offline support in scope?
