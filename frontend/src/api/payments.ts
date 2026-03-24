import type { CreditBalance, CreditPackage, PaginatedOrders, PaymentFormResponse } from "@/types";
import { apiClient } from "./client";

interface ListOrdersParams {
  page?: number;
  page_size?: number;
}

export const paymentsApi = {
  getPackages: async (): Promise<CreditPackage[]> => {
    const { data } = await apiClient.get<CreditPackage[]>("/payments/packages");
    return data;
  },

  createOrder: async (packageId: string): Promise<PaymentFormResponse> => {
    const { data } = await apiClient.post<PaymentFormResponse>("/payments/orders", {
      package_id: packageId,
    });
    return data;
  },

  getOrders: async (params?: ListOrdersParams): Promise<PaginatedOrders> => {
    const { data } = await apiClient.get<PaginatedOrders>("/payments/orders", { params });
    return data;
  },

  getBalance: async (): Promise<CreditBalance> => {
    const { data } = await apiClient.get<CreditBalance>("/payments/balance");
    return data;
  },
};
