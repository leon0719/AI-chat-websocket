export interface CreditPackage {
  id: string;
  name: string;
  credits: number;
  price: number;
  description: string;
}

export interface PaymentFormResponse {
  order_id: string;
  merchant_trade_no: string;
  form_html: string;
}

export interface PaymentOrder {
  id: string;
  merchant_trade_no: string;
  status: "pending" | "paid" | "failed";
  amount: number;
  credits_awarded: number;
  package_name: string;
  created_at: string;
  payment_date: string | null;
}

export interface PaginatedOrders {
  orders: PaymentOrder[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface CreditBalance {
  balance: number;
}
