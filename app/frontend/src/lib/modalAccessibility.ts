/**
 * Utilitários de Acessibilidade e Trap-Focus para Modais (WCAG 2.1 AA)
 * MedQuest - Ergonomia Frontend
 */

export interface ModalKeyNavigationOptions {
  isOpen: boolean;
  showConfirmDialog?: boolean;
  isBusy?: boolean;
  canSubmit?: boolean;
  onClose: () => void;
  onCancelConfirm?: () => void;
  onSubmit?: () => void;
  getFocusables: () => HTMLElement[];
  activeElement: Element | null;
  preventDefault: () => void;
  stopPropagation: () => void;
}

/**
 * Retorna todos os elementos focáveis visíveis e habilitados dentro de um container.
 */
export function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];

  const selector = [
    'button:not([disabled])',
    '[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(', ');

  const elements = Array.from(container.querySelectorAll<HTMLElement>(selector));

  return elements.filter((el) => {
    // Verifica se o elemento está visível no DOM
    const isVisible =
      el.offsetParent !== null ||
      el.getClientRects().length > 0 ||
      el.style.display !== 'none';
    const isHidden = el.getAttribute('aria-hidden') === 'true';
    return isVisible && !isHidden;
  });
}

/**
 * Intercepta e processa eventos de teclado para navegação de modal (Escape, Ctrl+Enter, Tab/Shift+Tab).
 * Retorna true se o evento foi tratado.
 */
export function handleModalKeyNavigation(
  event: { key: string; shiftKey?: boolean; ctrlKey?: boolean; metaKey?: boolean },
  options: ModalKeyNavigationOptions
): boolean {
  if (!options.isOpen) return false;

  // 1. Tecla Escape: fecha diálogo de confirmação se presente, senão fecha o modal (se não estiver ocupado)
  if (event.key === 'Escape') {
    options.preventDefault();
    options.stopPropagation();

    if (options.showConfirmDialog && options.onCancelConfirm) {
      options.onCancelConfirm();
      return true;
    }

    if (!options.isBusy) {
      options.onClose();
      return true;
    }

    return false;
  }

  // 2. Tecla de Confirmação Rápida: Ctrl+Enter ou Cmd+Enter
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    if (options.canSubmit && !options.isBusy && !options.showConfirmDialog && options.onSubmit) {
      options.preventDefault();
      options.stopPropagation();
      options.onSubmit();
      return true;
    }
    return false;
  }

  // 3. Tecla Tab / Shift+Tab: Ciclo fechado de foco (Trap-Focus)
  if (event.key === 'Tab') {
    const focusables = options.getFocusables();
    if (focusables.length === 0) {
      options.preventDefault();
      return true;
    }

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = options.activeElement as HTMLElement | null;

    if (event.shiftKey) {
      // Shift + Tab: se estiver no primeiro ou fora do modal, envia para o último
      if (active === first || !active || !focusables.includes(active)) {
        options.preventDefault();
        last.focus();
        return true;
      }
    } else {
      // Tab: se estiver no último ou fora do modal, envia para o primeiro
      if (active === last || !active || !focusables.includes(active)) {
        options.preventDefault();
        first.focus();
        return true;
      }
    }
  }

  return false;
}
