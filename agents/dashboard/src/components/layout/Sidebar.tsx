import { useViewStore } from "@/stores/viewStore";
import { Button } from "@/components/ui/button";
import { List, Columns, Calendar, GanttChart } from "lucide-react";

export function Sidebar() {
  const { currentView, setView } = useViewStore();

  const views = [
    { id: "list" as const, label: "List", icon: List },
    { id: "kanban" as const, label: "Kanban", icon: Columns },
    { id: "calendar" as const, label: "Calendar", icon: Calendar },
    { id: "timeline" as const, label: "Timeline", icon: GanttChart },
  ];

  return (
    <aside className="w-64 border-r bg-muted/10 p-4">
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-muted-foreground px-3 mb-4">
          Views
        </h2>
        {views.map((view) => {
          const Icon = view.icon;
          return (
            <Button
              key={view.id}
              variant={currentView === view.id ? "secondary" : "ghost"}
              className="w-full justify-start"
              onClick={() => setView(view.id)}
            >
              <Icon className="h-4 w-4 mr-2" />
              {view.label}
            </Button>
          );
        })}
      </div>
    </aside>
  );
}
