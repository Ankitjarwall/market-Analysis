---
name: frontend-design
description: Build distinctive, production-grade frontends that avoid generic aesthetics. Apply for all React/UI work in this project.
---

## Frontend Design Skill

### Design Philosophy
Before coding any UI component, consider:
- **Purpose & audience**: Traders need dense, information-rich displays. No wasted space.
- **Aesthetic direction**: This platform uses a **dark terminal/trading-desk** aesthetic — dark backgrounds (#0f1117, #1a1d26), monospace fonts for prices, subtle borders (#2a2d3a).
- **What makes it memorable**: Real-time data with immediate visual feedback (green/red), live pulsing indicators, sub-3-second latency feel.

### Color Conventions (Market Platform)
- `text-green-400` — price going up / FII buying / profit
- `text-red-400` — price going down / FII selling / loss
- `text-yellow-400` — warning / neutral / prediction
- `animate-ping` on a `bg-green-500` dot — live market open indicator
- `text-gray-500` — labels and secondary text
- `text-white` — primary values with no delta

### Live Data Display Rules
- Every price field MUST compare current vs `previousData` from `marketStore`
- Use `▲` (up arrow) and `▼` (down arrow) alongside color
- Show pulsing green dot for markets currently open (check UTC trading hours)
- Prices use `toLocaleString('en-IN')` for Indian number formatting

### Typography
- `font-mono` for all price/number values
- `font-semibold` or `font-bold` for key metrics
- `text-xs` for labels, `text-sm`–`text-3xl` for values depending on prominence

### Animation
- Price updates: use `transition-colors duration-300` for smooth color transitions
- Live indicators: use `animate-ping` for pulsing dot (Tailwind built-in)
- No distracting animations — subtle is better for a trading interface

### Component Patterns
- Cards: `className="card"` (from index.css)
- Grid layouts: `grid-cols-2 lg:grid-cols-4 gap-3`
- Scrollable ticker: `overflow-x-auto scrollbar-hide` with `whitespace-nowrap min-w-max`

### What to Avoid
- Light backgrounds or white themes
- Generic blue/gray color schemes without meaning
- Hiding data — traders want density
- Delayed UI feedback — every WebSocket update must immediately reflect in UI
