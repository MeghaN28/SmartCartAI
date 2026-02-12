# SmartCartAI – UI Design Diagram

High-level structure of the mobile UI (React Native / Expo). Screens, tabs, and main components only.

---

## 1. App structure (navigation)

```mermaid
flowchart TB
  subgraph App["SmartCartAI App"]
    ThemeContext["ThemeContext\n(dark / light)"]
    Nav["NavigationContainer"]
    Tabs["Bottom Tab Navigator"]
  end

  ThemeContext --> Nav
  Nav --> Tabs

  Tabs --> Tab1["📦 Inventory"]
  Tabs --> Tab2["💬 Chatbot"]
  Tabs --> Tab3["📊 Dashboard"]
  Tabs --> Tab4["📤 Upload"]
  Tabs --> Tab5["💡 Suggestions"]

  Tab1 --> HomeScreen
  Tab2 --> ChatbotScreen
  Tab3 --> DashboardScreen
  Tab4 --> UploadScreen
  Tab5 --> SuggestionLogScreen
```

---

## 2. Screen → components (UI only)

```mermaid
flowchart TB
  subgraph Home["📦 Inventory (HomeScreen)"]
    H1[HeroSection]
    H2[SearchBar]
    H3[FilterSection]
    H4[InventoryGrid]
  end

  subgraph Chat["💬 Chatbot (ChatbotScreen)"]
    C1[WelcomeScreen]
    C2[MessageList]
    C3[ChatInput]
  end

  subgraph Dash["📊 Dashboard (DashboardScreen)"]
    D1[StatsGrid]
    D2[ChartsSection]
    D3[LowStockAlerts]
    D4[AddItemForm]
    D5[InventoryTable]
    D6[ItemForecastModal]
  end

  subgraph Upload["📤 Upload (UploadPurchaseScreen)"]
    U1[Document picker / CSV upload]
    U2[Upload result message]
  end

  subgraph Suggestions["💡 Suggestions (SuggestionLogScreen)"]
    S1[Suggestion list from API]
    S2[Refresh / empty state]
  end
```

---

## 3. Screen layout (what the user sees)

| Tab | Screen | Main UI blocks (top → bottom) |
|-----|--------|-------------------------------|
| **Inventory** | HomeScreen | Logo/header → HeroSection (stats) → SearchBar → FilterSection (status/sort) → InventoryGrid (cards) |
| **Chatbot** | ChatbotScreen | Welcome / quick questions → MessageList (chat bubbles) → ChatInput (text + send) |
| **Dashboard** | DashboardScreen | StatsGrid (Total / In stock / Low stock / Out of stock) → ChartsSection → LowStockAlerts → AddItemForm → InventoryTable (tap row → ItemForecastModal) |
| **Upload** | UploadPurchaseScreen | Title → “Pick CSV” button → Upload → Success/error message |
| **Suggestions** | SuggestionLogScreen | Title → List of suggestions (item, action, priority, reasoning, etc.) or empty state |

---

## 4. Component hierarchy (simplified)

```
App (App.js)
└── ThemeProvider
    └── AppNavigator
        └── NavigationContainer
            └── Tab.Navigator (5 tabs)
                ├── Inventory  → HomeScreen
                │                 ├── HeroSection
                │                 ├── SearchBar
                │                 ├── FilterSection
                │                 └── InventoryGrid (InventoryCard per item)
                │
                ├── Chatbot   → ChatbotScreen
                │                 ├── WelcomeScreen (quick questions)
                │                 ├── MessageList (user/bot messages)
                │                 └── ChatInput
                │
                ├── Dashboard → DashboardScreen
                │                 ├── StatsGrid
                │                 ├── ChartsSection
                │                 ├── LowStockAlerts
                │                 ├── AddItemForm
                │                 ├── InventoryTable
                │                 └── ItemForecastModal (modal)
                │
                ├── Upload    → UploadPurchaseScreen
                │                 └── (picker + result UI)
                │
                └── Suggestions → SuggestionLogScreen
                                    └── (list / refresh / empty)
```

---

## 5. Visual summary (one screen per box)

```mermaid
flowchart LR
  subgraph Screens["Screens (tabs)"]
    A[Inventory\nSearch, filter, grid]
    B[Chatbot\nMessages + input]
    C[Dashboard\nStats, charts, table]
    D[Upload\nCSV upload]
    E[Suggestions\nSuggestion log]
  end

  Theme["Theme\nDark / Light"] --> Screens
```

---

**Location of UI code**

- **Navigation:** `SmartCartAIFrontEnd/mobile/src/navigation/AppNavigator.js`
- **Screens:** `SmartCartAIFrontEnd/mobile/src/screens/`
- **Components:** `SmartCartAIFrontEnd/mobile/src/components/`
- **Theme:** `SmartCartAIFrontEnd/mobile/src/theme.js` + `contexts/ThemeContext.js`
