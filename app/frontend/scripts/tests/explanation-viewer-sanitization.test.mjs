import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function loadExplanationViewerModule() {
  const source = readFileSync(new URL('../../src/components/ExplanationViewer.tsx', import.meta.url), 'utf8');
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
      if (id === 'clsx') {
        return (...args) => args.filter(Boolean).join(' ');
      }
      if (id === '@/components/FormattedContent') {
        return {
          FormattedContent: () => null,
          preprocessMarkdown: (str) => typeof str === 'string' ? str.replace(/\\n/g, '\n').trim() : ''
        };
      }
      return {};
    },
    console: { log() {}, warn() {}, error() {} },
    Error: globalThis.Error,
    TypeError: globalThis.TypeError,
    Math: globalThis.Math,
    Boolean: globalThis.Boolean
  });

  return exports;
}

test('cleanSectionDelimiters: limpa delimitadores órfãos e pontuações residuais preservando formatação válida', () => {
  const { cleanSectionDelimiters } = loadExplanationViewerModule();

  // Entradas nulas ou inválidas
  assert.equal(cleanSectionDelimiters(null), '');
  assert.equal(cleanSectionDelimiters(undefined), '');
  assert.equal(cleanSectionDelimiters(''), '');

  // Delimitadores órfãos no início
  assert.equal(cleanSectionDelimiters('** Incorreta.'), 'Incorreta.');
  assert.equal(cleanSectionDelimiters('*** Incorreta.'), 'Incorreta.');
  assert.equal(cleanSectionDelimiters(': Incorreta.'), 'Incorreta.');
  assert.equal(cleanSectionDelimiters('- : Incorreta.'), 'Incorreta.');
  assert.equal(cleanSectionDelimiters('**\n- Letra B'), '- Letra B');

  // Delimitadores órfãos no final
  assert.equal(cleanSectionDelimiters('Texto clínico normal **'), 'Texto clínico normal');
  assert.equal(cleanSectionDelimiters('Texto clínico normal :'), 'Texto clínico normal');

  // Divisores horizontais e quebras de linha/HTML
  assert.equal(cleanSectionDelimiters('<br/><br/>Texto médico.<br/>'), 'Texto médico.');
  assert.equal(cleanSectionDelimiters('---\nTexto médico.\n---'), 'Texto médico.');

  // Preservação estrita de listas legítimas e negritos no corpo
  assert.equal(cleanSectionDelimiters('- Paciente hipertenso há 10 anos'), '- Paciente hipertenso há 10 anos');
  assert.equal(cleanSectionDelimiters('* Paciente hipertenso há 10 anos'), '* Paciente hipertenso há 10 anos');
  assert.equal(cleanSectionDelimiters('**Diagnóstico confirmado:** Apendicite aguda'), '**Diagnóstico confirmado:** Apendicite aguda');
});

test('parseExplanation: fallback defensivo para entradas nulas, vazias e não-string', () => {
  const { parseExplanation } = loadExplanationViewerModule();

  const resNull = parseExplanation(null);
  assert.equal(resNull.parsed.fallbackText, 'Nenhum comentário disponível para esta questão.');
  assert.equal(resNull.isDiscursiveDetected, false);

  const resUndefined = parseExplanation(undefined);
  assert.equal(resUndefined.parsed.fallbackText, 'Nenhum comentário disponível para esta questão.');

  const resEmpty = parseExplanation('   \n\t  ');
  assert.equal(resEmpty.parsed.fallbackText, 'Nenhum comentário disponível para esta questão.');

  const resNonString = parseExplanation(12345);
  assert.equal(resNonString.parsed.fallbackText, 'Nenhum comentário disponível para esta questão.');
});

test('parseExplanation: higieniza delimitadores residuais órfãos em comentários com colon-inside (**Cabeçalho:**)', () => {
  const { parseExplanation } = loadExplanationViewerModule();

  const explanationWithColonInside = `
**Gabarito:** Letra A

**Pulo do Gato:**
Conceito central de alta prevalência na residência médica.

**Por que a Letra A é a Correta?:**
Alternativa perfeitamente alinhada com as diretrizes do CFM e SBC.

**Análise dos Distratores:**
- **Letra B:** Incorreta devido à fisiopatologia inversa.
- **Letra C:** Incorreta pois não se aplica ao paciente pediátrico.
- **Letra D:** Incorreta pois o tratamento de primeira linha é farmacológico.
`;

  const { parsed, isDiscursiveDetected } = parseExplanation(explanationWithColonInside);

  assert.equal(isDiscursiveDetected, false);
  assert.equal(parsed.gabarito, 'Letra A');

  // Pulo do Gato limpo sem asteriscos ou dois-pontos órfãos
  assert.ok(parsed.puloDoGato);
  assert.ok(!parsed.puloDoGato.startsWith('**'));
  assert.ok(!parsed.puloDoGato.startsWith(':'));
  assert.equal(parsed.puloDoGato, 'Conceito central de alta prevalência na residência médica.');

  // Alternativa Correta limpa sem asteriscos órfãos
  assert.ok(parsed.alternativaCorreta);
  assert.equal(parsed.alternativaCorreta.letter, 'A');
  assert.ok(!parsed.alternativaCorreta.text.startsWith('**'));
  assert.ok(!parsed.alternativaCorreta.text.startsWith(':'));
  assert.equal(parsed.alternativaCorreta.text, 'Alternativa perfeitamente alinhada com as diretrizes do CFM e SBC.');

  // Distratores: nenhum item fantasma '•' com texto '**' e textos sem asteriscos residuais
  assert.equal(JSON.stringify(parsed.distratores.map(d => d.letter)), JSON.stringify(['B', 'C', 'D']));

  for (const d of parsed.distratores) {
    assert.ok(!d.text.startsWith('**'), `Distrator ${d.letter} não deve iniciar com asteriscos órfãos`);
    assert.ok(!d.text.startsWith(':'), `Distrator ${d.letter} não deve iniciar com dois-pontos`);
  }
  assert.equal(parsed.distratores[0].text, 'Incorreta devido à fisiopatologia inversa.');
});

test('parseExplanation: suporta Raciocínio Clínico e Padrão de Resposta com sanitização cirúrgica', () => {
  const { parseExplanation } = loadExplanationViewerModule();

  const explanationWithReasoning = `
**Gabarito**: Letra C

**Pulo do Gato**:
Análise imediata do ECG no infarto inferior.

**Raciocínio Clínico:**
O quadro clínico descreve dor torácica típica com supradesnivelamento do segmento ST em derivações inferiores (DII, DIII e aVF).
Investigação de ventrículo direito é mandatória.

**Por que a Letra C é a Correta?**:
A alternativa C aponta a realização de derivações direitas (V3R e V4R).

**Análise dos Distratores**:
- **Letra A**: Incorreta.
- **Letra B**: Incorreta.
- **Letra D**: Incorreta.
`;

  const { parsed } = parseExplanation(explanationWithReasoning);

  assert.equal(parsed.gabarito, 'Letra C');
  assert.ok(parsed.raciocinioClinico);
  assert.ok(!parsed.raciocinioClinico.startsWith('**'));
  assert.ok(!parsed.raciocinioClinico.startsWith(':'));
  assert.ok(!parsed.raciocinioClinico.includes('Por que a Letra C'));
  assert.ok(!parsed.raciocinioClinico.includes('Análise dos Distratores'));
  assert.equal(parsed.alternativaCorreta?.letter, 'C');
  assert.equal(parsed.distratores?.length, 3);
});

test('parseExplanation: detecta questões discursivas e preserva padrão de resposta sem distratores', () => {
  const { parseExplanation } = loadExplanationViewerModule();

  const discursiveExplanation = `
**Padrão de Resposta:**
Critérios esperados pela banca:
1. Identificação de choque séptico de foco pulmonar.
2. Início imediato de antibiótico na primeira hora e ressuscitação volêmica guiada por metas.
`;

  const { parsed, isDiscursiveDetected } = parseExplanation(discursiveExplanation, true);

  assert.equal(isDiscursiveDetected, true);
  assert.ok(parsed.padraoResposta);
  assert.ok(!parsed.padraoResposta.startsWith('**'));
  assert.ok(!parsed.padraoResposta.startsWith(':'));
  assert.equal(parsed.distratores, undefined);
});
