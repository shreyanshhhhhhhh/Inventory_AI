export type ApiCategory = {
  id: string;
  name: string;
};

export type ApiSupplier = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  lead_time_days: number;
  is_active: boolean;
};

export type ApiProduct = {
  id: string;
  sku: string;
  name: string;
  category_id: string | null;
  category_name: string | null;
  unit: string;
  cost: string | null;
  price: string | null;
  reorder_point: string | null;
  safety_stock: string | null;
  preferred_supplier_id: string | null;
  preferred_supplier_name: string | null;
  is_active: boolean;
};

export type ApiProductList = {
  items: ApiProduct[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiUser = {
  id: string;
  email: string;
  full_name: string;
  role: "owner" | "staff";
  business_id: string;
};

export type ApiTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: ApiUser;
};

export type ApiBusiness = {
  id: string;
  name: string;
  currency_code: string;
  onboarding_completed: boolean;
};

export type ApiOnboardingStatus = {
  completed: boolean;
  completed_at: string | null;
  business_name: string;
  currency_code: string;
  location_count: number;
  product_count: number;
  supplier_count: number;
  can_complete: boolean;
};

export type ApiAuditEntry = {
  id: string;
  created_at: string;
  actor_type: "user" | "agent";
  actor_user_id: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
};

export type ApiAuditLog = {
  items: ApiAuditEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiProductWrite = {
  sku: string;
  name: string;
  category_id?: string | null;
  unit: string;
  cost?: string | null;
  price?: string | null;
  reorder_point?: string | null;
  safety_stock?: string | null;
  preferred_supplier_id?: string | null;
};

export type ApiSupplierWrite = {
  name: string;
  email?: string | null;
  phone?: string | null;
  lead_time_days: number;
};

export type ApiLocation = {
  id: string;
  name: string;
  is_default: boolean;
};

export type ApiStockLevel = {
  product_id: string;
  location_id: string;
  sku: string;
  product_name: string;
  location_name: string;
  on_hand: string;
  reorder_point: string | null;
  status: "in_stock" | "low" | "out";
};

export type ApiStockList = {
  items: ApiStockLevel[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiMovement = {
  id: string;
  occurred_at: string;
  product_id: string;
  product_name: string;
  location_id: string;
  location_name: string;
  movement_type: "receipt" | "purchase_receipt" | "sale" | "adjustment" | "transfer";
  quantity: string;
  note: string | null;
  reason: string | null;
  user_id: string;
  user_name: string;
};

export type ApiMovementList = {
  items: ApiMovement[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiMovementWrite = {
  product_id: string;
  location_id: string;
  type: "receipt" | "sale" | "adjustment" | "transfer";
  quantity: string;
  note?: string | null;
  destination_location_id?: string | null;
};

export type ApiSaleWrite = {
  location_id: string;
  lines: Array<{ product_id: string; quantity: string }>;
  note?: string | null;
};

export type ApiSale = {
  sale_group_id: string;
  items: ApiMovement[];
};

export type ApiPurchaseOrderLine = {
  id: string;
  product_id: string;
  product_name: string;
  quantity: string;
  unit_cost: string;
  line_total: string;
};

export type ApiPurchaseOrder = {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_name: string;
  location_id: string;
  status: "draft" | "approved" | "sent" | "received" | "cancelled";
  expected_date: string | null;
  notes: string | null;
  ordered_at: string | null;
  total: string;
  line_items: ApiPurchaseOrderLine[];
};

export type ApiPurchaseOrderList = {
  items: ApiPurchaseOrder[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiPurchaseOrderWrite = {
  supplier_id: string;
  expected_date?: string | null;
  location_id?: string | null;
  notes?: string | null;
  line_items: Array<{
    product_id: string;
    quantity: string;
    unit_cost?: string | null;
  }>;
};

export type ApiPurchaseOrderTransition = {
  action: "approve" | "send" | "receive" | "cancel";
};

export type ApiImportRowError = {
  row: number;
  message: string;
};

export type ApiImportResult = {
  imported_count: number;
  skipped_count: number;
  error_count: number;
  errors: ApiImportRowError[];
  success: boolean;
};

export type ApiDashboardSummary = {
  total_stock_value: string;
  unvalued_product_count: number;
  low_stock_count: number;
  open_purchase_orders: number;
  pending_approvals: number;
  open_exceptions: number;
};

export type ApiNeedsAttentionItem = {
  product_id: string;
  location_id: string;
  sku: string;
  product_name: string;
  location_name: string;
  on_hand: string;
  reorder_point: string | null;
  status: "in_stock" | "low" | "out";
};

export type ApiDashboardActivityItem = {
  id: string;
  kind: "movement" | "purchase_order_status";
  occurred_at: string;
  title: string;
  subtitle: string;
  quantity: string | null;
};

export type ApiMovementsOverTimePoint = {
  date: string;
  units_in: string;
  units_out: string;
};

export type ApiMovementsOverTime = {
  days: number;
  items: ApiMovementsOverTimePoint[];
};

export type ApiTopSeller = {
  product_id: string;
  product_name: string;
  units_sold: string;
};

export type ApiTopSellers = {
  days: number;
  limit: number;
  items: ApiTopSeller[];
};

export type ApiAccountsSummary = {
  stock_value: string;
  unvalued_product_count: number;
  open_po_value: string;
  payables_due: string;
};

export type ApiAccountsBySupplierRow = {
  supplier_id: string;
  supplier_name: string;
  status: string;
  total: string;
  purchase_order_count: number;
};

export type ApiSettingsLocation = {
  id: string;
  name: string;
  address: string | null;
  is_default: boolean;
  is_active: boolean;
};

export type ApiTeamUser = {
  id: string;
  email: string;
  full_name: string;
  role: "owner" | "staff";
  is_active: boolean;
};

export type ApiAutonomyRules = {
  auto_approve_below_amount: string | null;
};

export type ApiDemoSeedResult = {
  products_created: number;
  suppliers_created: number;
  categories_created: number;
  stock_movements_created: number;
  sale_movements_created: number;
  purchase_orders_created: number;
  message: string;
};
