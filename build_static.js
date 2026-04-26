// build_static.js — bundles CodeMirror 6 into src/odsbox_pilot/static/codemirror/bundle.js
// Run with: npm run build   (or: node build_static.js)

import * as esbuild from "esbuild";
import { mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "src", "odsbox_pilot", "static", "codemirror");

await mkdir(outDir, { recursive: true });

await esbuild.build({
  stdin: {
    contents: `
// CodeMirror 6 — JSON editor bootstrap exposed as window.cm
import { EditorState } from "@codemirror/state";
import {
  EditorView,
  keymap,
  highlightSpecialChars,
  highlightActiveLine,
  lineNumbers,
  drawSelection,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import {
  syntaxHighlighting,
  defaultHighlightStyle,
  foldGutter,
  bracketMatching,
  indentOnInput,
} from "@codemirror/language";
import { lintGutter, linter } from "@codemirror/lint";
import { json, jsonParseLinter } from "@codemirror/lang-json";

let _view = null;

function createEditor(domId, initialContent) {
  const target = document.getElementById(domId);
  const startState = EditorState.create({
    doc: initialContent || "",
    extensions: [
      lineNumbers(),
      highlightSpecialChars(),
      history(),
      foldGutter(),
      drawSelection(),
      indentOnInput(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      bracketMatching(),
      highlightActiveLine(),
      keymap.of([...defaultKeymap, ...historyKeymap,
        {
          key: "Alt-Enter",
          run: () => {
            // Signal Python host to execute the query
            window.location.hash = "execute-" + Date.now();
            return true;
          },
        },
      ]),
      json(),
      linter(jsonParseLinter()),
      lintGutter(),
      EditorView.theme({
        "&": { height: "100%", fontSize: "13px", fontFamily: "Consolas, monospace" },
        ".cm-scroller": { overflow: "auto" },
      }),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          // Notify Python host via hash navigation (wx.html2 intercepts)
          window.location.hash = "changed";
        }
      }),
    ],
  });
  _view = new EditorView({ state: startState, parent: target });
  return _view;
}

// Public API
window.cm = {
  create: createEditor,
  getContent: () => (_view ? _view.state.doc.toString() : ""),
  setContent: (text) => {
    if (!_view) return;
    _view.dispatch({
      changes: { from: 0, to: _view.state.doc.length, insert: text },
    });
  },
  hasErrors: () => {
    if (!_view) return false;
    try {
      JSON.parse(_view.state.doc.toString());
      return false;
    } catch {
      return true;
    }
  },
};
`,
    resolveDir: __dirname,
    loader: "js",
  },
  bundle: true,
  minify: false,
  format: "iife",
  outfile: join(outDir, "bundle.js"),
  logLevel: "info",
});

console.log(`Bundle written to ${outDir}/bundle.js`);
