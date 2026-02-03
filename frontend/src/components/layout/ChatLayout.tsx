import { Navigate, Outlet } from "react-router";
import { useShallow } from "zustand/react/shallow";
import { FullPageSpinner } from "@/components/common";
import { useAuthStore } from "@/stores";

export function ChatLayout() {
  const { isAuthenticated, isInitialized } = useAuthStore(
    useShallow((s) => ({ isAuthenticated: s.isAuthenticated, isInitialized: s.isInitialized })),
  );

  if (!isInitialized) {
    return <FullPageSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen">
      <Outlet />
    </div>
  );
}
