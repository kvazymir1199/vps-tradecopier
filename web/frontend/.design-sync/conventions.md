# Trade Copier UI — conventions

A **shadcn/ui ("new-york") + Tailwind v4** component set for the Trade Copier admin app
(MT5 terminals, copy links, symbol/magic mappings). Components are imported from the bundle
global and already carry their own styling.

## Setup & wrapping

- **No provider is required for styling.** All design tokens ship as CSS variables in the
  stylesheet's `:root` (light) and `.dark` (dark) blocks — components are styled the moment
  the stylesheet is present.
- **Dark mode:** add `class="dark"` to any ancestor; every token flips automatically.
- **Toasts:** render `<Toaster />` once near the app root, then fire notifications with the
  imperative `toast` (re-exported on the bundle global alongside `Toaster`):
  `toast.success(...)`, `toast.error(...)`, `toast.warning(...)`, `toast.info(...)`.
- **Overlays** (`Dialog`, `AlertDialog`, `Select`) are Radix-based and controlled via
  `open` / `defaultOpen` / `onOpenChange` (or `value` / `onValueChange` for `Select`).

## Styling idiom — Tailwind utilities + semantic tokens

Style with **Tailwind utility classes**; brand color/spacing come from **semantic tokens**,
never hard-coded hex. Two safe routes, in order of preference:

1. **Component props first** — `variant` and `size` already encode the design language:
   `<Button variant="destructive" size="sm">`, `<Badge variant="secondary">`,
   `<Switch size="sm">`. Check each `<Name>Props` for the exact unions.
2. **Semantic classes / token variables for your own layout glue.** These semantic utility
   classes ship in the stylesheet (all token-backed, dark-mode aware):

   | Role | Classes |
   |---|---|
   | Surfaces | `bg-background` `bg-primary` `bg-secondary` `bg-muted` `bg-accent` `bg-destructive` `bg-popover` `bg-input` |
   | Text | `text-foreground` `text-muted-foreground` `text-primary-foreground` `text-secondary-foreground` `text-accent-foreground` |
   | Lines | `border-border` `border-input` `ring-ring` |
   | Radius | `rounded-md` (derived from `--radius`) |

   For anything not in the table above (e.g. card surfaces), use the token **CSS variables**
   directly — they are always present: `var(--card)`, `var(--card-foreground)`, `var(--popover)`,
   `var(--ring)`, `var(--radius)`, plus every name above (`var(--primary)`, `var(--muted-foreground)`, …).
   Standard non-color Tailwind utilities (`flex`, `grid`, `gap-*`, `p-*`, `text-sm`, …) are fine
   for layout. Never invent new color names — map to the tokens above.

## Where the truth lives

- **Styling:** `_ds/<folder>/styles.css` → `@import "./_ds_bundle.css"` — the compiled
  Tailwind (every utility the components use) plus the full `:root` / `.dark` token sets.
- **Per component:** `<Name>.d.ts` (the `<Name>Props` contract) and `<Name>.prompt.md`
  (usage). Read these before composing — compound components (`Table`, `Dialog`,
  `AlertDialog`, `Select`) expose sub-parts on the same bundle (e.g. `TableHeader`,
  `DialogContent`, `SelectItem`).

## Idiomatic example

```tsx
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge, Button } from "<bundle>";

<div className="flex flex-col gap-4">
  <div className="flex items-center justify-between">
    <h2 className="text-foreground text-lg font-semibold">Copy links</h2>
    <Button size="sm">+ Add link</Button>
  </div>
  <Table>
    <TableHeader>
      <TableRow><TableHead>Master</TableHead><TableHead>Slave</TableHead><TableHead>Enabled</TableHead></TableRow>
    </TableHeader>
    <TableBody>
      <TableRow>
        <TableCell className="font-medium">MT5-Master-01</TableCell>
        <TableCell className="text-muted-foreground">MT5-Slave-A</TableCell>
        <TableCell><Badge>On</Badge></TableCell>
      </TableRow>
    </TableBody>
  </Table>
</div>
```
