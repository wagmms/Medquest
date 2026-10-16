import test from "node:test";
import assert from "node:assert/strict";

// Replica a lógica pura de filtragem e normalização de subtemas de QuizFilters
function normalizeSelectedSubtemas(subtemaProp) {
  if (Array.isArray(subtemaProp)) return subtemaProp;
  if (typeof subtemaProp === "string" && subtemaProp.trim().length > 0) return [subtemaProp];
  return [];
}

function filterSearchSubtemas(subtemas, query, selectedSet, limit = 50) {
  const q = (query || "").trim().toLowerCase();
  if (!q || !subtemas || !Array.isArray(subtemas)) return [];
  return subtemas
    .filter((s) => !selectedSet.has(s.subtema) && s.subtema.toLowerCase().includes(q))
    .slice(0, limit);
}

function removeSubtema(currentFilters, subtemaToRemove) {
  const current = Array.isArray(currentFilters.subtema)
    ? currentFilters.subtema
    : currentFilters.subtema ? [currentFilters.subtema] : [];
  const next = current.filter((x) => x !== subtemaToRemove);
  const updated = { ...currentFilters };
  if (next.length > 0) {
    updated.subtema = next;
  } else {
    delete updated.subtema;
  }
  return updated;
}

function addSubtema(currentFilters, subtemaToAdd) {
  const current = Array.isArray(currentFilters.subtema)
    ? [...currentFilters.subtema]
    : currentFilters.subtema ? [currentFilters.subtema] : [];
  if (!current.includes(subtemaToAdd)) {
    current.push(subtemaToAdd);
  }
  return { ...currentFilters, subtema: current };
}

test("normalizeSelectedSubtemas: normaliza formatos variados para array estável", () => {
  assert.deepEqual(normalizeSelectedSubtemas(undefined), []);
  assert.deepEqual(normalizeSelectedSubtemas(null), []);
  assert.deepEqual(normalizeSelectedSubtemas(""), []);
  assert.deepEqual(normalizeSelectedSubtemas("Cardiologia"), ["Cardiologia"]);
  assert.deepEqual(normalizeSelectedSubtemas(["Pediatria", "Trauma"]), ["Pediatria", "Trauma"]);
});

test("filterSearchSubtemas: filtra com busca case-insensitive e exclui selecionados via Set em O(1)", () => {
  const subtemasMock = [
    { subtema: "Cardiologia Básica", n: 120 },
    { subtema: "Cardiopatias Congênitas", n: 45 },
    { subtema: "Trauma Torácico", n: 80 },
    { subtema: "Cirurgia Pediátrica", n: 60 },
  ];

  const selectedSet = new Set(["Cardiologia Básica"]);

  // Busca por 'cardio' deve trazer apenas 'Cardiopatias Congênitas' (pois Cardiologia Básica já está selecionado)
  const results = filterSearchSubtemas(subtemasMock, "cardio", selectedSet);
  assert.equal(results.length, 1);
  assert.equal(results[0].subtema, "Cardiopatias Congênitas");
  assert.equal(results[0].n, 45);

  // Busca vazia retorna array vazio imediatamente sem iterar
  assert.deepEqual(filterSearchSubtemas(subtemasMock, "   ", selectedSet), []);

  // Lista nula retorna array vazio defensivamente
  assert.deepEqual(filterSearchSubtemas(null, "cardio", selectedSet), []);
});

test("filterSearchSubtemas: respeita limite defensivo de 50 itens", () => {
  const largeSubtemas = Array.from({ length: 100 }, (_, i) => ({
    subtema: `Subtema Teste ${i}`,
    n: i + 1,
  }));

  const results = filterSearchSubtemas(largeSubtemas, "subtema", new Set());
  assert.equal(results.length, 50);
});

test("removeSubtema: remove subtema selecionado e elimina chave quando vazio", () => {
  const initial = { area: "Clínica Médica", subtema: ["Cardiologia", "Pneumologia"] };
  const updated1 = removeSubtema(initial, "Cardiologia");
  assert.deepEqual(updated1.subtema, ["Pneumologia"]);

  const updated2 = removeSubtema(updated1, "Pneumologia");
  assert.equal(updated2.subtema, undefined);
  assert.equal("subtema" in updated2, false);
});

test("addSubtema: inclui novo subtema sem duplicatas e preserva outros filtros", () => {
  const initial = { area: "Cirurgia", subtema: ["Trauma"] };
  const updated1 = addSubtema(initial, "Apendicite");
  assert.deepEqual(updated1.subtema, ["Trauma", "Apendicite"]);

  // Tentativa de duplicata é ignorada
  const updated2 = addSubtema(updated1, "Trauma");
  assert.deepEqual(updated2.subtema, ["Trauma", "Apendicite"]);
});
