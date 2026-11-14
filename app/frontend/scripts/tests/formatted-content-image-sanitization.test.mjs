import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function loadFormattedContentModule() {
  const source = readFileSync(new URL('../../src/components/FormattedContent.tsx', import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { 
      module: ts.ModuleKind.CommonJS, 
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX
    },
  });

  const exports = {};
  runInNewContext(outputText, {
    exports,
    require: (id) => {
      if (id === 'react' || id === 'react/jsx-runtime') {
        return {
          createElement: () => null,
          useMemo: (fn) => fn(),
          useState: (init) => [init, () => {}],
          jsx: () => null,
          jsxs: () => null,
          Fragment: Symbol('Fragment')
        };
      }
      if (id === 'lucide-react') {
        return new Proxy({}, { get: () => () => null });
      }
      return {};
    },
    console: { log() {}, warn() {}, error() {} },
    Error: globalThis.Error,
    TypeError: globalThis.TypeError,
    Math: globalThis.Math,
    Boolean: globalThis.Boolean,
    encodeURI: globalThis.encodeURI,
    decodeURI: globalThis.decodeURI,
    Array: globalThis.Array,
    Set: globalThis.Set,
    String: globalThis.String,
    RegExp: globalThis.RegExp
  });

  return exports;
}

test('preprocessMarkdown: sanitiza URLs de imagens com espaços e parênteses sem quebrar tags', () => {
  const { preprocessMarkdown } = loadFormattedContentModule();

  const input = `
Diagnóstico: 3 critérios maiores MAIS 1 critério menor.
![imagem](https://cdn.medway.com.br/media/question_explanation_images/Sem título-1 (1).png)

Tratamento: Ambulatorial vs Hospitalar
![imagem](https://cdn.medway.com.br/media/question_explanation_images/Sem título-12 (1).png)
`;

  const output = preprocessMarkdown(input);

  // Não deve conter parênteses brutos não-escapados dentro da URL antes do fechamento
  assert.ok(output.includes('Sem%20t%C3%ADtulo-1%20%281%29.png'));
  assert.ok(output.includes('Sem%20t%C3%ADtulo-12%20%281%29.png'));
  assert.ok(!output.includes('Sem título-1 (1).png'));
});

test('normalizeImageSrc: sanitiza URLs com espaços e caracteres especiais', () => {
  const { normalizeImageSrc } = loadFormattedContentModule();

  const rawUrl = 'https://cdn.medway.com.br/media/question_explanation_images/HAS (MAPA).png';
  const normalized = normalizeImageSrc(rawUrl);

  assert.equal(normalized, 'https://cdn.medway.com.br/media/question_explanation_images/HAS%20%28MAPA%29.png');
});
