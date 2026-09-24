import { performance } from 'perf_hooks';

// Setup sample data simulating distractors and weakTopics
const generateData = (distractorCount, weakTopicCount) => {
  const distractors = Array.from({ length: distractorCount }, (_, i) => ({
    subtema: `Subtema ${i}`,
    wrong_choices: [{ letter: 'A', count: i % 5 }]
  }));

  const weakTopics = Array.from({ length: weakTopicCount }, () => ({
    topic: `Subtema ${Math.floor(Math.random() * distractorCount)}`,
    attempts: 10,
    correct: 5,
    accuracy: 0.5
  }));

  return { distractors, weakTopics };
};

const runBenchmark = (distractorCount, weakTopicCount, iterations = 10000) => {
  const { distractors, weakTopics } = generateData(distractorCount, weakTopicCount);

  // Baseline: O(N * M) Array.find inside loop
  const startBaseline = performance.now();
  for (let iter = 0; iter < iterations; iter++) {
    const sliced = weakTopics.slice(0, 8);
    sliced.map((wt) => {
      const distractor = Array.isArray(distractors) ? distractors.find(d => d.subtema === wt.topic) : undefined;
      return distractor?.wrong_choices?.[0];
    });
  }
  const baselineTime = performance.now() - startBaseline;

  // Optimized: O(1) Map lookup
  const startOptimized = performance.now();
  for (let iter = 0; iter < iterations; iter++) {
    // Map created once or memoized
    const map = new Map();
    if (Array.isArray(distractors)) {
      for (const d of distractors) {
        if (d?.subtema) map.set(d.subtema, d);
      }
    }
    const sliced = weakTopics.slice(0, 8);
    sliced.map((wt) => {
      const distractor = map.get(wt.topic);
      return distractor?.wrong_choices?.[0];
    });
  }
  const optimizedTime = performance.now() - startOptimized;

  // Memoized Map lookup (Map creation outside render loop / when distractors don't change)
  const map = new Map();
  if (Array.isArray(distractors)) {
    for (const d of distractors) {
      if (d?.subtema) map.set(d.subtema, d);
    }
  }
  const startMemoized = performance.now();
  for (let iter = 0; iter < iterations; iter++) {
    const sliced = weakTopics.slice(0, 8);
    sliced.map((wt) => {
      const distractor = map.get(wt.topic);
      return distractor?.wrong_choices?.[0];
    });
  }
  const memoizedTime = performance.now() - startMemoized;

  console.log(`--- Dataset: ${distractorCount} distractors, ${weakTopicCount} weakTopics (${iterations} iterations) ---`);
  console.log(`Baseline Array.find (.map loop): ${baselineTime.toFixed(2)} ms`);
  console.log(`Optimized (Map creation per render): ${optimizedTime.toFixed(2)} ms (${(baselineTime / optimizedTime).toFixed(2)}x faster)`);
  console.log(`Optimized (Memoized Map lookup): ${memoizedTime.toFixed(2)} ms (${(baselineTime / memoizedTime).toFixed(2)}x faster)\n`);
};

console.log("Running Distractors Lookup Benchmarks...\n");
runBenchmark(50, 20, 10000);
runBenchmark(200, 50, 10000);
runBenchmark(1000, 100, 10000);
