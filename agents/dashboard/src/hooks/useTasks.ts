import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  collection,
  query,
  where,
  orderBy,
  onSnapshot,
  addDoc,
  updateDoc,
  deleteDoc,
  doc,
  Timestamp,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "./useAuth";
import { SmartTask } from "@/types/task";

interface TaskFilters {
  status?: string;
  type?: string;
}

export function useTasks(filters?: TaskFilters) {
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
      const tasks = snapshot.docs.map((doc) => {
        const data = doc.data();
        return {
          id: doc.id,
          ...data,
          dueDate: data.dueDate instanceof Timestamp ? data.dueDate.toDate().toISOString() : data.dueDate,
          createdAt: data.createdAt instanceof Timestamp ? data.createdAt.toDate().toISOString() : data.createdAt,
          updatedAt: data.updatedAt instanceof Timestamp ? data.updatedAt.toDate().toISOString() : data.updatedAt,
          completedAt: data.completedAt instanceof Timestamp ? data.completedAt.toDate().toISOString() : data.completedAt,
        } as SmartTask;
      });

      queryClient.setQueryData(["tasks", filters], tasks);
    });

    return unsubscribe;
  }, [user, filters, queryClient]);

  return useQuery<SmartTask[]>({
    queryKey: ["tasks", filters],
    queryFn: () => [], // Initial, populated by subscription
    enabled: !!user,
    staleTime: Infinity, // Never stale, real-time updates
  });
}

export function useCreateTask() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (task: Partial<SmartTask>) => {
      if (!user) throw new Error("User not authenticated");

      const tasksRef = collection(db, "pkm_items", user.uid, "items");
      const docRef = await addDoc(tasksRef, {
        ...task,
        userId: parseInt(user.uid),
        createdAt: Timestamp.now(),
        updatedAt: Timestamp.now(),
      });
      return docRef.id;
    },
    onMutate: async (newTask) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ["tasks"] });
      const previous = queryClient.getQueryData(["tasks"]);

      queryClient.setQueryData(["tasks"], (old: SmartTask[] = []) => [
        {
          ...newTask,
          id: "temp-" + Date.now(),
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        } as SmartTask,
        ...old,
      ]);

      return { previous };
    },
    onError: (_err, _newTask, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["tasks"], context.previous);
      }
    },
  });
}

export function useUpdateTask() {
  const { user } = useAuth();

  return useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<SmartTask> }) => {
      if (!user) throw new Error("User not authenticated");

      const taskRef = doc(db, "pkm_items", user.uid, "items", id);
      await updateDoc(taskRef, {
        ...updates,
        updatedAt: Timestamp.now()
      });
    },
  });
}

export function useDeleteTask() {
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (id: string) => {
      if (!user) throw new Error("User not authenticated");

      const taskRef = doc(db, "pkm_items", user.uid, "items", id);
      await deleteDoc(taskRef);
    },
  });
}
