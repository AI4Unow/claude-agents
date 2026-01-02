import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { useTasks } from "@/hooks/useTasks";
import "react-big-calendar/lib/css/react-big-calendar.css";

const locales = {
  "en-US": require("date-fns/locale/en-US"),
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
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
    <div className="h-[calc(100vh-200px)] bg-background rounded-lg p-4">
      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        views={["month", "week", "day"]}
        defaultView="month"
        onSelectEvent={(event) => {
          // TODO: Open task detail modal
          console.log("Selected task:", event.resource);
        }}
        style={{ height: "100%" }}
      />
    </div>
  );
}
