import { Navigate, Outlet } from "react-router";
import { useShallow } from "zustand/react/shallow";
import { FullPageSpinner } from "@/components/common";
import { useAuthStore } from "@/stores";

export function AuthLayout() {
  const { isAuthenticated, isInitialized } = useAuthStore(
    useShallow((s) => ({ isAuthenticated: s.isAuthenticated, isInitialized: s.isInitialized })),
  );

  if (!isInitialized) {
    return <FullPageSpinner />;
  }

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Outlet />
      </div>
    </div>
  );
}
