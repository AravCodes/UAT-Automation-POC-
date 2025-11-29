const express = require('express');
const session = require('express-session');
const cors = require('cors');
const path = require('path');
const app = express();
const PORT = 3000;

// Middleware
app.use(cors({
    origin: true,
    credentials: true
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static('public'));

// Session configuration
app.use(session({
  secret: 'ecommerce-secret-key-change-in-production',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false, maxAge: 24 * 60 * 60 * 1000 } // 24 hours
}));

// Sample product data
const products = [
  {
    id: 1,
    name: "Wireless Headphones",
    price: 79.99,
    description: "High-quality wireless headphones with noise cancellation and 30-hour battery life.",
    image: "https://via.placeholder.com/400x300?text=Wireless+Headphones"
  },
  {
    id: 2,
    name: "Smart Watch",
    price: 199.99,
    description: "Feature-rich smartwatch with fitness tracking, heart rate monitor, and smartphone notifications.",
    image: "https://via.placeholder.com/400x300?text=Smart+Watch"
  },
  {
    id: 3,
    name: "Laptop Stand",
    price: 49.99,
    description: "Ergonomic aluminum laptop stand with adjustable height and ventilation.",
    image: "https://via.placeholder.com/400x300?text=Laptop+Stand"
  },
  {
    id: 4,
    name: "Mechanical Keyboard",
    price: 129.99,
    description: "RGB backlit mechanical keyboard with Cherry MX switches and programmable keys.",
    image: "https://via.placeholder.com/400x300?text=Mechanical+Keyboard"
  },
  {
    id: 5,
    name: "USB-C Hub",
    price: 39.99,
    description: "Multi-port USB-C hub with HDMI, USB 3.0, and SD card reader support.",
    image: "https://via.placeholder.com/400x300?text=USB-C+Hub"
  },
  {
    id: 6,
    name: "Wireless Mouse",
    price: 29.99,
    description: "Ergonomic wireless mouse with precision tracking and long battery life.",
    image: "https://via.placeholder.com/400x300?text=Wireless+Mouse"
  }
];

// In-memory storage
let cart = {}; // Object to store carts per user (userId -> cart array)
let users = [
  // Sample user for testing: email: test@example.com, password: password123
  {
    id: 1,
    email: 'test@example.com',
    password: 'password123', // In production, this should be hashed
    name: 'Test User'
  }
];

// Helper function to get user cart (per user session)
function getUserCart(userId) {
  if (!cart[userId]) {
    cart[userId] = [];
  }
  return cart[userId];
}

// API Routes

// GET /products - return all products
app.get('/products', (req, res) => {
  res.json(products);
});

// GET /product/:id - return product details
app.get('/product/:id', (req, res) => {
  const productId = parseInt(req.params.id);
  const product = products.find(p => p.id === productId);
  
  if (product) {
    res.json(product);
  } else {
    res.status(404).json({ error: 'Product not found' });
  }
});

// Authentication Routes

// POST /auth/signup - register new user
app.post('/auth/signup', (req, res) => {
  const { email, password, name } = req.body;
  
  if (!email || !password || !name) {
    return res.status(400).json({ error: 'Email, password, and name are required' });
  }
  
  // Check if user already exists
  const existingUser = users.find(u => u.email === email);
  if (existingUser) {
    return res.status(400).json({ error: 'User with this email already exists' });
  }
  
  // Create new user (in production, hash the password)
  const newUser = {
    id: users.length + 1,
    email: email,
    password: password, // In production, use bcrypt to hash
    name: name
  };
  
  users.push(newUser);
  
  // Set session
  req.session.userId = newUser.id;
  req.session.userEmail = newUser.email;
  req.session.userName = newUser.name;
  
  res.json({ 
    success: true, 
    user: { id: newUser.id, email: newUser.email, name: newUser.name } 
  });
});

// POST /auth/login - authenticate user
app.post('/auth/login', (req, res) => {
  const { email, password } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }
  
  // Find user and verify credentials
  const user = users.find(u => u.email === email);
  
  if (!user || user.password !== password) {
    return res.status(401).json({ error: 'Invalid email or password' });
  }
  
  // Set session
  req.session.userId = user.id;
  req.session.userEmail = user.email;
  req.session.userName = user.name;
  
  res.json({ 
    success: true, 
    user: { id: user.id, email: user.email, name: user.name } 
  });
});

// POST /auth/logout - logout user
app.post('/auth/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({ error: 'Error logging out' });
    }
    res.json({ success: true });
  });
});

// GET /auth/me - get current user
app.get('/auth/me', (req, res) => {
  if (req.session.userId) {
    const user = users.find(u => u.id === req.session.userId);
    if (user) {
      return res.json({ 
        authenticated: true,
        user: { id: user.id, email: user.email, name: user.name } 
      });
    }
  }
  res.json({ authenticated: false });
});

// Cart Routes (now per user)

// POST /cart/add - add item to cart
app.post('/cart/add', (req, res) => {
  const userId = req.session.userId || 'guest';
  const { productId, quantity } = req.body;
  const product = products.find(p => p.id === productId);
  
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }
  
  const userCart = getUserCart(userId);
  const existingItem = userCart.find(item => item.id === productId);
  
  if (existingItem) {
    existingItem.quantity += quantity || 1;
  } else {
    userCart.push({
      id: product.id,
      name: product.name,
      price: product.price,
      quantity: quantity || 1
    });
  }
  
  res.json({ success: true, cart: userCart });
});

// GET /cart - return cart items
app.get('/cart', (req, res) => {
  const userId = req.session.userId || 'guest';
  const userCart = getUserCart(userId);
  res.json(userCart);
});

// POST /cart/remove - remove item from cart
app.post('/cart/remove', (req, res) => {
  const userId = req.session.userId || 'guest';
  const { productId } = req.body;
  const userCart = getUserCart(userId);
  const updatedCart = userCart.filter(item => item.id !== productId);
  cart[userId] = updatedCart;
  res.json({ success: true, cart: updatedCart });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

