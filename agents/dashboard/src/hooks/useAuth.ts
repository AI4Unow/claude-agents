import { useState, useEffect } from "react";
import { auth } from "@/lib/firebase";
import { apiClient } from "@/lib/api";
import { signInWithCustomToken, onAuthStateChanged, User } from "firebase/auth";
import { TelegramUser } from "@/types/task";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const loginWithTelegram = async (telegramUser: TelegramUser) => {
    try {
      setError(null);
      const { customToken } = await apiClient.verifyTelegramAuth({
        id: telegramUser.id,
        first_name: telegramUser.first_name,
        auth_date: telegramUser.auth_date,
        hash: telegramUser.hash,
      });
      await signInWithCustomToken(auth, customToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      throw err;
    }
  };

  const logout = () => auth.signOut();

  return { user, loading, error, loginWithTelegram, logout };
}
