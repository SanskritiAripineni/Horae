# AutoLife — Mobile UI Screens

## Navigation Structure

The app uses a bottom navigation bar with 5 tabs plus a Settings/Dev route:

| Tab | Icon | Purpose |
|-----|------|---------|
| **Agent** | SmartToy | Run analysis, view tool status, see last result |
| **Health** | FavoriteBorder | Detailed wellbeing assessment |
| **Schedule** | CalendarMonth | Visual calendar + proposal selection |
| **Journal** | Article | View journals and live sensor logs |
| **Memory** | Storage | View personalization data from backend |

Settings gear → **Dev Dashboard** (debug controls)

---

## Agent Screen

The control panel. Users come here to trigger analysis and see pipeline status at a glance.

### Life Agent Control Card
- **"Run Analysis"** button — sends journals + sensor data to backend, starts pipeline
- **"Cancel Analysis"** button — appears while running
- Last run timestamp + journal count sent
- Linear progress bar while running
- Error card with retry option if pipeline fails

### Tools Grid (2×2)
Four status tiles, each tappable to open a detail bottom sheet:

1. **AutoLife (Live) — Motion & Location**
   - Current detected activity: Walking / Still / Vehicle / etc.
   - Acceleration reading in m/s²

2. **Wellbeing — Behavioral State**
   - Risk level badge (minimal / mild / moderate / severe)
   - Signal count (# concerns + # positives detected)

3. **VectorDB — Wellness Research**
   - Status: OK / Error / —
   - Top-K = 5 (papers retrieved per query)

4. **Calendar — Events & Tasks**
   - Upcoming event count
   - Task count

### Memory Section
- Preferences: goal count from user memory
- Health history: entry count + trend direction

### Last Result Summary
Shown after analysis completes:
- Risk state (large, color-coded text)
- Recommendation count
- Proposed changes count
- Error count (if any)
- Tap to open full detail bottom sheet

### Tool Detail Bottom Sheets
Each grid tile opens a sheet:
- **AutoLife Detail:** Live motion class, acceleration, location info
- **Wellbeing Detail:** Risk level, all concerns, all positives, behavioral context prose
- **VectorDB Detail:** Status, embedding model used, description
- **Calendar Detail:** Event list, task list, total scheduled hours
- **Last Result Detail:** Full summary prose + all recommendations + all proposals with "Apply to Calendar" option

---

## Health Screen

Displays the full wellbeing assessment from the last pipeline run.

### Elements (top to bottom)
- **Risk Level Card:** Large hero card with color-coded risk state
  - minimal = green, mild = yellow, moderate = orange, severe = red
- **Status Pill:** Risk level badge
- **Behavioral Context:** Prose from the sensor pipeline (e.g., "Sleep disruption detected with elevated late-night device engagement...")
- **Summary:** Journal summary if available
- **Key Concerns:** Bulleted list with warning icons (e.g., "below-average sleep duration", "elevated screen time")
- **Positive Indicators:** Bulleted list with checkmarks (e.g., "maintained physical activity", "social engagement present")
- **Recommendations:** One card per recommendation
  - Category pill (Sleep / Stress / Social / Physical / Mindfulness) — color-coded
  - Priority indicator (high / medium / low) if available
  - Action text (specific, actionable)
  - "When to do" sub-text if available
- **Errors:** Red error list if pipeline had partial failures

---

## Schedule Screen

The most interactive screen — shows a visual weekly calendar with AI proposals overlaid.

### Weekly Summary Card (top)
- Total scheduled hours across the week
- Existing event count
- AI proposal count
- Category breakdown pills: Work hours / Health hours / Leisure hours

### Filter Chips
Toggle visibility by category: Work / Health / Leisure

### Week Navigation
- Left/right chevrons to move between weeks
- Week range label: "Mon Jan 13 – Sun Jan 19"

### Week Bar Chart
- **Rows:** 7 days (Mon–Sun)
- **Columns:** Time axis 6 AM – 10 PM
- **Existing events:** Colored blocks
  - Work = blue
  - Health = green
  - Leisure = gray
- **Proposals:** Light green, semi-transparent blocks
- **Conflicts:** Proposals overlapping existing events are visually flagged
- **Tap event:** Opens detail bottom sheet with title, time, description

### AI Proposals List (below chart)

**Clear Proposals** (no conflict):
- Checkbox (selectable)
- Event title
- Formatted time: "Wed, Jan 15 · 8:00 AM – 8:30 AM"
- Expandable description
- "Select All" button for the section

**Conflict Proposals** (red left border, disabled):
- Title + time
- Warning icon + "Overlaps existing event" label
- Cannot be selected or applied

### Apply Button
"Apply X changes to Calendar" — disabled until at least one proposal is checked.
Sends selected proposals to `POST /api/apply_calendar`.

---

## Journal Screen

Two tabs showing collected data from the background service.

### Journals Tab
- Status bar: Service active/stopped badge + detected motion class + log/journal counts
- "Clear All" button (shows confirmation dialog)
- **Journal cards** (newest first):
  - Date + time header (tap to expand/collapse)
  - Period label: Morning / Afternoon / Evening / Night
  - Content preview (3 lines collapsed, full text when expanded)

### Live Logs Tab
Raw sensor events from the background service:
- "Clear All" button
- **Log cards:**
  - Type badge with color: MOTION (blue) / LOCATION (green) / WIFI (orange)
  - Timestamp
  - Content: JSON payload (max 4 lines displayed)

---

## Memory Screen

Shows personalization data fetched from `GET /api/memory`.

### Elements
- **Header:** "Memory" title + "Refresh" button (or loading spinner)
- **Error Card:** If fetch fails, shows message + "Retry" button

### Preferences Card
- Work Hours: "9:00 – 17:00"
- Max Daily Hours: "8h"
- Goals: Bulleted list (e.g., "improve sleep", "reduce stress")
- Preferred Interventions: Comma-separated (e.g., "yoga, meditation, walking")

### Wellbeing Card
- Current Risk Level (color-coded)
- Trend: stable / improving / declining
- History count: "X entries recorded"

### History List
Per-entry row: Date + Risk level badge + Status pill

---

## Dev Dashboard (Settings)

Debug/research controls accessible from the Settings gear icon:
- Toggle demo mode (2-min vs 15-min journal interval)
- Manual sensor collection triggers
- Backend URL override for local development
- Raw pipeline output viewer
- Service start/stop controls
