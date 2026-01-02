import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { useViewStore } from "@/stores/viewStore";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { ListView } from "@/components/views/ListView";
import { KanbanView } from "@/components/views/KanbanView";
import { CalendarView } from "@/components/views/CalendarView";
import { TelegramLogin } from "@/components/TelegramLogin";
import { TelegramUser } from "@/types/task";

const queryClient = new QueryClient();

const BOT_NAME = import.meta.env.VITE_TELEGRAM_BOT_NAME || "ai4u_now_bot";

function AppContent() {
  const { user, loading, loginWithTelegram } = useAuth();
  const { currentView } = useViewStore();

  const handleTelegramAuth = async (telegramUser: TelegramUser) => {
    try {
      await loginWithTelegram(telegramUser);
    } catch (error) {
      console.error("Login failed:", error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-background to-muted">
        <div className="text-center space-y-6 p-8 rounded-lg border bg-card">
          <h1 className="text-3xl font-bold">Task Dashboard</h1>
          <p className="text-muted-foreground">
            Sign in with Telegram to access your tasks
          </p>
          <TelegramLogin botName={BOT_NAME} onAuth={handleTelegramAuth} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
          {currentView === "list" && <ListView />}
          {currentView === "kanban" && <KanbanView />}
          {currentView === "calendar" && <CalendarView />}
          {currentView === "timeline" && (
            <div className="text-center text-muted-foreground py-12">
              Timeline view coming soon...
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
