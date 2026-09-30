import type {
  BusinessProfile,
  Location,
  Product,
  PurchaseOrder,
  StockLevel,
  StockMovement,
  Supplier,
  TeamUser,
} from "@/types";

export const MOCK_BUSINESS: BusinessProfile = {
  name: "Harbor Market",
  currency: "USD",
};

export const MOCK_CURRENT_USER = {
  id: "user-owner-1",
  name: "Alex Rivera",
  email: "alex@harbormarket.example",
};

export const MOCK_LOCATIONS: Location[] = [
  { id: "loc-1", name: "Front store", isDefault: true },
  { id: "loc-2", name: "Back stockroom", isDefault: false },
];

export const MOCK_SUPPLIERS: Supplier[] = [
  {
    id: "sup-1",
    name: "Green Valley Produce",
    email: "orders@greenvalley.example",
    phone: "(555) 410-2200",
    leadTimeDays: 2,
    isActive: true,
  },
  {
    id: "sup-2",
    name: "Summit Beverage Co.",
    email: "wholesale@summitbev.example",
    phone: "(555) 410-3300",
    leadTimeDays: 3,
    isActive: true,
  },
  {
    id: "sup-3",
    name: "Coastal Dairy",
    email: "sales@coastaldairy.example",
    phone: "(555) 410-4400",
    leadTimeDays: 1,
    isActive: true,
  },
  {
    id: "sup-4",
    name: "Metro Dry Goods",
    email: "buyers@metrodry.example",
    phone: "(555) 410-5500",
    leadTimeDays: 5,
    isActive: true,
  },
  {
    id: "sup-5",
    name: "Oak Street Bakery Supply",
    email: "hello@oakstreetbakery.example",
    phone: "(555) 410-6600",
    leadTimeDays: 2,
    isActive: true,
  },
];

const supplierNames = Object.fromEntries(
  MOCK_SUPPLIERS.map((supplier) => [supplier.id, supplier.name]),
);

function mockProduct(
  seed: Omit<
    Product,
    "categoryId" | "categoryName" | "preferredSupplierName" | "isActive"
  > & { categoryName: string },
): Product {
  return {
    ...seed,
    categoryId: `cat-${seed.categoryName.toLowerCase().replace(/\s+/g, "-")}`,
    preferredSupplierName: seed.preferredSupplierId
      ? (supplierNames[seed.preferredSupplierId] ?? null)
      : null,
    isActive: true,
  };
}

export const MOCK_PRODUCTS: Product[] = [
  mockProduct({ id: "p-01", sku: "GV-001", name: "Organic Gala Apples", categoryName: "Produce", unit: "lb", cost: 1.25, price: 2.49, reorderPoint: 40, safetyStock: 20, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-02", sku: "GV-002", name: "Baby Spinach", categoryName: "Produce", unit: "pack", cost: 2.10, price: 3.99, reorderPoint: 24, safetyStock: 12, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-03", sku: "GV-003", name: "Roma Tomatoes", categoryName: "Produce", unit: "lb", cost: 0.95, price: 1.89, reorderPoint: 35, safetyStock: 15, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-04", sku: "GV-004", name: "Yellow Onions", categoryName: "Produce", unit: "lb", cost: 0.55, price: 1.29, reorderPoint: 50, safetyStock: 25, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-05", sku: "GV-005", name: "Avocados", categoryName: "Produce", unit: "each", cost: 0.85, price: 1.75, reorderPoint: 30, safetyStock: 15, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-06", sku: "CD-101", name: "Whole Milk 1 gal", categoryName: "Dairy", unit: "each", cost: 2.40, price: 4.29, reorderPoint: 20, safetyStock: 10, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-07", sku: "CD-102", name: "Sharp Cheddar Block", categoryName: "Dairy", unit: "lb", cost: 3.80, price: 6.49, reorderPoint: 15, safetyStock: 8, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-08", sku: "CD-103", name: "Greek Yogurt 32oz", categoryName: "Dairy", unit: "each", cost: 3.25, price: 5.99, reorderPoint: 18, safetyStock: 9, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-09", sku: "CD-104", name: "Unsalted Butter", categoryName: "Dairy", unit: "lb", cost: 2.95, price: 5.49, reorderPoint: 12, safetyStock: 6, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-10", sku: "SB-201", name: "Sparkling Water 12pk", categoryName: "Beverages", unit: "case", cost: 4.50, price: 8.99, reorderPoint: 10, safetyStock: 5, preferredSupplierId: "sup-2" }),
  mockProduct({ id: "p-11", sku: "SB-202", name: "Cold Brew Coffee 64oz", categoryName: "Beverages", unit: "each", cost: 5.20, price: 9.99, reorderPoint: 8, safetyStock: 4, preferredSupplierId: "sup-2" }),
  mockProduct({ id: "p-12", sku: "SB-203", name: "Orange Juice 59oz", categoryName: "Beverages", unit: "each", cost: 2.75, price: 4.99, reorderPoint: 14, safetyStock: 7, preferredSupplierId: "sup-2" }),
  mockProduct({ id: "p-13", sku: "SB-204", name: "Iced Tea Gallon", categoryName: "Beverages", unit: "each", cost: 1.90, price: 3.49, reorderPoint: 12, safetyStock: 6, preferredSupplierId: "sup-2" }),
  mockProduct({ id: "p-14", sku: "MD-301", name: "Paper Towels 6-roll", categoryName: "Household", unit: "pack", cost: 6.80, price: 11.99, reorderPoint: 8, safetyStock: 4, preferredSupplierId: "sup-4" }),
  mockProduct({ id: "p-15", sku: "MD-302", name: "Dish Soap 24oz", categoryName: "Household", unit: "each", cost: 2.10, price: 3.99, reorderPoint: 10, safetyStock: 5, preferredSupplierId: "sup-4" }),
  mockProduct({ id: "p-16", sku: "MD-303", name: "Laundry Detergent 100oz", categoryName: "Household", unit: "each", cost: 8.50, price: 14.99, reorderPoint: 6, safetyStock: 3, preferredSupplierId: "sup-4" }),
  mockProduct({ id: "p-17", sku: "MD-304", name: "Trash Bags 45ct", categoryName: "Household", unit: "pack", cost: 5.40, price: 9.49, reorderPoint: 8, safetyStock: 4, preferredSupplierId: "sup-4" }),
  mockProduct({ id: "p-18", sku: "OB-401", name: "Sourdough Loaf", categoryName: "Bakery", unit: "each", cost: 2.20, price: 4.50, reorderPoint: 16, safetyStock: 8, preferredSupplierId: "sup-5" }),
  mockProduct({ id: "p-19", sku: "OB-402", name: "Blueberry Muffins 4pk", categoryName: "Bakery", unit: "pack", cost: 3.10, price: 5.99, reorderPoint: 12, safetyStock: 6, preferredSupplierId: "sup-5" }),
  mockProduct({ id: "p-20", sku: "OB-403", name: "Chocolate Chip Cookies 12ct", categoryName: "Bakery", unit: "pack", cost: 2.85, price: 5.49, reorderPoint: 10, safetyStock: 5, preferredSupplierId: "sup-5" }),
  mockProduct({ id: "p-21", sku: "GV-006", name: "Bananas", categoryName: "Produce", unit: "lb", cost: 0.45, price: 0.79, reorderPoint: 60, safetyStock: 30, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-22", sku: "GV-007", name: "Red Bell Peppers", categoryName: "Produce", unit: "lb", cost: 1.60, price: 2.99, reorderPoint: 20, safetyStock: 10, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-23", sku: "GV-008", name: "Cilantro Bunch", categoryName: "Produce", unit: "each", cost: 0.65, price: 1.29, reorderPoint: 15, safetyStock: 8, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-24", sku: "CD-105", name: "Large Eggs 18ct", categoryName: "Dairy", unit: "each", cost: 3.60, price: 6.29, reorderPoint: 16, safetyStock: 8, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-25", sku: "SB-205", name: "Kombucha 6pk", categoryName: "Beverages", unit: "pack", cost: 7.80, price: 13.99, reorderPoint: 6, safetyStock: 3, preferredSupplierId: "sup-2" }),
  mockProduct({ id: "p-26", sku: "MD-305", name: "Aluminum Foil 200ft", categoryName: "Household", unit: "each", cost: 4.20, price: 7.49, reorderPoint: 8, safetyStock: 4, preferredSupplierId: "sup-4" }),
  mockProduct({ id: "p-27", sku: "OB-404", name: "Croissants 6pk", categoryName: "Bakery", unit: "pack", cost: 3.40, price: 6.49, reorderPoint: 10, safetyStock: 5, preferredSupplierId: "sup-5" }),
  mockProduct({ id: "p-28", sku: "GV-009", name: "Organic Carrots 2lb", categoryName: "Produce", unit: "pack", cost: 1.40, price: 2.69, reorderPoint: 18, safetyStock: 9, preferredSupplierId: "sup-1" }),
  mockProduct({ id: "p-29", sku: "CD-106", name: "Mozzarella Shredded 16oz", categoryName: "Dairy", unit: "each", cost: 3.15, price: 5.49, reorderPoint: 12, safetyStock: 6, preferredSupplierId: "sup-3" }),
  mockProduct({ id: "p-30", sku: "SB-206", name: "Sports Drink 12pk", categoryName: "Beverages", unit: "case", cost: 6.90, price: 12.99, reorderPoint: 8, safetyStock: 4, preferredSupplierId: "sup-2" }),
];

export const MOCK_STOCK_LEVELS: StockLevel[] = [
  { productId: "p-01", locationId: "loc-1", onHand: 52 },
  { productId: "p-01", locationId: "loc-2", onHand: 18 },
  { productId: "p-02", locationId: "loc-1", onHand: 8 },
  { productId: "p-02", locationId: "loc-2", onHand: 6 },
  { productId: "p-03", locationId: "loc-1", onHand: 28 },
  { productId: "p-04", locationId: "loc-1", onHand: 62 },
  { productId: "p-05", locationId: "loc-1", onHand: 0 },
  { productId: "p-06", locationId: "loc-1", onHand: 24 },
  { productId: "p-07", locationId: "loc-1", onHand: 11 },
  { productId: "p-08", locationId: "loc-1", onHand: 14 },
  { productId: "p-09", locationId: "loc-1", onHand: 9 },
  { productId: "p-10", locationId: "loc-2", onHand: 7 },
  { productId: "p-11", locationId: "loc-1", onHand: 5 },
  { productId: "p-12", locationId: "loc-1", onHand: 16 },
  { productId: "p-13", locationId: "loc-1", onHand: 10 },
  { productId: "p-14", locationId: "loc-2", onHand: 4 },
  { productId: "p-15", locationId: "loc-2", onHand: 12 },
  { productId: "p-16", locationId: "loc-2", onHand: 3 },
  { productId: "p-17", locationId: "loc-2", onHand: 9 },
  { productId: "p-18", locationId: "loc-1", onHand: 20 },
  { productId: "p-19", locationId: "loc-1", onHand: 6 },
  { productId: "p-20", locationId: "loc-1", onHand: 8 },
  { productId: "p-21", locationId: "loc-1", onHand: 45 },
  { productId: "p-22", locationId: "loc-1", onHand: 12 },
  { productId: "p-23", locationId: "loc-1", onHand: 0 },
  { productId: "p-24", locationId: "loc-1", onHand: 18 },
  { productId: "p-25", locationId: "loc-2", onHand: 4 },
  { productId: "p-26", locationId: "loc-2", onHand: 7 },
  { productId: "p-27", locationId: "loc-1", onHand: 5 },
  { productId: "p-28", locationId: "loc-1", onHand: 22 },
  { productId: "p-29", locationId: "loc-1", onHand: 10 },
  { productId: "p-30", locationId: "loc-2", onHand: 6 },
];

function movement(
  id: string,
  date: string,
  productId: string,
  locationId: string,
  type: StockMovement["type"],
  quantity: number,
  note: string,
): StockMovement {
  return {
    id,
    date,
    productId,
    locationId,
    type,
    quantity,
    userId: "user-owner-1",
    note,
  };
}

export const MOCK_MOVEMENTS: StockMovement[] = [
  movement("m-01", "2026-09-28T09:15:00", "p-01", "loc-1", "receipt", 40, "Morning produce delivery"),
  movement("m-02", "2026-09-28T10:30:00", "p-06", "loc-1", "sale", -3, "Register 1 checkout"),
  movement("m-03", "2026-09-28T11:05:00", "p-18", "loc-1", "sale", -4, "Lunch rush bakery sales"),
  movement("m-04", "2026-09-28T12:20:00", "p-02", "loc-1", "sale", -6, "Salad bar restock pull"),
  movement("m-05", "2026-09-28T14:00:00", "p-10", "loc-2", "receipt", 12, "Beverage case delivery"),
  movement("m-06", "2026-09-28T15:45:00", "p-05", "loc-1", "sale", -8, "Weekend promo"),
  movement("m-07", "2026-09-27T08:30:00", "p-14", "loc-2", "receipt", 6, "Household restock"),
  movement("m-08", "2026-09-27T09:10:00", "p-11", "loc-1", "sale", -2, "Cold brew demand"),
  movement("m-09", "2026-09-27T10:00:00", "p-16", "loc-2", "adjustment", -1, "Damaged jug during unload"),
  movement("m-10", "2026-09-27T11:30:00", "p-21", "loc-1", "receipt", 50, "Banana shipment"),
  movement("m-11", "2026-09-27T13:15:00", "p-07", "loc-1", "sale", -2, "Deli counter"),
  movement("m-12", "2026-09-27T14:40:00", "p-19", "loc-1", "sale", -3, "Cafe pairing"),
  movement("m-13", "2026-09-26T08:00:00", "p-03", "loc-1", "receipt", 30, "Tomato delivery"),
  movement("m-14", "2026-09-26T09:30:00", "p-12", "loc-1", "sale", -5, "Breakfast rush"),
  movement("m-15", "2026-09-26T10:45:00", "p-23", "loc-1", "adjustment", -4, "Wilted cilantro write-off"),
  movement("m-16", "2026-09-26T12:00:00", "p-08", "loc-1", "sale", -3, "Yogurt promo"),
  movement("m-17", "2026-09-26T14:20:00", "p-25", "loc-2", "receipt", 8, "Kombucha restock"),
  movement("m-18", "2026-09-25T08:15:00", "p-04", "loc-1", "receipt", 60, "Onion bulk delivery"),
  movement("m-19", "2026-09-25T09:45:00", "p-20", "loc-1", "sale", -2, "Cookie display"),
  movement("m-20", "2026-09-25T11:00:00", "p-09", "loc-1", "sale", -1, "Baking supplies"),
  movement("m-21", "2026-09-25T13:30:00", "p-15", "loc-2", "receipt", 10, "Cleaning supplies"),
  movement("m-22", "2026-09-25T15:00:00", "p-27", "loc-1", "sale", -4, "Pastry case"),
  movement("m-23", "2026-09-24T08:45:00", "p-24", "loc-1", "receipt", 20, "Egg delivery"),
  movement("m-24", "2026-09-24T10:10:00", "p-13", "loc-1", "sale", -3, "Tea gallon refill"),
  movement("m-25", "2026-09-24T11:55:00", "p-05", "loc-1", "sale", -6, "Avocado toast bar"),
  movement("m-26", "2026-09-24T13:20:00", "p-17", "loc-2", "receipt", 8, "Trash bag restock"),
  movement("m-27", "2026-09-24T14:50:00", "p-28", "loc-1", "sale", -2, "Soup kit bundle"),
  movement("m-28", "2026-09-23T09:00:00", "p-29", "loc-1", "receipt", 14, "Cheese delivery"),
  movement("m-29", "2026-09-23T10:30:00", "p-30", "loc-2", "receipt", 10, "Sports drink case"),
  movement("m-30", "2026-09-23T12:15:00", "p-01", "loc-1", "sale", -5, "Apple sampling"),
  movement("m-31", "2026-09-23T13:40:00", "p-06", "loc-1", "sale", -4, "Milk restock pull"),
  movement("m-32", "2026-09-22T08:20:00", "p-22", "loc-1", "receipt", 18, "Pepper delivery"),
  movement("m-33", "2026-09-22T09:50:00", "p-02", "loc-1", "receipt", 24, "Spinach restock"),
  movement("m-34", "2026-09-22T11:10:00", "p-18", "loc-1", "sale", -6, "Sandwich prep"),
  movement("m-35", "2026-09-22T12:30:00", "p-26", "loc-2", "receipt", 6, "Foil restock"),
  movement("m-36", "2026-09-22T14:00:00", "p-07", "loc-1", "sale", -3, "Cheese board"),
  movement("m-37", "2026-09-21T08:00:00", "p-05", "loc-1", "adjustment", -2, "Overripe avocados"),
  movement("m-38", "2026-09-21T09:30:00", "p-11", "loc-1", "receipt", 8, "Coffee delivery"),
  movement("m-39", "2026-09-21T11:00:00", "p-21", "loc-1", "sale", -12, "Smoothie bar"),
  movement("m-40", "2026-09-21T13:45:00", "p-14", "loc-2", "sale", -2, "Janitorial pull"),
];

export const MOCK_PURCHASE_ORDERS: PurchaseOrder[] = [
  {
    id: "po-1",
    poNumber: "PO-2026-001",
    supplierId: "sup-1",
    status: "sent",
    expectedDate: "2026-10-02",
    lineItems: [
      { id: "pol-1", productId: "p-02", quantity: 30, unitCost: 2.10 },
      { id: "pol-2", productId: "p-05", quantity: 40, unitCost: 0.85 },
      { id: "pol-3", productId: "p-23", quantity: 20, unitCost: 0.65 },
    ],
  },
  {
    id: "po-2",
    poNumber: "PO-2026-002",
    supplierId: "sup-3",
    status: "approved",
    expectedDate: "2026-10-01",
    lineItems: [
      { id: "pol-4", productId: "p-06", quantity: 24, unitCost: 2.40 },
      { id: "pol-5", productId: "p-09", quantity: 12, unitCost: 2.95 },
    ],
  },
  {
    id: "po-3",
    poNumber: "PO-2026-003",
    supplierId: "sup-2",
    status: "draft",
    expectedDate: "2026-10-05",
    lineItems: [
      { id: "pol-6", productId: "p-10", quantity: 8, unitCost: 4.50 },
      { id: "pol-7", productId: "p-25", quantity: 6, unitCost: 7.80 },
    ],
  },
  {
    id: "po-4",
    poNumber: "PO-2026-004",
    supplierId: "sup-4",
    status: "received",
    expectedDate: "2026-09-25",
    lineItems: [
      { id: "pol-8", productId: "p-14", quantity: 10, unitCost: 6.80 },
      { id: "pol-9", productId: "p-16", quantity: 6, unitCost: 8.50 },
    ],
  },
  {
    id: "po-5",
    poNumber: "PO-2026-005",
    supplierId: "sup-5",
    status: "sent",
    expectedDate: "2026-10-03",
    lineItems: [
      { id: "pol-10", productId: "p-18", quantity: 24, unitCost: 2.20 },
      { id: "pol-11", productId: "p-27", quantity: 12, unitCost: 3.40 },
    ],
  },
  {
    id: "po-6",
    poNumber: "PO-2026-006",
    supplierId: "sup-1",
    status: "cancelled",
    expectedDate: "2026-09-20",
    lineItems: [
      { id: "pol-12", productId: "p-01", quantity: 50, unitCost: 1.25 },
    ],
  },
  {
    id: "po-7",
    poNumber: "PO-2026-007",
    supplierId: "sup-3",
    status: "draft",
    expectedDate: "2026-10-06",
    lineItems: [
      { id: "pol-13", productId: "p-24", quantity: 18, unitCost: 3.60 },
      { id: "pol-14", productId: "p-29", quantity: 15, unitCost: 3.15 },
    ],
  },
  {
    id: "po-8",
    poNumber: "PO-2026-008",
    supplierId: "sup-2",
    status: "approved",
    expectedDate: "2026-10-04",
    lineItems: [
      { id: "pol-15", productId: "p-30", quantity: 10, unitCost: 6.90 },
    ],
  },
];

export const MOCK_TEAM_USERS: TeamUser[] = [
  {
    id: "user-owner-1",
    name: "Alex Rivera",
    email: "alex@harbormarket.example",
    role: "owner",
    active: true,
  },
  {
    id: "user-staff-1",
    name: "Jordan Lee",
    email: "jordan@harbormarket.example",
    role: "staff",
    active: true,
  },
  {
    id: "user-staff-2",
    name: "Sam Patel",
    email: "sam@harbormarket.example",
    role: "staff",
    active: true,
  },
];

export const SAMPLE_CSV_CONTENT = `sku,name,category,location,quantity,unit,reorder_point,supplier,unit_cost,lead_time_days
NEW-001,Sample Item,Produce,Front store,10,each,5,Green Valley Produce,1.50,2`;
