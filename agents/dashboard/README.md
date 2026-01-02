# Task Dashboard

React SPA for ai4u.now smart task management system.

## Features

- **Multi-View Support**: List, Kanban, Calendar, Timeline
- **Real-time Sync**: Firebase Firestore live updates
- **Telegram Auth**: Login with Telegram Widget
- **Dark Mode**: Full dark/light theme support
- **Responsive**: Mobile-friendly design

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: TanStack Query (server) + Zustand (client)
- **Calendar**: react-big-calendar
- **Drag-drop**: @hello-pangea/dnd
- **Backend**: Modal.com (FastAPI)
- **Database**: Firebase Firestore
- **Auth**: Telegram Login → Firebase Custom Token

## Development

### Prerequisites

- Node.js 18+
- Firebase project with Firestore enabled
- Telegram Bot Token

### Setup

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your Firebase and API credentials
```

3. Start dev server:
```bash
npm run dev
```

4. Open http://localhost:5173

### Environment Variables

See `.env.example` for required configuration:

- `VITE_FIREBASE_API_KEY`: Firebase API key
- `VITE_FIREBASE_AUTH_DOMAIN`: Firebase auth domain
- `VITE_FIREBASE_PROJECT_ID`: Firebase project ID
- `VITE_API_URL`: Backend API URL (Modal.com)
- `VITE_TELEGRAM_BOT_NAME`: Telegram bot username

## Building

```bash
npm run build
```

Output in `dist/` directory.

## Deployment

### Vercel

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Deploy:
```bash
vercel --prod
```

3. Configure environment variables in Vercel dashboard

## Project Structure

```
dashboard/
├── src/
│   ├── components/
│   │   ├── common/         # TaskCard, QuickAdd, SyncStatus
│   │   ├── views/          # ListView, KanbanView, CalendarView
│   │   ├── layout/         # Header, Sidebar
│   │   └── ui/             # shadcn/ui components
│   ├── hooks/              # useAuth, useTasks
│   ├── lib/                # firebase, api, utils
│   ├── stores/             # Zustand stores
│   ├── types/              # TypeScript types
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## Backend Integration

Dashboard integrates with Modal.com backend:

- `POST /auth/telegram` - Verify Telegram login, return Firebase token
- `GET /api/sync/status` - Get calendar sync status
- Firebase Firestore `pkm_items/{userId}/items` - Task collection

## License

MIT
