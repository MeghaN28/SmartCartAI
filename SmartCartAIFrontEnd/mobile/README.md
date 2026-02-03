# SmartCartAI Mobile (React Native / Expo)

Mobile frontend for the medical inventory management app. All pages from the web app are available:

- **Inventory (Home)** – List and filter inventory items
- **Chatbot** – AI assistant (text mode; voice uses platform APIs where available)
- **Dashboard** – Stats, charts, low-stock alerts, add/edit/delete items, item forecast
- **Upload Purchase** – Pick and upload receipt files, trigger agent
- **Reorder Log** – View reorder log entries

## Setup

```bash
cd mobile
npm install
npx expo start
```

Then press `i` for iOS simulator or `a` for Android emulator, or scan the QR code with Expo Go.

## API base URL

The app uses `http://127.0.0.1:8080` for inventory and reorder APIs. For a physical device, set your machine’s LAN IP in `src/config.js` (e.g. `http://192.168.1.x:8080`) or use a tunnel (e.g. `npx expo start --tunnel`).
