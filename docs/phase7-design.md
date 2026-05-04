# Phase 7: UI Polish & Timeseries Chart

## Design Direction: Industrial Terminal

The IMS dashboard uses a refined **industrial terminal** aesthetic:
- Deep black `#080808` background with a subtle scanline texture
- Geist font at all weights — 800 for numbers, 600 for headers, 400 for body
- Tight letter-spacing (-0.03em to -0.04em) on all headings
- Monospace data wherever numbers appear (font-family: var(--font-mono))
- `--text-2xs` (10px) ALL CAPS labels with wide letter-spacing for field names
- Priority colours are vivid against black: P0=#ff3b3b, P1=#ff8c00, P2=#f5c400, P3=#3b8cff
- Resolved/success colour: #00d97e (high-contrast green)
- 4px scrollbars, 3px radius badges, 1.5px strokes on charts

## New Components

### ThroughputChart (recharts AreaChart)
- 30-minute rolling window, auto-refreshes every 10s
- `<AreaChart>` with gradient fill, dotted grid lines at 4% opacity
- Custom tooltip with time + count
- Loading state shows animated skeleton bars
- Peak/total stats in header

### StatsStrip
Replaces MetricsBar with a denser single-row strip:
- 5 tiles in one `<div>` with internal `border-right` dividers
- P0 alert tile turns red background when `work_items_open > 0`
- P1 warning when queue > 5000
- Numbers at 22px/800 weight for instant scanning

## Animations
| Element | Animation | Duration |
|---------|-----------|---------|
| Page mount | fadeIn + translateY(8px) | 250ms |
| New table row | slideDown + green bg flash | 500ms |
| New signal row | slideRight + green bg flash | 350ms |
| Toast | slideUp + scale(0.96→1) | 200ms |
| Drawer open | translateX(100%→0) cubic-bezier(.22,1,.36,1) | 220ms |
| Shimmer skeleton | background-position sweep | 1600ms |
| P0 alert badge | opacity pulse | 2000ms |

## Responsive breakpoints
- Sidebar collapses to top nav at ≤900px
- Dashboard bottom grid goes 1-col at ≤960px
- Stats strip wraps at ≤700px
- Drawer is 96vw max on mobile
