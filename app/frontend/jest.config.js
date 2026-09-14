const { createDefaultPreset } = require("ts-jest");

const tsJestTransformCfg = createDefaultPreset().transform;

/** @type {import("jest").Config} **/
module.exports = { testPathIgnorePatterns: ["/node_modules/", "/e2e/"],
  testEnvironment: "node",
  transform: {
    ...tsJestTransformCfg,
  },
};