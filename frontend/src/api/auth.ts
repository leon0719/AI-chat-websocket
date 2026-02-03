import axios from "axios";
import { API_BASE_URL } from "@/lib/constants";
import type { LoginCredentials, RegisterCredentials, TokenResponse, User } from "@/types";
import { apiClient } from "./client";

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<TokenResponse> => {
    const { data } = await axios.post<TokenResponse>(
      `${API_BASE_URL}/auth/token/pair`,
      credentials,
      { withCredentials: true },
    );
    return data;
  },

  register: async (credentials: RegisterCredentials): Promise<User> => {
    const { data } = await axios.post<User>(`${API_BASE_URL}/auth/register`, credentials);
    return data;
  },

  refresh: async (): Promise<TokenResponse> => {
    const { data } = await axios.post<TokenResponse>(
      `${API_BASE_URL}/auth/token/refresh`,
      {},
      { withCredentials: true },
    );
    return data;
  },

  getMe: async (): Promise<User> => {
    const { data } = await apiClient.get<User>("/auth/me");
    return data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post("/auth/logout");
  },
};
