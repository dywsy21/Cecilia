# Dissertation Template

## Preview

<a href="example/dissertation.pdf"> <img src="example/dissertation.png"></a>

## Description

Dissertation template modified from the Eisvogel template. 

## Sample YAML Setup

Place the following at the top of your markdown file:

```
---
title: Your Awesome Academic Title
abstract: Lorem markdownum corpus. Date vastarumque artis a incepto Quodsi,
  pressit diversaque tersit excita. Ponti posset quo atro. Ama ungues quo via
  quaerenti culmine haesit moenibus iugum, pluribus flumina ingens.
author: Leonardo V. Castorina
acknowledgements: I would like to thank my dog Data.
declaration: I declare that this thesis was composed by myself, that the work
  contained herein is my own except where explicitly stated otherwise in the
  text, and that this work has not been submitted for any other degree
  pr  professional qualification except as specified.
text1: Doctor of Philosophy
text2: School of Informatics
text3: University of Edinburgh
text4: 2023
titlepage-logo: /path/to/your/logo.pdf
link-citations: true
reference-section-title: References
---
```

If you remove the sections marked as `acknowledgements`, `abstract`, `declaration` they will simply be removed from the export. 

`text1`, `text2`, `text3`, `text4` are text lines that appear after the logo in the cover page.

`titlepage-logo` is not necessary to produce this PDF.
