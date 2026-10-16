import test from "node:test";
import assert from "node:assert/strict";
import {
  handleModalKeyNavigation,
  getFocusableElements,
} from "../../src/lib/modalAccessibility.ts";

test("handleModalKeyNavigation: ignora teclas se isOpen for false", () => {
  let closed = false;
  let submitted = false;

  const handled = handleModalKeyNavigation(
    { key: "Escape" },
    {
      isOpen: false,
      onClose: () => {
        closed = true;
      },
      onSubmit: () => {
        submitted = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  assert.equal(handled, false);
  assert.equal(closed, false);
  assert.equal(submitted, false);
});

test("handleModalKeyNavigation: Escape fecha confirmação de exclusão prioritariamente", () => {
  let closed = false;
  let cancelledConfirm = false;
  let defaultPrevented = false;

  const handled = handleModalKeyNavigation(
    { key: "Escape" },
    {
      isOpen: true,
      showConfirmDialog: true,
      onClose: () => {
        closed = true;
      },
      onCancelConfirm: () => {
        cancelledConfirm = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {
        defaultPrevented = true;
      },
      stopPropagation: () => {},
    }
  );

  assert.equal(handled, true);
  assert.equal(cancelledConfirm, true);
  assert.equal(closed, false);
  assert.equal(defaultPrevented, true);
});

test("handleModalKeyNavigation: Escape fecha modal quando não há confirmação e não está ocupado", () => {
  let closed = false;
  let defaultPrevented = false;

  const handled = handleModalKeyNavigation(
    { key: "Escape" },
    {
      isOpen: true,
      showConfirmDialog: false,
      isBusy: false,
      onClose: () => {
        closed = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {
        defaultPrevented = true;
      },
      stopPropagation: () => {},
    }
  );

  assert.equal(handled, true);
  assert.equal(closed, true);
  assert.equal(defaultPrevented, true);
});

test("handleModalKeyNavigation: Escape não fecha se modal estiver ocupado (salvando/excluindo)", () => {
  let closed = false;

  const handled = handleModalKeyNavigation(
    { key: "Escape" },
    {
      isOpen: true,
      showConfirmDialog: false,
      isBusy: true,
      onClose: () => {
        closed = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  assert.equal(handled, false);
  assert.equal(closed, false);
});

test("handleModalKeyNavigation: Ctrl+Enter e Cmd+Enter disparam submit rápido se apto", () => {
  let submittedCtrl = false;
  let submittedMeta = false;

  const handledCtrl = handleModalKeyNavigation(
    { key: "Enter", ctrlKey: true },
    {
      isOpen: true,
      canSubmit: true,
      isBusy: false,
      onClose: () => {},
      onSubmit: () => {
        submittedCtrl = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  const handledMeta = handleModalKeyNavigation(
    { key: "Enter", metaKey: true },
    {
      isOpen: true,
      canSubmit: true,
      isBusy: false,
      onClose: () => {},
      onSubmit: () => {
        submittedMeta = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  assert.equal(handledCtrl, true);
  assert.equal(submittedCtrl, true);
  assert.equal(handledMeta, true);
  assert.equal(submittedMeta, true);
});

test("handleModalKeyNavigation: Ctrl+Enter não dispara submit se canSubmit for falso ou se showConfirmDialog for ativo", () => {
  let submitted = false;

  const handledIncomplete = handleModalKeyNavigation(
    { key: "Enter", ctrlKey: true },
    {
      isOpen: true,
      canSubmit: false,
      isBusy: false,
      onClose: () => {},
      onSubmit: () => {
        submitted = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  const handledWithConfirm = handleModalKeyNavigation(
    { key: "Enter", ctrlKey: true },
    {
      isOpen: true,
      canSubmit: true,
      showConfirmDialog: true,
      isBusy: false,
      onClose: () => {},
      onSubmit: () => {
        submitted = true;
      },
      getFocusables: () => [],
      activeElement: null,
      preventDefault: () => {},
      stopPropagation: () => {},
    }
  );

  assert.equal(handledIncomplete, false);
  assert.equal(handledWithConfirm, false);
  assert.equal(submitted, false);
});

test("handleModalKeyNavigation: Trap-Focus cicla entre primeiro e último elemento", () => {
  const el1 = { id: "btn-close", focusCalled: 0, focus() { this.focusCalled++; } };
  const el2 = { id: "input-search", focusCalled: 0, focus() { this.focusCalled++; } };
  const el3 = { id: "btn-save", focusCalled: 0, focus() { this.focusCalled++; } };

  const focusables = [el1, el2, el3];

  // Tab no último elemento deve focar o primeiro
  let prevented = false;
  const handledTabLast = handleModalKeyNavigation(
    { key: "Tab", shiftKey: false },
    {
      isOpen: true,
      onClose: () => {},
      getFocusables: () => focusables,
      activeElement: el3,
      preventDefault: () => {
        prevented = true;
      },
      stopPropagation: () => {},
    }
  );

  assert.equal(handledTabLast, true);
  assert.equal(prevented, true);
  assert.equal(el1.focusCalled, 1);

  // Shift+Tab no primeiro elemento deve focar o último
  prevented = false;
  const handledShiftTabFirst = handleModalKeyNavigation(
    { key: "Tab", shiftKey: true },
    {
      isOpen: true,
      onClose: () => {},
      getFocusables: () => focusables,
      activeElement: el1,
      preventDefault: () => {
        prevented = true;
      },
      stopPropagation: () => {},
    }
  );

  assert.equal(handledShiftTabFirst, true);
  assert.equal(prevented, true);
  assert.equal(el3.focusCalled, 1);

  // Se foco estiver fora dos focáveis (ex: container do modal)
  prevented = false;
  const handledOutsideTab = handleModalKeyNavigation(
    { key: "Tab", shiftKey: false },
    {
      isOpen: true,
      onClose: () => {},
      getFocusables: () => focusables,
      activeElement: null,
      preventDefault: () => {
        prevented = true;
      },
      stopPropagation: () => {},
    }
  );

  assert.equal(handledOutsideTab, true);
  assert.equal(el1.focusCalled, 2);
});

test("getFocusableElements: filtra elementos desabilitados e ocultos", () => {
  const fakeContainer = {
    querySelectorAll: () => {
      // Mock simples retornando 2 elementos
      return [
        {
          id: "1",
          offsetParent: {},
          getClientRects: () => [{ width: 10 }],
          getAttribute: () => null,
          style: { display: "block" },
        },
        {
          id: "2",
          offsetParent: null,
          getClientRects: () => [],
          getAttribute: () => "true", // aria-hidden
          style: { display: "none" },
        },
      ];
    },
  };

  const visible = getFocusableElements(fakeContainer);
  assert.equal(visible.length, 1);
  assert.equal(visible[0].id, "1");

  // Container nulo retorna array vazio defensivamente
  assert.deepEqual(getFocusableElements(null), []);
});
