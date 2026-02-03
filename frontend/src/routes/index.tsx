import { createBrowserRouter, Navigate } from "react-router";
import { AuthLayout, ChatLayout, RootLayout } from "@/components/layout";
import { ChatPage, LoginPage, RegisterPage } from "@/pages";

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          {
            path: "/login",
            element: <LoginPage />,
          },
          {
            path: "/register",
            element: <RegisterPage />,
          },
        ],
      },
      {
        element: <ChatLayout />,
        children: [
          {
            path: "/chat",
            element: <ChatPage />,
          },
        ],
      },
      {
        path: "/",
        element: <Navigate to="/chat" replace />,
      },
      {
        path: "*",
        element: <Navigate to="/chat" replace />,
      },
    ],
  },
]);
