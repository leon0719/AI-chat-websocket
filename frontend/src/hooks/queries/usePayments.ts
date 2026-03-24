import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "@/api";
import { PAGINATION } from "@/lib/constants";
import { queryKeys } from "@/lib/queryClient";

export function usePackages() {
  return useQuery({
    queryKey: queryKeys.payments.packages,
    queryFn: () => paymentsApi.getPackages(),
    staleTime: 1000 * 60 * 10, // 10 minutes - packages rarely change
  });
}

export function useBalance() {
  return useQuery({
    queryKey: queryKeys.payments.balance,
    queryFn: () => paymentsApi.getBalance(),
  });
}

interface UseOrdersOptions {
  pageSize?: number;
}

export function useOrders(options?: UseOrdersOptions) {
  const { pageSize = PAGINATION.DEFAULT_PAGE_SIZE } = options ?? {};

  return useInfiniteQuery({
    queryKey: queryKeys.payments.orders({ pageSize }),
    queryFn: ({ pageParam = 1 }) =>
      paymentsApi.getOrders({
        page: pageParam,
        page_size: pageSize,
      }),
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
    initialPageParam: 1,
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (packageId: string) => paymentsApi.createOrder(packageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.payments.all });
    },
  });
}
