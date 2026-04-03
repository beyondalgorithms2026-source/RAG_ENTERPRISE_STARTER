# Design System Specification

## 1. Overview & Creative North Star: "The Intelligent Curator"
The Creative North Star for this design system is **The Intelligent Curator**. In the complex world of Retrieval-Augmented Generation (RAG) and Enterprise AI, the UI must not add to the noise; it must distill it. 

This system moves away from the "boxy" industrial feel of traditional SaaS. Instead, it adopts a high-end editorial approach characterized by **tonal depth, intentional asymmetry, and "breathable" layouts.** We break the template look by using generous white space as a structural element rather than a void. The experience should feel like a premium digital workspace—crisp, calm, and hyper-organized, yet softened by organic roundedness and subtle material layering.

---

## 2. Colors & Surface Logic
The palette is rooted in a sophisticated contrast between deep enterprise blues and "warm-white" surfaces. This creates a more human, premium feel than pure digital white (#FFFFFF).

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section off the interface. Structural boundaries are defined exclusively through background color shifts or tonal transitions. To separate a sidebar from a main content area, use `surface-container-low` (#f5f5e0) against the `surface` (#fbfbe6) background. 

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—stacked sheets of fine paper.
*   **Base:** `surface` (#fbfbe6) - The foundation.
*   **De-emphasized:** `surface-container-low` (#f5f5e0) - Use for secondary sidebars or footer areas.
*   **Elevated Content:** `surface-container-lowest` (#ffffff) - Reserved for primary cards or "active" work surfaces to give them a natural lift.
*   **Interactive/Nested:** `surface-container-high` (#eae9d5) - For elements nested inside cards, like code blocks or metadata chips.

### The "Glass & Gradient" Rule
To elevate the "RAG Console" experience, floating elements (modals, dropdowns, or pinned navigation) must utilize **Glassmorphism**.
*   **Token:** Use `surface` with 80% opacity and a `24px` backdrop-blur. 
*   **Signature Textures:** For main CTAs and Hero sections, use a subtle linear gradient: `primary` (#0e11d8) to `primary-container` (#343ced) at a 135-degree angle. This prevents the "flat" look and adds a sense of professional polish.

---

## 3. Typography
We utilize a highly disciplined typographic scale to convey authority and clarity.

*   **Display (3.5rem - 2.25rem):** Use `display-lg` and `display-md` for Hero statements and "Big Search" moments. These should be set with tight letter spacing (-0.02em) to feel editorial and high-end.
*   **Headline (2rem - 1.5rem):** Use `headline-md` for section headers. This is the "voice" of the console. 
*   **Title (1.375rem - 1rem):** For card titles and modal headers.
*   **Body (1rem - 0.75rem):** `body-lg` is the workhorse. Always prioritize line heights of 1.5x or 1.6x to ensure the "Calm" style guide requirement is met.
*   **Labels (0.75rem - 0.6875rem):** Used for metadata, breadcrumbs, and micro-copy. 

**Brand Note:** While the system defaults to Inter, when implementing Polysans-inspired weights, use "Medium" for headlines to mimic the "Neutral" 69% weight, and "Regular" for body text.

---

## 4. Elevation & Depth
In the absence of borders, depth is our primary tool for hierarchy.

*   **Tonal Layering:** Achieve "lift" by stacking `surface-container-lowest` (#ffffff) on top of `surface` (#fbfbe6). This creates a soft, natural edge that is easier on the eyes than a hard line.
*   **Ambient Shadows:** For floating elements (Modals, Popovers), use an extra-diffused shadow:
    *   `0px 12px 32px rgba(30, 41, 55, 0.06)`
    *   The shadow is tinted with `on-surface` (#1b1d10) rather than pure black to simulate natural light.
*   **The "Ghost Border" Fallback:** If accessibility requirements demand a border (e.g., in high-contrast situations), use `outline-variant` (#c6c5d9) at **15% opacity**. This provides a "hint" of a container without breaking the "No-Line" rule.

---

## 5. Components

### Buttons
*   **Primary:** Gradient of `primary` to `primary-container`. 12px (`md`) rounded corners. White text. No border.
*   **Secondary:** `secondary-container` background with `on-secondary-container` text.
*   **Tertiary/Ghost:** No background. `primary` text. Becomes `surface-container-low` on hover.

### Input Fields
*   **Style:** No 1px border. Use `surface-container-highest` (#e4e4cf) as the background. 12px rounded corners.
*   **Focus State:** A 2px "ring" of `primary` with a 4px offset.

### Cards & Lists
*   **Strict Rule:** No dividers. Use `3.5rem` (10) or `4rem` (12) vertical spacing to separate list items or background tonal shifts.
*   **RAG Context Cards:** Use `surface-container-lowest` with a "Ghost Border" for AI-generated responses to distinguish them from user-sourced data.

### Chips (Metadata & Tags)
*   **Filter Chips:** Use `tertiary-fixed` (#cdf13d) with `on-tertiary-fixed` (#171e00) for high-visibility AI "Confidence Scores" or "Source Citations."

---

## 6. Do's and Don'ts

### Do
*   **Do** use asymmetrical layouts. For example, a 1440px grid where the main content is offset to the left with a large, breathing margin on the right.
*   **Do** lean into the 12px (`md`) and 16px (`lg`) corner radii to keep the interface feeling approachable.
*   **Do** use `tertiary` (#3a4700) and `tertiary-fixed` (lime) for AI-specific highlights. It creates a "pro-tool" aesthetic distinct from standard SaaS.

### Don't
*   **Don't** use 100% opaque borders to separate sections. (Refer to the "No-Line" rule).
*   **Don't** use standard drop shadows (e.g., `0 2px 4px black`). They look "cheap." Use Ambient Shadows.
*   **Don't** crowd the interface. If a screen feels full, increase the spacing tokens (e.g., move from `8` to `12`) rather than adding dividers.
*   **Don't** use pure black (#000000) for text. Use `on-surface` (#1b1d10) to maintain the "calm" enterprise tone.