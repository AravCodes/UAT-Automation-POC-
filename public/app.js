// API base URL
const API_BASE = '';

// Authentication state
let currentUser = null;

// Check authentication status
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`);
        const data = await response.json();
        if (data.authenticated) {
            currentUser = data.user;
            updateNavigation();
            return true;
        }
        currentUser = null;
        updateNavigation();
        return false;
    } catch (error) {
        console.error('Error checking auth:', error);
        currentUser = null;
        updateNavigation();
        return false;
    }
}

// Update navigation based on auth status
function updateNavigation() {
    const navLinks = document.querySelectorAll('.nav-links');
    navLinks.forEach(nav => {
        // Remove existing auth links
        const existingLogin = nav.querySelector('[data-testid="nav-login"]');
        const existingLogout = nav.querySelector('[data-testid="nav-logout"]');
        const existingUser = nav.querySelector('[data-testid="nav-user"]');
        
        if (existingLogin) existingLogin.remove();
        if (existingLogout) existingLogout.remove();
        if (existingUser) existingUser.remove();
        
        // Add appropriate links
        if (currentUser) {
            const userSpan = document.createElement('span');
            userSpan.setAttribute('data-testid', 'nav-user');
            userSpan.textContent = currentUser.name;
            userSpan.style.marginRight = '1rem';
            userSpan.style.color = 'white';
            
            const logoutLink = document.createElement('a');
            logoutLink.setAttribute('href', '#');
            logoutLink.setAttribute('data-testid', 'nav-logout');
            logoutLink.textContent = 'Logout';
            logoutLink.style.cursor = 'pointer';
            logoutLink.addEventListener('click', async (e) => {
                e.preventDefault();
                await logout();
            });
            
            nav.insertBefore(userSpan, nav.firstChild);
            nav.appendChild(logoutLink);
        } else {
            const loginLink = document.createElement('a');
            loginLink.setAttribute('href', 'login.html');
            loginLink.setAttribute('data-testid', 'nav-login');
            loginLink.textContent = 'Login';
            nav.appendChild(loginLink);
        }
    });
}

// Logout function
async function logout() {
    try {
        const response = await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            currentUser = null;
            updateNavigation();
            if (window.location.pathname.includes('cart.html')) {
                window.location.href = 'index.html';
            } else {
                window.location.reload();
            }
        }
    } catch (error) {
        console.error('Error logging out:', error);
    }
}

// Utility function to update cart count in navigation
async function updateCartCount() {
    try {
        const response = await fetch(`${API_BASE}/cart`, {
            credentials: 'include'
        });
        const cart = await response.json();
        const count = cart.reduce((sum, item) => sum + item.quantity, 0);
        const cartCountElements = document.querySelectorAll('[data-testid="cart-count"]');
        cartCountElements.forEach(el => {
            el.textContent = count;
        });
    } catch (error) {
        console.error('Error updating cart count:', error);
    }
}

// Home Page - Load products
if (window.location.pathname.includes('index.html') || window.location.pathname === '/') {
    async function loadProducts() {
        try {
            const response = await fetch(`${API_BASE}/products`);
            const products = await response.json();
            const container = document.querySelector('[data-testid="products-container"]');
            
            container.innerHTML = products.map(product => `
                <div class="product-card" data-testid="product-card-${product.id}">
                    <img src="${product.image}" alt="${product.name}">
                    <div>
                        <h3 data-testid="product-name-${product.id}">${product.name}</h3>
                        <p class="price" data-testid="product-price-${product.id}">$${product.price.toFixed(2)}</p>
                        <button class="view-button" data-testid="view-button-${product.id}">View Details</button>
                    </div>
                </div>
            `).join('');

            // Add click event listeners to view buttons
            products.forEach(product => {
                const viewButton = document.querySelector(`[data-testid="view-button-${product.id}"]`);
                viewButton.addEventListener('click', () => {
                    window.location.href = `product.html?id=${product.id}`;
                });
            });
        } catch (error) {
            console.error('Error loading products:', error);
        }
    }

    loadProducts();
    updateCartCount();
}

// Product Page - Load product details
if (window.location.pathname.includes('product.html')) {
    async function loadProductDetails() {
        const urlParams = new URLSearchParams(window.location.search);
        const productId = urlParams.get('id');

        if (!productId) {
            window.location.href = 'index.html';
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/product/${productId}`);
            const product = await response.json();

            document.querySelector('[data-testid="product-image"]').src = product.image;
            document.querySelector('[data-testid="product-image"]').alt = product.name;
            document.querySelector('[data-testid="product-title"]').textContent = product.name;
            document.querySelector('[data-testid="product-description"]').textContent = product.description;
            document.querySelector('[data-testid="product-price"]').textContent = `$${product.price.toFixed(2)}`;

            // Add to cart functionality
            const addToCartButton = document.querySelector('[data-testid="add-to-cart-button"]');
            addToCartButton.addEventListener('click', async () => {
                const quantityInput = document.querySelector('[data-testid="quantity-input"]');
                const quantity = parseInt(quantityInput.value) || 1;

                try {
                    const response = await fetch(`${API_BASE}/cart/add`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        credentials: 'include',
                        body: JSON.stringify({
                            productId: product.id,
                            quantity: quantity
                        })
                    });

                    if (response.ok) {
                        alert('Item added to cart!');
                        updateCartCount();
                    } else {
                        alert('Error adding item to cart');
                    }
                } catch (error) {
                    console.error('Error adding to cart:', error);
                    alert('Error adding item to cart');
                }
            });
        } catch (error) {
            console.error('Error loading product details:', error);
            window.location.href = 'index.html';
        }
    }

    loadProductDetails();
    updateCartCount();
}

// Cart Page - Load cart items
if (window.location.pathname.includes('cart.html')) {
    async function loadCart() {
        try {
            const response = await fetch(`${API_BASE}/cart`, {
                credentials: 'include'
            });
            const cart = await response.json();

            const emptyMessage = document.querySelector('[data-testid="empty-cart-message"]');
            const cartTable = document.querySelector('[data-testid="cart-table"]');
            const cartItems = document.querySelector('[data-testid="cart-items"]');
            const checkoutSection = document.querySelector('[data-testid="checkout-section"]');
            const cartTotal = document.querySelector('[data-testid="cart-total"]');

            if (cart.length === 0) {
                emptyMessage.style.display = 'block';
                cartTable.style.display = 'none';
                checkoutSection.style.display = 'none';
            } else {
                emptyMessage.style.display = 'none';
                cartTable.style.display = 'table';
                checkoutSection.style.display = 'block';

                cartItems.innerHTML = cart.map(item => `
                    <tr class="cart-item-row" data-testid="cart-item-${item.id}">
                        <td data-testid="cart-item-name-${item.id}">${item.name}</td>
                        <td data-testid="cart-item-price-${item.id}">$${item.price.toFixed(2)}</td>
                        <td data-testid="cart-item-qty-${item.id}">${item.quantity}</td>
                        <td>$${(item.price * item.quantity).toFixed(2)}</td>
                        <td>
                            <button class="remove-button" data-testid="remove-item-${item.id}">Remove</button>
                        </td>
                    </tr>
                `).join('');

                // Calculate total
                const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
                cartTotal.textContent = `$${total.toFixed(2)}`;

                // Add event listeners to remove buttons
                cart.forEach(item => {
                    const removeButton = document.querySelector(`[data-testid="remove-item-${item.id}"]`);
                    removeButton.addEventListener('click', async () => {
                        try {
                            const response = await fetch(`${API_BASE}/cart/remove`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                credentials: 'include',
                                body: JSON.stringify({
                                    productId: item.id
                                })
                            });

                            if (response.ok) {
                                loadCart();
                                updateCartCount();
                            } else {
                                alert('Error removing item from cart');
                            }
                        } catch (error) {
                            console.error('Error removing from cart:', error);
                            alert('Error removing item from cart');
                        }
                    });
                });
            }
        } catch (error) {
            console.error('Error loading cart:', error);
        }
    }

    // Checkout button functionality
    const checkoutButton = document.querySelector('[data-testid="checkout-button"]');
    if (checkoutButton) {
        checkoutButton.addEventListener('click', () => {
            alert('Checkout functionality would be implemented here!');
        });
    }

    loadCart();
    updateCartCount();
}

// Login Page
if (window.location.pathname.includes('login.html')) {
    const loginForm = document.querySelector('[data-testid="login-form"]');
    const errorMessage = document.querySelector('[data-testid="login-error-message"]');
    
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.querySelector('[data-testid="email-input"]').value;
            const password = document.querySelector('[data-testid="password-input"]').value;
            
            try {
                const response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({ email, password })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Redirect to home page
                    window.location.href = 'index.html';
                } else {
                    errorMessage.textContent = data.error || 'Login failed. Please try again.';
                    errorMessage.style.display = 'block';
                }
            } catch (error) {
                console.error('Error logging in:', error);
                errorMessage.textContent = 'An error occurred. Please try again.';
                errorMessage.style.display = 'block';
            }
        });
    }
    
    checkAuth().then(isAuthenticated => {
        if (isAuthenticated) {
            window.location.href = 'index.html';
        }
    });
    updateCartCount();
}

// Signup Page
if (window.location.pathname.includes('signup.html')) {
    const signupForm = document.querySelector('[data-testid="signup-form"]');
    const errorMessage = document.querySelector('[data-testid="signup-error-message"]');
    
    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const name = document.querySelector('[data-testid="name-input"]').value;
            const email = document.querySelector('[data-testid="email-input"]').value;
            const password = document.querySelector('[data-testid="password-input"]').value;
            
            try {
                const response = await fetch(`${API_BASE}/auth/signup`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({ name, email, password })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // Redirect to home page
                    window.location.href = 'index.html';
                } else {
                    errorMessage.textContent = data.error || 'Signup failed. Please try again.';
                    errorMessage.style.display = 'block';
                }
            } catch (error) {
                console.error('Error signing up:', error);
                errorMessage.textContent = 'An error occurred. Please try again.';
                errorMessage.style.display = 'block';
            }
        });
    }
    
    checkAuth().then(isAuthenticated => {
        if (isAuthenticated) {
            window.location.href = 'index.html';
        }
    });
    updateCartCount();
}

// Update cart count on all pages and check auth
checkAuth();
updateCartCount();

