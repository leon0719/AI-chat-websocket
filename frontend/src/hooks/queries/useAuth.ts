import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { authApi } from "@/api";
import { queryKeys } from "@/lib/queryClient";
import { useAuthStore } from "@/stores";
import type { LoginCredentials, RegisterCredentials } from "@/types";

export function useAuthInit() {
  const { setAccessToken, setUser, logout, setInitialized, isInitialized } = useAuthStore();

  useEffect(() => {
    if (isInitialized) return;

    const initAuth = async () => {
      try {
        const { access } = await authApi.refresh();
        setAccessToken(access);

        const user = await authApi.getMe();
        setUser(user);
      } catch {
        logout();
      } finally {
        setInitialized(true);
      }
    };

    initAuth();
  }, [isInitialized, setAccessToken, setUser, logout, setInitialized]);
}

export function useCurrentUser() {
  const { accessToken, isAuthenticated } = useAuthStore();

  return useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: authApi.getMe,
    enabled: !!accessToken && isAuthenticated,
    staleTime: 1000 * 60 * 10,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  const { login } = useAuthStore();

  return useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      const { access } = await authApi.login(credentials);
      const user = await authApi.getMe();
      return { access, user };
    },
    onSuccess: ({ access, user }) => {
      login(user, access);
      queryClient.setQueryData(queryKeys.auth.me, user);
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (credentials: RegisterCredentials) => authApi.register(credentials),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const { logout } = useAuthStore();

  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      logout();
      queryClient.clear();
    },
  });
}
