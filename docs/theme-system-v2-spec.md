# Theme System V2 Spec (Culturally Grounded, Generic by Default)

## Goals

- Keep the default theme culturally warm and community-oriented without binding to one group.
- Make cultural direction configurable via tokens and components, not hardcoded per template.
- Preserve offline-first behavior and accessibility.
- Support future community-specific themes (for example Bororo) as layered overrides.

## Design Principles

- Ritual clarity over decoration: structured pages, calm spacing, high legibility.
- Symbolic structure: center/periphery patterns are optional layout metaphors.
- Controlled ornament: motifs only in headers/dividers/background accents, never under long text.
- Community governance: culturally sensitive visuals must be easy to configure and restrict.

## Scope

### In scope

- New theme tokens beyond colors/fonts.
- Optional layout metaphors and reusable symbolic components.
- Accessibility enforcement for contrast and motion.
- Module-specific "visual intensity" controls.
- Config schema extension and tests.

### Out of scope (this phase)

- Embedding community-specific sacred motifs in default presets.
- Shipping group-specific icon packs by default.

## Proposed Config Extensions

```yaml
theme:
  preset: "terra"
  style: "terra"
  layout_metaphor: "linear"         # linear | radial_hero | split_axis
  motif_style: "minimal_geometric"  # none | minimal_geometric | custom
  motif_density: "low"              # none | low | medium
  motion_tempo: "gentle"            # none | gentle | ceremonial
  icon_style: "outline"             # outline | filled | custom
  image_treatment: "natural"        # natural | muted | documentary
  module_intensity:
    dictionary: "minimal"
    encyclopedia: "balanced"
    myths: "rich"
  language_emphasis:
    weight: 600
    color: "primary"
    italic: false
  community_visual_rules:
    allow_patterns: true
    allow_ritual_imagery: false
```

## Token Model

### Existing tokens (keep)

- Colors, radius, fonts, logo/favicon, hero image.

### New semantic tokens

- `layout_metaphor`
- `motif_style`
- `motif_density`
- `motion_tempo`
- `icon_style`
- `image_treatment`
- `module_intensity`
- `language_emphasis`

### Color semantics refinement

- Keep `accent` for non-text emphasis (borders, dividers, badges, focus rings).
- Use `accent_muted` or `primary` for body-size link text on light surfaces.
- Add CI checks for text contrast thresholds.

## Component System (Reusable, Optional)

- `centerpiece`: central emblem/wordmark block.
- `ring_nav`: radial or semi-radial section list (hero-level, optional).
- `section_spine`: thin vertical structural rule for entry lists.
- `motif_divider`: low-contrast separator motif.
- `badge_circle`: small circular module marker.

All components must have a no-ornament fallback.

## Template Architecture

- Keep base linear layout as default.
- Add optional hero variant hooks:
  - `hero_layout = standard | radial`
  - `hero_decor = none | divider | motif`
- Inner pages remain linear for readability, with optional small symbolic markers.

## Accessibility and Performance

- Contrast:
  - Normal text: WCAG AA (4.5:1).
  - Large text: 3:1.
- Motion:
  - Respect `prefers-reduced-motion`.
  - No flashing or rapid loops.
- Offline:
  - No external font/image dependencies.
  - All motifs via inline SVG/CSS or packaged assets.

## Language Picker Policy

- Remains intentionally minimal and standalone.
- Must still align with theme basics:
  - bundled font loading
  - style class hook
  - consistent spacing and color tokens

## Implementation Plan

1. Phase 1: Hardening and baseline consistency
- Validate config shapes for `theme` objects.
- Adjust low-contrast text usages in templates/CSS.
- Keep language picker standalone, but load bundled fonts and heading font token.

2. Phase 2: Token and schema expansion
- Extend dataclasses and `THEME_PRESETS`.
- Add defaults for new semantic tokens.
- Add tests for token loading/override behavior.

3. Phase 3: Optional symbolic components
- Add template partials for `section_spine`, `motif_divider`, `badge_circle`.
- Add feature flags through context/theme tokens.
- Snapshot-style tests for rendered output hooks.

4. Phase 4: Layout metaphors
- Add optional `radial_hero` and `split_axis` hero templates.
- Ensure mobile fallbacks degrade to linear stack.
- Add visual regression checks where possible.

5. Phase 5: Governance and documentation
- Document a "Cultural Theme Playbook" for co-design workflows.
- Define public vs restricted motif/image guidance for contributors.

## Testing Plan

- Unit tests:
  - Config validation and token merge behavior.
  - Invalid value/type handling.
- Template tests:
  - Presence of expected classes/hooks for enabled modes.
- Style checks:
  - Contrast validation for theme text tokens.
- Build tests:
  - Static assets copied and referenced correctly.

## Risks and Mitigations

- Risk: Over-generalization creates vague visuals.
  - Mitigation: keep defaults opinionated; expose tokens selectively.
- Risk: Cultural mismatch if motifs are too literal.
  - Mitigation: default motifs remain abstract and low-fidelity.
- Risk: Theme complexity increases maintenance burden.
  - Mitigation: phased rollout with strict defaults and documentation.
