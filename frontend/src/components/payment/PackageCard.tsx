import { Button, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import type { CreditPackage } from "@/types";

interface PackageCardProps {
  pkg: CreditPackage;
  onBuy: (packageId: string) => void;
  isPending: boolean;
}

export function PackageCard({ pkg, onBuy, isPending }: PackageCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="text-lg">{pkg.name}</CardTitle>
        {pkg.description && <p className="text-sm text-muted-foreground">{pkg.description}</p>}
      </CardHeader>
      <CardContent className="mt-auto space-y-4">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold">NT${pkg.price}</span>
        </div>
        <div className="text-sm text-muted-foreground">{pkg.credits} 點</div>
        <Button className="w-full" onClick={() => onBuy(pkg.id)} disabled={isPending}>
          {isPending ? "處理中..." : "購買"}
        </Button>
      </CardContent>
    </Card>
  );
}
