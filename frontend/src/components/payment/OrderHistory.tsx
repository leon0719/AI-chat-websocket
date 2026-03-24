import { Button } from "@/components/ui";
import { useOrders } from "@/hooks";
import type { PaymentOrder } from "@/types";

const STATUS_LABELS: Record<PaymentOrder["status"], string> = {
  pending: "處理中",
  paid: "已完成",
  failed: "失敗",
};

const STATUS_COLORS: Record<PaymentOrder["status"], string> = {
  pending: "text-yellow-600",
  paid: "text-green-600",
  failed: "text-red-600",
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });
}

export function OrderHistory() {
  const { data, isLoading, hasNextPage, fetchNextPage, isFetchingNextPage } = useOrders();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">載入中...</p>;
  }

  const orders = data?.pages.flatMap((page) => page.orders) ?? [];

  if (orders.length === 0) {
    return <p className="text-sm text-muted-foreground">尚無購買紀錄</p>;
  }

  return (
    <div className="space-y-3">
      {orders.map((order) => (
        <div key={order.id} className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">{order.package_name}</p>
            <p className="text-xs text-muted-foreground">{formatDate(order.created_at)}</p>
          </div>
          <div className="text-right space-y-1">
            <p className="text-sm font-medium">NT${order.amount}</p>
            <p className={`text-xs ${STATUS_COLORS[order.status]}`}>
              {STATUS_LABELS[order.status]}
            </p>
          </div>
        </div>
      ))}
      {hasNextPage && (
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
        >
          {isFetchingNextPage ? "載入中..." : "載入更多"}
        </Button>
      )}
    </div>
  );
}
