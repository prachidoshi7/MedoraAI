# MedoraAI — Light Theme (Primary) + Dark Mode Toggle

## Goal

Convert the current dark-only glassmorphic frontend into a **light-primary design** with a **toggle button** to switch to dark mode. The light theme should feel clean, premium, and medical — similar to Doctronic.ai's default light mode. The user's theme preference is persisted in `localStorage`.

---

## Core Problem
c
Currently, **all 10 component/page TSX files contain hardcoded color values in inline styles** (e.g. `#09090B`, `rgba(255,255,255,0.06)`, `#FAFAFA`, `#2DD4BF`). This means:

1. We must introduce **CSS custom properties** (`var(--xxx)`) for every semantic color
2. We must **refactor every inline `style={{...}}` color** across all files to use these variables
3. We must define **two complete palettes** (light + dark) that swap via a `data-theme` attribute on `<html>`
4. We need a **ThemeProvider context** + toggle button in the navbar

> [!IMPORTANT]
> This is a **significant refactor** — every TSX file must be touched to replace ~200+ hardcoded color references with CSS variables. The architecture shift is from "colors in JS" → "colors in CSS via custom properties".

---

## Design — Light Theme Palette

Inspired by Doctronic.ai's light mode: clean white backgrounds, soft gray text, the same teal/cyan accents but adapted for light surfaces.

| Token | Light Value | Dark Value | Usage |
|-------|-------------|------------|-------|
| `--bg-primary` | `#FFFFFF` | `#09090B` | Page background |
| `--bg-secondary` | `#F8FAFB` | `#0F0F12` | Subtle section backgrounds |
| `--bg-card` | `rgba(255,255,255,0.7)` | `rgba(255,255,255,0.03)` | Glass card fills |
| `--bg-card-hover` | `rgba(0,0,0,0.02)` | `rgba(255,255,255,0.06)` | Hover state |
| `--bg-input` | `rgba(0,0,0,0.03)` | `rgba(255,255,255,0.04)` | Input fields |
| `--bg-overlay` | `rgba(255,255,255,0.85)` | `rgba(9,9,11,0.88)` | Loading overlay |
| `--text-primary` | `#09090B` | `#FAFAFA` | Headings / main text |
| `--text-secondary` | `#52525B` | `#A1A1AA` | Descriptions |
| `--text-muted` | `#A1A1AA` | `#52525B` | Labels / hints |
| `--text-hint` | `#D4D4D8` | `#3F3F46` | Faintest text |
| `--border` | `rgba(0,0,0,0.06)` | `rgba(255,255,255,0.06)` | Card borders |
| `--border-light` | `rgba(0,0,0,0.10)` | `rgba(255,255,255,0.10)` | Stronger borders |
| `--glass-border` | `rgba(0,0,0,0.08)` | `rgba(255,255,255,0.08)` | Glass borders |
| `--glass-bg` | `rgba(255,255,255,0.6)` | `rgba(255,255,255,0.03)` | Glass fills |
| `--nav-bg` | `rgba(255,255,255,0.75)` | `rgba(9,9,11,0.75)` | Navbar background |
| `--shadow-card` | `0 2px 16px rgba(0,0,0,0.06)` | `0 8px 32px rgba(0,0,0,0.3)` | Card shadows |
| `--shadow-heavy` | `0 12px 40px rgba(0,0,0,0.08)` | `0 32px 64px rgba(0,0,0,0.5)` | Modal shadows |
| `--orb-teal` | `rgba(45,212,191,0.08)` | `rgba(45,212,191,0.08)` | Gradient orb (same) |
| `--orb-violet` | `rgba(139,92,246,0.06)` | `rgba(139,92,246,0.06)` | Gradient orb (same) |
| `--orb-cyan` | `rgba(34,211,238,0.05)` | `rgba(34,211,238,0.05)` | Gradient orb (same) |
| `--accent` | `#0D9488` | `#2DD4BF` | Primary accent (darker teal for light bg) |
| `--accent-light` | `#14B8A6` | `#5EEAD4` | Lighter accent |
| `--accent-cyan` | `#0891B2` | `#22D3EE` | Cyan accent |
| `--accent-violet` | `#7C3AED` | `#8B5CF6` | Violet accent |
| `--btn-primary-text` | `#FFFFFF` | `#09090B` | Button text on accent bg |
| `--logo-stroke` | `#FFFFFF` | `#09090B` | Logo cross stroke |
| `--dot-pattern` | `rgba(0,0,0,0.04)` | `rgba(255,255,255,0.015)` | Dot grid opacity |
| `--scrollbar-thumb` | `rgba(0,0,0,0.12)` | `rgba(255,255,255,0.08)` | Scrollbar |

> [!NOTE]
> Accent colors are **slightly darker** in light mode (e.g. `#0D9488` vs `#2DD4BF`) so they have sufficient contrast against white backgrounds. Severity colors remain the same in both themes.

---

## Proposed Changes

### 1. Theme Infrastructure

#### [NEW] [ThemeProvider.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/hooks/ThemeProvider.tsx)

New React context to manage theme state:
- Stores `'light' | 'dark'` in state
- Reads initial value from `localStorage('medoraai_theme')`, defaults to `'light'`
- Sets `data-theme` attribute on `document.documentElement`
- Exposes `{ theme, toggleTheme }` via context

#### [NEW] [useTheme.ts](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/hooks/useTheme.ts)

Hook to consume the theme context (mirrors the `useAuth` pattern).

---

### 2. CSS Design System

#### [MODIFY] [globals.css](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/styles/globals.css)

Major restructure:
- **Remove** the `@theme` block with hardcoded dark colors
- **Add** `:root` (light theme) and `[data-theme="dark"]` blocks defining all custom properties from the table above
- **Update** all CSS utilities (`.glass-card`, `.glass-nav`, `.glass-input`, `.btn-primary`, `.badge-*`, `.skeleton`, `.page-bg`, etc.) to use `var(--xxx)` instead of hardcoded colors
- **Adjust** gradient orbs for light mode (more subtle, slightly different hues)
- **Update** `.gradient-text` and `.gradient-text-teal` to use `var(--accent)` → `var(--accent-cyan)` gradients
- **Add** transition on `background-color, color, border-color` on `body` for smooth theme switching

#### [MODIFY] [index.html](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/index.html)

- Add inline `<script>` in `<head>` to read `localStorage('medoraai_theme')` and set `data-theme` on `<html>` **before paint** (prevents flash of wrong theme)
- Update `<meta name="theme-color">` to white for light mode

---

### 3. App Shell

#### [MODIFY] [main.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/main.tsx)

- Wrap `<App />` with `<ThemeProvider>` (inside `<AuthProvider>`)

#### [MODIFY] [App.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/App.tsx)

- Add theme toggle button (sun/moon SVG icon) to the navbar right section
- Replace all hardcoded inline colors in NavBar with `var(--xxx)` references
- Update logo stroke color to use `var(--logo-stroke)`

---

### 4. Pages — Replace Hardcoded Colors

#### [MODIFY] [LoginPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/LoginPage.tsx)

Replace all inline style colors:
- `#09090B` → `var(--bg-primary)`
- `rgba(255,255,255,0.03)` → `var(--glass-bg)`
- `rgba(255,255,255,0.08)` → `var(--glass-border)`
- `#FAFAFA` → `var(--text-primary)`  (not used directly but implied)
- `#71717A` → `var(--text-secondary)` 
- `#2DD4BF` → `var(--accent)`
- All `rgba(45,212,191,...)` accent references → `var(--accent-*)` variants
- Background → `var(--bg-primary)`
- Card shadow → `var(--shadow-heavy)`
- Dot pattern → `var(--dot-pattern)`

#### [MODIFY] [UploadPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/UploadPage.tsx)

Same pattern — replace ~30+ hardcoded colors with CSS variables.

#### [MODIFY] [ResultsPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/ResultsPage.tsx)

Same pattern — replace hardcoded colors with CSS variables.

---

### 5. Components — Replace Hardcoded Colors

#### [MODIFY] [UploadZone.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/UploadZone.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

#### [MODIFY] [LoadingSpinner.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/LoadingSpinner.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

#### [MODIFY] [ScanViewer.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ScanViewer.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

#### [MODIFY] [ResultPanel.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ResultPanel.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

#### [MODIFY] [ReportEditor.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ReportEditor.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

#### [MODIFY] [HistorySidebar.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/HistorySidebar.tsx)

Replace all hardcoded inline colors with `var(--xxx)`.

---

## Theme Toggle Button Design

The toggle will be a **pill-shaped button** in the navbar with an animated sun/moon SVG icon:

```
┌──────────────────────────────────────────────────────┐
│  🏥 MedoraAI   ○ New Scan          ☀️   👤 demo  │
└──────────────────────────────────────────────────────┘
                                      ↑
                              Theme toggle (sun/moon)
```

- **Light mode**: Shows moon icon 🌙 (click to go dark)
- **Dark mode**: Shows sun icon ☀️ (click to go light)
- Smooth icon rotation transition on toggle
- `localStorage` persistence

---

## Open Questions

> [!IMPORTANT]
> **Accent color in light mode**: Should I keep the exact same bright teal `#2DD4BF` or darken it to `#0D9488` for better contrast against white backgrounds? I'm planning to use the darker variant for body text/links but the brighter variant for gradients and badges.

---

## Verification Plan

### Automated Tests
- `npx tsc -b --noEmit` — TypeScript check (0 errors expected)
- `npm run build` — Production build

### Manual Verification
1. Run `npm run dev`
2. **Light mode (default)**: Verify all 3 pages are clean white with proper contrast
3. **Dark mode (toggle)**: Verify dark theme is identical to the current design
4. **Toggle persistence**: Refresh page → theme should persist
5. **No flash**: Hard refresh → no flash of wrong theme (thanks to inline script)
6. **All functionality**: Login, upload, analyze, results, PDF download, history still work
7. **Hover/focus states**: All interactive elements look correct in both themes
