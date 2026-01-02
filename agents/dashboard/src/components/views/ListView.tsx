import { useTasks, useUpdateTask } from "@/hooks/useTasks";
import { TaskCard } from "@/components/common/TaskCard";
import { QuickAdd } from "@/components/common/QuickAdd";

export function ListView() {
  const { data: tasks, isLoading } = useTasks();
  const updateTask = useUpdateTask();

  const handleComplete = (id: string, currentStatus: string) => {
    const newStatus = currentStatus === "done" ? "active" : "done";
    const updates: any = { status: newStatus };
    if (newStatus === "done") {
      updates.completedAt = new Date().toISOString();
    }
    updateTask.mutate({ id, updates });
  };

  if (isLoading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="space-y-4">
      <QuickAdd />

      <div className="space-y-2">
        {tasks && tasks.length === 0 && (
          <div className="text-center text-muted-foreground py-12">
            No tasks yet. Add one above to get started!
          </div>
        )}
        {tasks?.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onComplete={() => handleComplete(task.id, task.status)}
          />
        ))}
      </div>
    </div>
  );
}
