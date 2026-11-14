export interface NavItem {
  href: string;
  label: string;
  bottomLabel?: string;
  icon: string;
}

/** Fonte única da verdade para os itens de navegação principal. */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Dashboard", bottomLabel: "Cockpit", icon: "dashboard" },
  { href: "/buscar", label: "Busca Clínica", icon: "search" },
  { href: "/estudar", label: "Estudar", icon: "menu_book" },
  { href: "/osce", label: "OSCE (2ª Fase)", bottomLabel: "OSCE", icon: "stethoscope" },
  { href: "/simulado", label: "Simulados", icon: "description" },
  { href: "/cobertura", label: "Cobertura", icon: "my_location" },
  { href: "/analise", label: "Análise", icon: "analytics" },
  { href: "/planner", label: "Planner", icon: "calendar_month" },
];

const PRIMARY_BOTTOM_HREFS = new Set(["/", "/estudar", "/simulado", "/osce"]);

export const PRIMARY_BOTTOM_NAV_ITEMS: readonly NavItem[] = [
  NAV_ITEMS[0], // Cockpit
  NAV_ITEMS[2], // Estudar
  NAV_ITEMS[4], // Simulados
  NAV_ITEMS[3], // OSCE
];

export const MORE_BOTTOM_NAV_ITEMS: readonly NavItem[] = NAV_ITEMS.filter(
  (item) => !PRIMARY_BOTTOM_HREFS.has(item.href)
);
