module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  globals: { __APP_VERSION__: "readonly" },
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  extends: ["eslint:recommended", "plugin:react/recommended", "plugin:react-hooks/recommended"],
  settings: { react: { version: "18.3" } },
  rules: {
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "space-infix-ops": "error",
    "no-multi-spaces": "error",
    "key-spacing": ["error", { "beforeColon": false, "afterColon": true }]
  },
};
