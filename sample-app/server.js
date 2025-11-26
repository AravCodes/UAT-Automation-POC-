import express from 'express'
import cors from 'cors'
import jwt from 'jsonwebtoken'

const app = express()
const PORT = process.env.PORT || 3000
const JWT_SECRET = 'uat-sample-app-secret-key'

app.use(cors())
app.use(express.json())

// In-memory database
let users = [
  {
    id: '1',
    name: 'Admin User',
    email: 'admin@example.com',
    password: 'Admin123!',
    role: 'admin'
  },
  {
    id: '2',
    name: 'Regular User',
    email: 'user@example.com',
    password: 'User123!',
    role: 'user'
  },
  {
    id: '3',
    name: 'Viewer User',
    email: 'viewer@example.com',
    password: 'Viewer123!',
    role: 'viewer'
  },
  {
    id: '4',
    name: 'John Doe',
    email: 'john@example.com',
    password: 'John123!',
    role: 'user'
  },
  {
    id: '5',
    name: 'Jane Smith',
    email: 'jane@example.com',
    password: 'Jane123!',
    role: 'user'
  }
]

let userSettings = {}

// Middleware to verify JWT token
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization']
  const token = authHeader && authHeader.split(' ')[1]

  if (!token) {
    return res.status(401).json({ message: 'Access token required' })
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ message: 'Invalid or expired token' })
    }
    req.user = user
    next()
  })
}

// Auth endpoints
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body

  const user = users.find(u => u.email === email && u.password === password)

  if (!user) {
    return res.status(401).json({ message: 'Invalid credentials' })
  }

  const token = jwt.sign(
    { id: user.id, email: user.email, role: user.role },
    JWT_SECRET,
    { expiresIn: '24h' }
  )

  const { password: _, ...userWithoutPassword } = user

  res.json({
    token,
    user: userWithoutPassword
  })
})

// User management endpoints
app.get('/api/users', authenticateToken, (req, res) => {
  const usersWithoutPasswords = users.map(({ password, ...user }) => user)
  res.json(usersWithoutPasswords)
})

app.post('/api/users', authenticateToken, (req, res) => {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ message: 'Admin access required' })
  }

  const { name, email, role } = req.body

  if (users.find(u => u.email === email)) {
    return res.status(400).json({ message: 'Email already exists' })
  }

  const newUser = {
    id: String(users.length + 1),
    name,
    email,
    password: 'Password123!',
    role: role || 'user'
  }

  users.push(newUser)

  const { password, ...userWithoutPassword } = newUser
  res.status(201).json(userWithoutPassword)
})

app.put('/api/users/:id', authenticateToken, (req, res) => {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ message: 'Admin access required' })
  }

  const { id } = req.params
  const { name, email, role } = req.body

  const userIndex = users.findIndex(u => u.id === id)

  if (userIndex === -1) {
    return res.status(404).json({ message: 'User not found' })
  }

  users[userIndex] = {
    ...users[userIndex],
    name: name || users[userIndex].name,
    email: email || users[userIndex].email,
    role: role || users[userIndex].role
  }

  const { password, ...userWithoutPassword } = users[userIndex]
  res.json(userWithoutPassword)
})

app.delete('/api/users/:id', authenticateToken, (req, res) => {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ message: 'Admin access required' })
  }

  const { id } = req.params

  if (id === req.user.id) {
    return res.status(400).json({ message: 'Cannot delete your own account' })
  }

  const userIndex = users.findIndex(u => u.id === id)

  if (userIndex === -1) {
    return res.status(404).json({ message: 'User not found' })
  }

  users.splice(userIndex, 1)
  res.status(204).send()
})

// Dashboard endpoints
app.get('/api/dashboard/stats', authenticateToken, (req, res) => {
  res.json({
    totalUsers: users.length,
    activeUsers: users.filter(u => u.role !== 'viewer').length,
    pendingTasks: 5,
    completedTasks: 23
  })
})

// Profile endpoints
app.get('/api/profile', authenticateToken, (req, res) => {
  const user = users.find(u => u.id === req.user.id)

  if (!user) {
    return res.status(404).json({ message: 'User not found' })
  }

  const { password, ...userWithoutPassword } = user
  res.json(userWithoutPassword)
})

app.put('/api/profile', authenticateToken, (req, res) => {
  const { name, email } = req.body

  const userIndex = users.findIndex(u => u.id === req.user.id)

  if (userIndex === -1) {
    return res.status(404).json({ message: 'User not found' })
  }

  if (email && email !== users[userIndex].email) {
    if (users.find(u => u.email === email && u.id !== req.user.id)) {
      return res.status(400).json({ message: 'Email already exists' })
    }
  }

  users[userIndex] = {
    ...users[userIndex],
    name: name || users[userIndex].name,
    email: email || users[userIndex].email
  }

  const { password, ...userWithoutPassword } = users[userIndex]
  res.json({ user: userWithoutPassword })
})

app.put('/api/profile/password', authenticateToken, (req, res) => {
  const { currentPassword, newPassword } = req.body

  const userIndex = users.findIndex(u => u.id === req.user.id)

  if (userIndex === -1) {
    return res.status(404).json({ message: 'User not found' })
  }

  if (users[userIndex].password !== currentPassword) {
    return res.status(400).json({ message: 'Current password is incorrect' })
  }

  users[userIndex].password = newPassword
  res.json({ message: 'Password updated successfully' })
})

// Settings endpoints
app.get('/api/settings', authenticateToken, (req, res) => {
  const settings = userSettings[req.user.id] || {
    notifications: {
      email: true,
      push: false,
      sms: false
    },
    display: {
      theme: 'light',
      language: 'en'
    }
  }

  res.json(settings)
})

app.put('/api/settings', authenticateToken, (req, res) => {
  userSettings[req.user.id] = req.body
  res.json({ message: 'Settings saved successfully' })
})

// Account management endpoints
app.post('/api/account/deactivate', authenticateToken, (req, res) => {
  const userIndex = users.findIndex(u => u.id === req.user.id)

  if (userIndex !== -1) {
    users.splice(userIndex, 1)
  }

  res.json({ message: 'Account deactivated successfully' })
})

app.get('/api/account/export', authenticateToken, (req, res) => {
  const user = users.find(u => u.id === req.user.id)

  if (!user) {
    return res.status(404).json({ message: 'User not found' })
  }

  const { password, ...userData } = user
  const settings = userSettings[req.user.id] || {}

  const exportData = {
    user: userData,
    settings,
    exportDate: new Date().toISOString()
  }

  res.setHeader('Content-Type', 'application/json')
  res.setHeader('Content-Disposition', 'attachment; filename=user-data.json')
  res.json(exportData)
})

app.listen(PORT, () => {
  console.log(`Backend API running on http://localhost:${PORT}`)
  console.log('\nSeeded users:')
  users.forEach(u => {
    console.log(`  - ${u.email} / ${u.password} (${u.role})`)
  })
})


