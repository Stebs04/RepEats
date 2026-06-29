---
name: Lumina Performance AI
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#baccb0'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#85967c'
  outline-variant: '#3c4b35'
  surface-tint: '#2ae500'
  primary: '#efffe3'
  on-primary: '#053900'
  primary-container: '#39ff14'
  on-primary-container: '#107100'
  inverse-primary: '#106e00'
  secondary: '#ffb59c'
  on-secondary: '#5c1900'
  secondary-container: '#fa5c1c'
  on-secondary-container: '#511500'
  tertiary: '#e6fffe'
  on-tertiary: '#003737'
  tertiary-container: '#00f6f6'
  on-tertiary-container: '#006d6d'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#79ff5b'
  primary-fixed-dim: '#2ae500'
  on-primary-fixed: '#022100'
  on-primary-fixed-variant: '#095300'
  secondary-fixed: '#ffdbcf'
  secondary-fixed-dim: '#ffb59c'
  on-secondary-fixed: '#390c00'
  on-secondary-fixed-variant: '#832700'
  tertiary-fixed: '#00fbfb'
  tertiary-fixed-dim: '#00dddd'
  on-tertiary-fixed: '#002020'
  on-tertiary-fixed-variant: '#004f4f'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-xl:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-xl-mobile:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 42px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  stat-value:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '800'
    lineHeight: 32px
    letterSpacing: -0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  container-margin: 20px
  gutter: 16px
---

## Brand & Style
The design system is engineered for a premium, tech-forward fitness and nutrition ecosystem. The brand personality is high-energy, precise, and authoritative, positioning the AI as a high-performance coach rather than just a tracker. 

The visual style blends **Dark Minimalism** with **Glassmorphism**. It utilizes anthracite depth to reduce eye strain during workouts, while employing vibrant, neon-tinted "data glows" to highlight progress. The interface feels like a high-end sports car dashboard—tactile, responsive, and glowing with vital information. Every element is designed to evoke a sense of digital intelligence and physical momentum.

## Colors
This design system operates exclusively in a dark-mode environment to maintain high contrast and a "tech-core" aesthetic.

- **Neon Green (Primary):** Reserved for core fitness actions: "Start Workout," completion states, and positive performance trends.
- **Electric Orange (Secondary):** Used for nutrition, metabolic energy tracking, and high-intensity alerts.
- **Cyan/Electric Blue (AI/Tech):** Used for AI-driven insights, chatbot interactions, and automated scheduling.
- **Surfaces:** The base layer is `#121212`. Cards and elevated surfaces use `#181818` with varying levels of opacity (60-80%) when combined with backdrop blurs.

## Typography
The system uses **Inter** for its systematic, geometric clarity. The hierarchy is designed to make data consumption effortless during physical activity.

- **Headlines:** Use Bold or ExtraBold weights with tighter letter spacing to feel aggressive and impactful.
- **Stats:** A specific "stat-value" role is used for numerical data (reps, calories, time) to ensure prominence.
- **Labels:** Small caps and increased letter spacing are used for category tags to distinguish them from interactive body text.

## Layout & Spacing
This design system utilizes an **8px linear scale** for spatial harmony.

- **Grid:** A 12-column grid is used for desktop, 8-column for tablet, and 4-column for mobile.
- **Padding:** Content cards use a default internal padding of `24px` (`md`) to provide breathing room for data visualizations.
- **Safe Areas:** Mobile layouts must maintain a `20px` horizontal margin to prevent glass-card strokes from clipping on curved displays.

## Elevation & Depth
Depth is created through **Glassmorphism** rather than traditional drop shadows. 

- **Surface 0 (Background):** Solid `#121212`.
- **Surface 1 (Cards):** `#181818` with 70% opacity, a `16px` backdrop-blur, and a `1px` inner-border (`rgba(255, 255, 255, 0.1)`).
- **Surface 2 (Modals/Overlays):** `#181818` with 90% opacity, `32px` backdrop-blur, and a subtle outer glow matching the primary or secondary accent color (5% opacity).
- **Interactive States:** When hovered or pressed, glass elements should increase their background opacity and border brightness.

## Shapes
The shape language is "Hyper-Rounded," emphasizing approachability within a technical framework.

- **Primary Containers:** `rounded-lg` (16px) for standard cards.
- **Hero Containers:** `rounded-xl` (24px) for large dashboard widgets.
- **Buttons/Inputs:** `rounded-lg` (16px) to maintain a cohesive look with cards.
- **Progress Bars:** Fully pill-shaped for a fluid, organic feel.

## Components

- **Buttons:** Primary buttons use a solid Neon Green fill with black text. Secondary buttons use a glass-style border with a subtle Cyan glow effect on hover.
- **Cards:** All cards must implement `backdrop-filter: blur(16px)` and a thin, top-weighted gradient border to simulate light catching the "edge" of the glass.
- **Progress Indicators:** Use glowing gradients (e.g., Neon Green to Cyan) for rings and bars to represent AI-optimized goals.
- **Input Fields:** Semi-transparent dark backgrounds with a 1px border that illuminates in Electric Orange or Cyan when focused.
- **Chips/Badges:** Small, pill-shaped elements with low-opacity fills and high-intensity text colors (e.g., 15% Green background with 100% Green text).
- **AI Insight Component:** A specialized card featuring a subtle animated Cyan mesh gradient in the background to signify "active thinking" or real-time processing.