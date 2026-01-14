export type InventoryRisk = "Low" | "Medium" | "High";

export interface InventoryItemType {
  id: string;
  name: string;
  stock: number;
  expiryDays: number;
  risk: InventoryRisk;
}

export interface DecisionType {
  id: string;
  product: string;
  action: string;
  reason: string;
}
