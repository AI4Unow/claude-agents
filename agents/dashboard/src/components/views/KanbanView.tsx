import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd";
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

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;

    const taskId = result.draggableId;
    const newStatus = result.destination.droppableId;

    const updates: any = { status: newStatus };
    if (newStatus === "done") {
      updates.completedAt = new Date().toISOString();
    }

    updateTask.mutate({ id: taskId, updates });
  };

  const getTasksByStatus = (status: string) =>
    tasks?.filter((t) => t.status === status) || [];

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className="flex gap-4 h-full overflow-x-auto pb-4">
        {COLUMNS.map((column) => (
          <div key={column.id} className="flex-shrink-0 w-80">
            <div className="bg-muted/50 rounded-lg p-4">
              <h3 className="font-semibold mb-4 flex items-center justify-between">
                {column.title}
                <span className="text-sm text-muted-foreground">
                  {getTasksByStatus(column.id).length}
                </span>
              </h3>

              <Droppable droppableId={column.id}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`space-y-2 min-h-[200px] ${
                      snapshot.isDraggingOver ? "bg-accent/50 rounded-md" : ""
                    }`}
                  >
                    {getTasksByStatus(column.id).map((task, index) => (
                      <Draggable key={task.id} draggableId={task.id} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            className={snapshot.isDragging ? "opacity-50" : ""}
                          >
                            <TaskCard task={task} compact />
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          </div>
        ))}
      </div>
    </DragDropContext>
  );
}
