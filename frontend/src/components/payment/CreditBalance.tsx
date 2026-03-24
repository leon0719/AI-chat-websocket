import { useBalance } from "@/hooks";

export function CreditBalance() {
  const { data, isLoading } = useBalance();

  if (isLoading) {
    return <span className="text-sm text-muted-foreground">載入中...</span>;
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">點數餘額:</span>
      <span className="font-semibold">{data?.balance ?? 0}</span>
    </div>
  );
}
