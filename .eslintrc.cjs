module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: ["eslint:recommended", "plugin:react/recommended", "plugin:react-hooks/recommended"],
  settings: { react: { version: "18.3" } },
  rules: { "react/react-in-jsx-scope": "off", "react/prop-types": "off" },
};
