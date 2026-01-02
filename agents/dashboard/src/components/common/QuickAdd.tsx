import { useState } from "react";
import { useCreateTask } from "@/hooks/useTasks";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export function QuickAdd() {
  const [content, setContent] = useState("");
  const createTask = useCreateTask();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    await createTask.mutateAsync({
      content: content.trim(),
      type: "task",
      status: "inbox",
      tags: [],
      blockedBy: [],
      autoCreated: false,
    });

    setContent("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Input
        placeholder="Add a task... (e.g., 'Call dentist tomorrow at 2pm')"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="flex-1"
      />
      <Button type="submit" disabled={createTask.isPending}>
        <Plus className="h-4 w-4 mr-2" />
        Add
      </Button>
    </form>
  );
}
