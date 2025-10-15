import express from 'express'
import bodyParser from 'body-parser'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
app.use(bodyParser.urlencoded({ extended: false }))
app.use(express.static(path.join(__dirname, 'public')))

const PORT = process.env.PORT || 5173

// In-memory user
const VALID_EMAIL = 'user@example.com'
const VALID_PASSWORD = 'Password123!'

app.get('/', (req, res) => {
  res.redirect('/login')
})

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'login.html'))
})

app.post('/login', (req, res) => {
  const { email, password } = req.body
  if (email === VALID_EMAIL && password === VALID_PASSWORD) {
    return res.redirect('/dashboard?welcome=1')
  }
  return res.redirect('/login?error=1')
})

app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'))
})

app.listen(PORT, () => {
  console.log(`Sample app running on http://localhost:${PORT}`)
})


