#!/usr/bin/env bash
# Build the NORMA guide PDFs (English + French) from their LaTeX sources.
# Usage:  bash guide/build.sh        (run from anywhere; it cd's to its own folder)
# Requires a TeX distribution providing pdflatex (e.g. TeX Live / MiKTeX).
set -e
cd "$(dirname "$0")"

command -v pdflatex >/dev/null 2>&1 || {
  echo "pdflatex not found. Install TeX Live (Linux: 'sudo apt install texlive-latex-recommended')." >&2
  exit 1
}

for f in norma-guide norma-guide-fr; do
  # run twice so the table of contents resolves
  pdflatex -interaction=nonstopmode -halt-on-error "$f.tex" >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error "$f.tex" >/dev/null
  echo "built $f.pdf"
done

rm -f ./*.aux ./*.toc ./*.out ./*.log
echo "Done. PDFs: guide/norma-guide.pdf (EN), guide/norma-guide-fr.pdf (FR)."
