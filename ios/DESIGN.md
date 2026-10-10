# Design System: Canarito (iOS)

## Overview

**Creative North Star: "The night lamp"**

A quiet dark room with one small light on. The app is night teal and almost empty; canary yellow exists only for an alert. Nothing moves unless it means something. The home screen answers one question and gets out of the way.

Platform: native iOS. System navigation, sheets, lists and buttons. Brand lives in color, one display face for titles, and the content, never in reinvented controls.

**Key Characteristics:**
- Always dark. `preferredColorScheme(.dark)` on every screen, on purpose (night use). The alert screen is the one light surface: canary yellow with dark ink.
- One accent (night-teal accent) for interactive things. Canary is not an accent.
- The bird: app icon and a 26 pt mark in the home header. Never on an alert, late or after screen.
- No numbers on the home screen. States are words and one symbol.

## Colors

Defined once in `Brand.swift`. Raw hex appears nowhere else.

### Primary
- **Lamp Teal** (#56C2B6): buttons, links, the covered state. 7.6:1 on Surface.

### Secondary
- **Canary** (#F5C842): the alert screen background and the "limited" state tint. Nothing else.
- **Coral** (#F08A6E): problems that need action (location off, server unreachable).

### Neutral
- **Night** (#0E1517): page background.
- **Surface** (#172226): grouped lists, cards.
- **Text** (#E4ECEC), **Text Secondary** (#9DB0B2), **Outline** (#3A474B).
- **On Accent** (#062421): text on Lamp Teal. **On Canary** (#1E1700) and **On Canary Secondary** (#4A3B00).
- **Sand** (#D9D4C4): the test-alert background.

### Named Rules
**The Canary Rule.** Canary yellow only fills the alert screen. If a screen is yellow, an earthquake happened or someone pressed "send a test".
**The No-Gray Rule.** Secondary text is tinted from the page hue (Text Secondary), never system gray.

## Typography

**Display Font:** Bricolage Grotesque, weight 800, titles only (falls back to system rounded heavy).
**Body Font:** San Francisco through Dynamic Type text styles. No fixed point sizes except the display face, which scales with `@ScaledMetric`.

### Hierarchy
- **Display** (800, 28 to 30 pt, relative to Title): state title on home, alert headings.
- **Headline** (system headline): buttons, card titles.
- **Body** (system body, 17 pt): detail lines.
- **Caption** (system caption): source lines, never below 11 pt.

### Named Rules
**The Real Words Rule.** The alert text comes from the server and is shown as written. The app adds no advice of its own except the quoted guide line.

## Layout

Single column, 24 to 32 pt side margins, inside the safe area. Buttons pinned to the bottom, last in VoiceOver order. At accessibility text sizes the button scrolls with the content and rows turn into stacks (`AnyLayout`). Pictograms and icons scale with `@ScaledMetric`.

## Elevation & Depth

Flat. Depth is tonal: Surface on Night. No shadows, no glass, no blur.

## Shapes

One corner radius for cards and buttons: 14 pt. Pictogram rows use the same 14 pt. No colored side borders on cards.

## Components

### Buttons
One `ButtonStyle` pair (`CanaritoButtonStyle`: filled and outlined) with a pressed state (opacity 0.85, scale 0.98 unless Reduce Motion). Minimum height 52 pt. System `Button` semantics, never a tappable `Text`.

### Cards
Surface fill, 14 pt radius, 16 pt padding. Used for the server line and for warnings. Never nested.

### Navigation
A single home screen. Sheets for pairing details and settings. System navigation bar in sheets. No tab bar: there is one thing to look at.

### Icons
SF Symbols only, drawn at the surrounding text size. The bird is the single custom image.

## Motion

Reduce Motion is read through `AppMotion`. Without it: a cross-fade between states and one slow pulse on the covered symbol. With it: no pulse, state changes cut or fade. No slides.

## Do's and Don'ts

### Do:
- **Do** write every string in tú and in plain words. Say what is wrong and what the person can do.
- **Do** end every unknown state in a warning. Silence is not safety.
- **Do** keep copy true for a self-hosted server: no "we are fixing it", no company, no email.
- **Do** keep the alert screen free of everything but the fact, the elapsed time and the protective action.

### Don't:
- **Don't** put the bird on an alert, late or after screen.
- **Don't** use uppercase eyebrow labels, colored side bars, icon-in-a-circle heroes, or gradients.
- **Don't** show exact position or say it never leaves the phone. The app sends a rounded position to the paired server and says so.
- **Don't** add a paywall, account, email field or analytics.
- **Don't** reinvent a system control.
