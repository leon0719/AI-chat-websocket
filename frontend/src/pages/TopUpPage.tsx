import { useRef } from "react";
import { useNavigate } from "react-router";
import { Separator } from "@/components/ui";
import { CreditBalance, OrderHistory, PackageCard } from "@/components/payment";
import { useCreateOrder, usePackages } from "@/hooks";

export function TopUpPage() {
  const navigate = useNavigate();
  const formContainerRef = useRef<HTMLDivElement>(null);
  const { data: packages, isLoading } = usePackages();
  const createOrder = useCreateOrder();

  const handleBuy = (packageId: string) => {
    createOrder.mutate(packageId, {
      onSuccess: (data) => {
        // ECPay form HTML is server-generated from our own backend (trusted source).
        // We parse it safely and reconstruct the form via DOM APIs.
        const parser = new DOMParser();
        const doc = parser.parseFromString(data.form_html, "text/html");
        const sourceForm = doc.querySelector("form");
        if (!sourceForm || !formContainerRef.current) return;

        const form = document.createElement("form");
        form.method = sourceForm.method;
        form.action = sourceForm.action;

        for (const input of sourceForm.querySelectorAll("input")) {
          const clone = document.createElement("input");
          clone.type = "hidden";
          clone.name = input.name;
          clone.value = input.value;
          form.appendChild(clone);
        }

        formContainerRef.current.appendChild(form);
        form.submit();
      },
    });
  };

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">儲值點數</h1>
          <p className="text-muted-foreground">購買點數以使用 AI 聊天服務</p>
        </div>
        <div className="flex items-center gap-4">
          <CreditBalance />
          <button
            type="button"
            onClick={() => navigate("/chat")}
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            返回聊天
          </button>
        </div>
      </div>

      <Separator />

      {isLoading ? (
        <p className="text-muted-foreground">載入方案中...</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {packages?.map((pkg) => (
            <PackageCard
              key={pkg.id}
              pkg={pkg}
              onBuy={handleBuy}
              isPending={createOrder.isPending}
            />
          ))}
        </div>
      )}

      {createOrder.isError && (
        <p className="text-sm text-destructive">建立訂單失敗，請稍後再試</p>
      )}

      <Separator />

      <div>
        <h2 className="mb-4 text-lg font-semibold">購買紀錄</h2>
        <OrderHistory />
      </div>

      {/* Container for ECPay form submission */}
      <div ref={formContainerRef} className="hidden" />
    </div>
  );
}
