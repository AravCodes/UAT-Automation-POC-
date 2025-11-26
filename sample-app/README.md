# UAT Sample Application

A comprehensive multi-module sample application built with React, Vite, TailwindCSS, and Express for demonstrating UAT automation capabilities.

## Features

- **Login Module**: Email/password authentication with JWT-based session management
- **User Management**: Full CRUD operations with role assignment (Admin, User, Viewer)
- **Dashboard**: User-specific statistics and role-based content visibility
- **Profile**: View/edit profile information and change password
- **Settings**: Notification preferences, display settings, and account management

## Tech Stack

### Frontend
- React 18
- Vite
- TailwindCSS
- React Router DOM

### Backend
- Node.js
- Express
- JWT for authentication
- In-memory database

## Setup Instructions

### Prerequisites
- Node.js 16+ installed
- npm or yarn package manager

### Installation

1. Install dependencies:
```bash
npm install
```

### Running the Application

You need to run both the backend API and the frontend development server:

#### Terminal 1 - Backend API (Port 3000)
```bash
npm run server
```

#### Terminal 2 - Frontend Dev Server (Port 5173)
```bash
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:3000

## Test Credentials

The application comes with pre-seeded test users:

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | Admin123! | admin |
| user@example.com | User123! | user |
| viewer@example.com | Viewer123! | viewer |
| john@example.com | John123! | user |
| jane@example.com | Jane123! | user |

## Test Attributes

All interactive elements include comprehensive `data-testid` attributes for automated testing:

### Login
- `login-email` - Email input field
- `login-password` - Password input field
- `login-submit` - Submit button
- `login-error` - Error message display

### User Management
- `create-user-button` - Create new user button
- `users-table` - Users table
- `user-row-{id}` - User table row
- `edit-user-{id}` - Edit user button
- `delete-user-{id}` - Delete user button
- `user-form-name` - User form name input
- `user-form-email` - User form email input
- `user-form-role` - User form role select
- `user-form-submit` - User form submit button

### Dashboard
- `dashboard-title` - Dashboard page title
- `stat-total-users` - Total users statistic
- `stat-active-users` - Active users statistic
- `nav-card-users` - User management navigation card
- `nav-card-profile` - Profile navigation card
- `nav-card-settings` - Settings navigation card

### Profile
- `profile-edit-button` - Edit profile button
- `profile-form-name` - Profile name input
- `profile-form-email` - Profile email input
- `password-change-button` - Change password button
- `password-form-current` - Current password input
- `password-form-new` - New password input
- `password-form-confirm` - Confirm password input

### Settings
- `notification-email` - Email notification toggle
- `notification-push` - Push notification toggle
- `notification-sms` - SMS notification toggle
- `display-theme` - Theme selector
- `display-language` - Language selector
- `save-settings-button` - Save settings button
- `export-data-button` - Export data button
- `deactivate-account-button` - Deactivate account button

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with email and password

### Users
- `GET /api/users` - Get all users (requires auth)
- `POST /api/users` - Create new user (admin only)
- `PUT /api/users/:id` - Update user (admin only)
- `DELETE /api/users/:id` - Delete user (admin only)

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics

### Profile
- `GET /api/profile` - Get current user profile
- `PUT /api/profile` - Update profile
- `PUT /api/profile/password` - Change password

### Settings
- `GET /api/settings` - Get user settings
- `PUT /api/settings` - Update settings

### Account
- `POST /api/account/deactivate` - Deactivate account
- `GET /api/account/export` - Export user data

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
sample-app/
├── src/
│   ├── components/
│   │   ├── Layout.jsx
│   │   └── ProtectedRoute.jsx
│   ├── context/
│   │   └── AuthContext.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   ├── UserManagement.jsx
│   │   ├── Profile.jsx
│   │   └── Settings.jsx
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── server.js
├── package.json
└── README.md
```

## License

MIT
