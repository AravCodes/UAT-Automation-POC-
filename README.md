# E-Commerce Web Application

A complete sample e-commerce web application built for testing purposes with stable `data-testid` attributes on all interactive elements.

## Tech Stack

- **Frontend**: HTML + CSS + Vanilla JavaScript
- **Backend**: Node.js + Express

## Project Structure

```
ecommerce-app/
├── server.js          # Express server with API endpoints
├── package.json       # Dependencies
├── public/
│   ├── index.html    # Home page with product listing
│   ├── product.html  # Product details page
│   ├── cart.html     # Shopping cart page
│   ├── login.html    # Login page
│   ├── signup.html   # Sign up page
│   ├── styles.css    # Styling
│   └── app.js        # Frontend JavaScript logic
└── README.md
```

## Installation

1. Install dependencies:
```bash
npm install
```

## Running the Application

1. Start the server:
```bash
npm start
```

2. Open your browser and navigate to:
```
http://localhost:3000
```

## Features

### Authentication
- **Login Page** (`login.html`)
  - User login with email and password
  - Validates credentials against stored users
  - Elements include:
    - `data-testid="login-form"`
    - `data-testid="email-input"`
    - `data-testid="password-input"`
    - `data-testid="login-submit-button"`
    - `data-testid="login-error-message"`
    - `data-testid="signup-link"`

- **Sign Up Page** (`signup.html`)
  - User registration with name, email, and password
  - Checks for duplicate emails
  - Elements include:
    - `data-testid="signup-form"`
    - `data-testid="name-input"`
    - `data-testid="email-input"`
    - `data-testid="password-input"`
    - `data-testid="signup-submit-button"`
    - `data-testid="signup-error-message"`
    - `data-testid="login-link"`

- **Session Management**
  - Express sessions for user authentication
  - Per-user cart storage
  - Navigation shows user name and logout when authenticated
  - Navigation shows login link when not authenticated

### Home Page (`index.html`)
- Displays 6 sample products
- Each product card has:
  - `data-testid="product-card-{id}"`
  - `data-testid="product-name-{id}"`
  - `data-testid="product-price-{id}"`
  - `data-testid="view-button-{id}"`

### Product Page (`product.html`)
- Shows detailed product information
- Elements include:
  - `data-testid="product-image"`
  - `data-testid="product-title"`
  - `data-testid="product-description"`
  - `data-testid="product-price"`
  - `data-testid="quantity-input"`
  - `data-testid="add-to-cart-button"`

### Cart Page (`cart.html`)
- Displays items in the shopping cart
- Elements include:
  - `data-testid="cart-item-{id}"`
  - `data-testid="cart-item-name-{id}"`
  - `data-testid="cart-item-price-{id}"`
  - `data-testid="cart-item-qty-{id}"`
  - `data-testid="remove-item-{id}"`
  - `data-testid="checkout-button"`
  - `data-testid="empty-cart-message"`

## API Endpoints

### Product Endpoints
- `GET /products` - Returns all products
- `GET /product/:id` - Returns product details by ID

### Authentication Endpoints
- `POST /auth/signup` - Register new user (body: `{ name, email, password }`)
- `POST /auth/login` - Authenticate user (body: `{ email, password }`)
- `POST /auth/logout` - Logout current user
- `GET /auth/me` - Get current authenticated user

### Cart Endpoints
- `POST /cart/add` - Adds item to cart (body: `{ productId, quantity }`)
- `GET /cart` - Returns current cart items (per user session)
- `POST /cart/remove` - Removes item from cart (body: `{ productId }`)

## Sample User Credentials

For testing purposes, a sample user is pre-configured:
- **Email**: `test@example.com`
- **Password**: `password123`

You can also create new accounts using the sign-up page.

## Testing

All interactive elements include stable `data-testid` attributes for easy testing with tools like:
- Cypress
- Playwright
- Selenium
- Jest with testing-library

