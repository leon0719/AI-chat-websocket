import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "請輸入電子郵件").email("請輸入有效的電子郵件"),
  password: z.string().min(1, "請輸入密碼"),
});

export const registerSchema = z
  .object({
    email: z.string().min(1, "請輸入電子郵件").email("請輸入有效的電子郵件"),
    username: z
      .string()
      .min(3, "使用者名稱至少 3 個字元")
      .max(50, "使用者名稱最多 50 個字元")
      .regex(/^[a-zA-Z0-9_-]+$/, "使用者名稱只能包含字母、數字、底線和連字號"),
    password: z
      .string()
      .min(12, "密碼至少 12 個字元")
      .max(128, "密碼最多 128 個字元")
      .regex(/[a-z]/, "密碼必須包含至少一個小寫字母")
      .regex(/[A-Z]/, "密碼必須包含至少一個大寫字母")
      .regex(/\d/, "密碼必須包含至少一個數字")
      .regex(/[!@#$%^&*(),.?":{}|<>_\-+=[\]\\;'`~]/, "密碼必須包含至少一個特殊字元"),
    confirmPassword: z.string().min(1, "請確認密碼"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "密碼不相符",
    path: ["confirmPassword"],
  });

export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormData = z.infer<typeof registerSchema>;
