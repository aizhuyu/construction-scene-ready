# AIC manuscript workspace

Compile the anonymous manuscript:

```bash
/Library/TeX/texbin/latexmk -xelatex manuscript.tex
```

Compile the separate title page:

```bash
/Library/TeX/texbin/latexmk -xelatex title-page.tex
```

The manuscript uses:

- Elsevier `elsarticle` class;
- review/preprint layout with line numbers;
- numbered Elsevier citations;
- separate `highlights.txt`;
- separate author/title page;
- explicit CRediT, data, code, competing-interest, funding, and AI-use
  statement placeholders.

No empirical result is pre-filled. Planned results are visibly marked and must
only be replaced after the registered experiment scripts generate them.

