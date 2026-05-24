# CLAUDE.md - Haakonbench

## Purpose
A single static HTML page acting as a styled reference / strategy guide (WoW Classic fishing strategy for a level 60 Alliance warrior).

## Stack
- Pure HTML + inline CSS, no JS framework, no build step.
- Uses Google Fonts (`Cinzel`, `Inter`) via CDN.

## Entry point
- `index.html` - the whole project.

## Conventions / gotchas
- CSS variables for the theme are defined at top of `<style>` (`--gold`, `--alliance-blue`, etc.).
- No backend, no package manager, no tests.
- Edits = open `index.html` and modify directly.
