import {
  Castle, Compass, Droplets, Flower2, Landmark, Mountain, Palette, ShoppingBag, Trees, UtensilsCrossed, Users, Waves,
  type LucideIcon,
} from "lucide-react";
import type { Category } from "@/api/types";

export const CATEGORY: Record<Category, { label: string; icon: LucideIcon; from: string; to: string; line: string }> = {
  heritage: { label: "Heritage", icon: Castle, from: "#f6e3c9", to: "#e9c79b", line: "#b9772f" },
  religious: { label: "Spiritual", icon: Landmark, from: "#dcebe6", to: "#bcd8d0", line: "#2d7a70" },
  museums: { label: "Museums", icon: Palette, from: "#e6e2f1", to: "#cfc8e4", line: "#6c5fa3" },
  nature: { label: "Nature", icon: Trees, from: "#dcebd5", to: "#bcd9b0", line: "#4c8a3c" },
  mountains: { label: "Mountains", icon: Mountain, from: "#d9e6f0", to: "#b5cce0", line: "#3f6f98" },
  lakes: { label: "Lakes", icon: Droplets, from: "#d3eeef", to: "#a9dcdf", line: "#1f8a88" },
  beaches: { label: "Beaches", icon: Waves, from: "#d6ecf4", to: "#f2e6c8", line: "#2e8aa8" },
  parks: { label: "Parks", icon: Flower2, from: "#e3efd3", to: "#cfe3b2", line: "#6a9a2e" },
  food: { label: "Food", icon: UtensilsCrossed, from: "#fbe3d2", to: "#f4c4a3", line: "#c5642b" },
  shopping: { label: "Markets", icon: ShoppingBag, from: "#f7dde4", to: "#eebccb", line: "#b04a6c" },
  adventure: { label: "Adventure", icon: Compass, from: "#fde4cc", to: "#f7c394", line: "#d9822f" },
  family: { label: "Family", icon: Users, from: "#f9ecc4", to: "#f2d98d", line: "#a98516" },
};
export const categoryOf = (c: string) => CATEGORY[c as Category] ?? CATEGORY.heritage;
