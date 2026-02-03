import { RouterProvider } from "react-router";
import { useAuthInit } from "@/hooks";
import { router } from "@/routes";

function AuthInitializer() {
  useAuthInit();
  return null;
}

function App() {
  return (
    <>
      <AuthInitializer />
      <RouterProvider router={router} />
    </>
  );
}

export default App;
