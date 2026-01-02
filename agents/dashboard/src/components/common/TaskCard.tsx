import { SmartTask } from "@/types/task";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, Calendar, Clock, Tag } from "lucide-react";
import { format } from "date-fns";

interface TaskCardProps {
  task: SmartTask;
  onComplete?: () => void;
  compact?: boolean;
}

export function TaskCard({ task, onComplete, compact = false }: TaskCardProps) {
  const priorityColors = {
    p1: "bg-red-500",
    p2: "bg-orange-500",
    p3: "bg-yellow-500",
    p4: "bg-blue-500",
  };

  return (
    <Card className={compact ? "p-3" : ""}>
      <CardContent className={compact ? "p-0" : "pt-6"}>
        <div className="flex items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 rounded-full border"
            onClick={onComplete}
          >
            {task.status === "done" && <Check className="h-3 w-3" />}
          </Button>

          <div className="flex-1 space-y-2">
            <p
              className={`text-sm ${
                task.status === "done" ? "line-through text-muted-foreground" : ""
              }`}
            >
              {task.content}
            </p>

            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              {task.dueDate && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {format(new Date(task.dueDate), "MMM d")}
                  {task.dueTime && ` ${task.dueTime}`}
                </span>
              )}

              {task.estimatedDuration && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {task.estimatedDuration}m
                </span>
              )}

              {task.tags.length > 0 && (
                <span className="flex items-center gap-1">
                  <Tag className="h-3 w-3" />
                  {task.tags.join(", ")}
                </span>
              )}
            </div>

            <div className="flex gap-2">
              {task.priority && (
                <Badge variant="outline" className={priorityColors[task.priority]}>
                  {task.priority.toUpperCase()}
                </Badge>
              )}
              {task.energyLevel && (
                <Badge variant="secondary">{task.energyLevel}</Badge>
              )}
              {task.type !== "task" && (
                <Badge variant="outline">{task.type}</Badge>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
