import { useEffect, useRef } from "react";
import { TelegramUser } from "@/types/task";

interface TelegramLoginProps {
  botName: string;
  onAuth: (user: TelegramUser) => void;
}

export function TelegramLogin({ botName, onAuth }: TelegramLoginProps) {
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
