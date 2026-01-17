"""Dashboard HTML templates."""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SafetyVision - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f0f1a', 800: '#1a1a2e', 700: '#252542', 600: '#2f2f4a' },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
    </style>
</head>
<body class="text-white min-h-screen flex items-center justify-center">
    <div class="w-full max-w-md p-8">
        <div class="text-center mb-8">
            <div class="w-16 h-16 bg-accent rounded-2xl flex items-center justify-center mx-auto mb-4">
                <svg class="w-10 h-10 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                    <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                </svg>
            </div>
            <h1 class="text-3xl font-bold">SafetyVision</h1>
            <p class="text-gray-400 mt-2">AI-Powered Safety Monitoring</p>
        </div>

        <input type="hidden" id="auth-mode" value="login">

        <div id="login-form" class="bg-dark-800 rounded-xl p-6 border border-dark-600">
            <h2 id="form-title" class="text-xl font-semibold mb-6">Sign In</h2>

            <div id="error-message" class="hidden bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg mb-4"></div>

            <!-- Register-only fields -->
            <div id="register-fields" class="hidden space-y-4 mb-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-2">Organization Name</label>
                    <input type="text" id="org-name" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="Acme Construction">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-2">Full Name</label>
                    <input type="text" id="full-name" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="John Smith">
                </div>
            </div>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-2">Email</label>
                    <input type="email" id="email" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="you@company.com">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-2">Password</label>
                    <input type="password" id="password" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="••••••••">
                </div>
            </div>

            <button id="submit-btn" onclick="submitAuth()" class="w-full bg-accent text-dark-900 font-semibold py-3 rounded-lg mt-6 hover:bg-opacity-90 transition">
                Sign In
            </button>

            <p id="toggle-text" class="text-center text-gray-400 mt-4">
                Don't have an account? <a href="#" onclick="toggleMode()" class="text-accent hover:underline">Register</a>
            </p>
        </div>
    </div>

    <script>
        const mode = document.getElementById('auth-mode').value;
        if (mode === 'register') {
            toggleMode();
        }

        function toggleMode() {
            const authMode = document.getElementById('auth-mode');
            const registerFields = document.getElementById('register-fields');
            const formTitle = document.getElementById('form-title');
            const submitBtn = document.getElementById('submit-btn');
            const toggleText = document.getElementById('toggle-text');

            if (authMode.value === 'login') {
                authMode.value = 'register';
                registerFields.classList.remove('hidden');
                formTitle.textContent = 'Create Account';
                submitBtn.textContent = 'Create Account';
                toggleText.innerHTML = 'Already have an account? <a href="#" onclick="toggleMode()" class="text-accent hover:underline">Sign In</a>';
            } else {
                authMode.value = 'login';
                registerFields.classList.add('hidden');
                formTitle.textContent = 'Sign In';
                submitBtn.textContent = 'Sign In';
                toggleText.innerHTML = 'Don\\'t have an account? <a href="#" onclick="toggleMode()" class="text-accent hover:underline">Register</a>';
            }
        }

        async function submitAuth() {
            const authMode = document.getElementById('auth-mode').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error-message');

            errorDiv.classList.add('hidden');

            try {
                let response;
                if (authMode === 'login') {
                    response = await fetch('/api/v1/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({ email, password })
                    });
                } else {
                    const orgName = document.getElementById('org-name').value;
                    const fullName = document.getElementById('full-name').value;
                    response = await fetch('/api/v1/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            organization_name: orgName,
                            email,
                            password,
                            full_name: fullName
                        })
                    });
                }

                if (response.ok) {
                    window.location.href = '/dashboard';
                } else {
                    const data = await response.json();
                    errorDiv.textContent = data.detail || 'Authentication failed';
                    errorDiv.classList.remove('hidden');
                }
            } catch (e) {
                errorDiv.textContent = 'Connection error. Please try again.';
                errorDiv.classList.remove('hidden');
            }
        }

        // Handle Enter key
        document.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitAuth();
        });
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SafetyVision - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f0f1a', 800: '#1a1a2e', 700: '#252542', 600: '#2f2f4a' },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
        .sidebar { background-color: #1a1a2e; }
        .card { background-color: #1a1a2e; border: 1px solid #2f2f4a; }
        .camera-feed { border: 2px solid #2f2f4a; border-radius: 8px; overflow: hidden; }
        .zone-tag { font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
        .zone-warehouse { background-color: rgba(255, 165, 0, 0.2); color: #ffa500; }
        .zone-production { background-color: rgba(0, 255, 0, 0.2); color: #00ff00; }
        .zone-common { background-color: rgba(0, 255, 255, 0.2); color: #00ffff; }
        .toast {
            position: fixed; bottom: 20px; right: 20px;
            background: #ff4444; color: white; padding: 16px 24px;
            border-radius: 8px; animation: slideIn 0.3s ease; z-index: 1000;
        }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .event-item { border-left: 3px solid #ff4444; padding-left: 12px; margin-bottom: 12px; }
        .event-item.warning { border-color: #ffaa00; }
    </style>
</head>
<body class="text-white min-h-screen">
    <div class="flex">
        <!-- Sidebar -->
        <nav class="sidebar w-64 min-h-screen p-4 fixed left-0 top-0">
            <div class="flex items-center gap-3 mb-8">
                <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                </div>
                <span class="text-xl font-semibold">SafetyVision</span>
            </div>

            <div class="space-y-2">
                <a href="/dashboard" class="flex items-center gap-3 p-3 bg-dark-700 rounded-lg text-accent">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 6a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
                    </svg>
                    Dashboard
                </a>
                <a href="/live" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/>
                    </svg>
                    Live View
                </a>
                <a href="/cameras/setup" id="camera-setup-link" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                        <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"/>
                    </svg>
                    Camera Setup
                </a>
                <a href="/docs" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"/>
                    </svg>
                    API Docs
                </a>
            </div>

            <div class="absolute bottom-4 left-4 right-4">
                <button onclick="logout()" class="w-full flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7z"/>
                    </svg>
                    Logout
                </button>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="ml-64 flex-1 p-6">
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-bold">Dashboard</h1>
                <div class="flex items-center gap-4">
                    <span id="datetime" class="text-gray-400"></span>
                    <span id="user-info" class="text-gray-400"></span>
                </div>
            </div>

            <!-- Stats Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">Violations Today</p>
                            <p id="violations-count" class="text-4xl font-bold">0</p>
                            <p id="violations-change" class="text-sm text-gray-400 mt-1"></p>
                        </div>
                        <div class="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                            </svg>
                        </div>
                    </div>
                </div>
                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">Active Cameras</p>
                            <p class="text-4xl font-bold">
                                <span id="active-cameras">0</span>
                                <span class="text-gray-500 text-2xl">/ <span id="total-cameras">0</span></span>
                            </p>
                            <p class="text-sm text-green-400 mt-1">All systems online</p>
                        </div>
                        <div class="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zm12.553 1.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z"/>
                            </svg>
                        </div>
                    </div>
                </div>
                <div class="card p-6 rounded-xl">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-gray-400 text-sm mb-1">AI Processing</p>
                            <p id="ai-scanned" class="text-4xl font-bold">0</p>
                            <p class="text-sm text-accent mt-1">Frames analyzed</p>
                        </div>
                        <div class="w-12 h-12 bg-accent/20 rounded-lg flex items-center justify-center">
                            <svg class="w-6 h-6 text-accent" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M13 7H7v6h6V7z"/>
                                <path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2z"/>
                            </svg>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Camera Grid & Activity -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div class="card rounded-xl overflow-hidden">
                    <div class="p-4 border-b border-dark-600">
                        <h2 class="text-xl font-semibold">Live Cameras</h2>
                    </div>
                    <div id="camera-grid" class="grid grid-cols-2 gap-4 p-4">
                        <p class="text-gray-500 col-span-2 text-center py-8">Loading cameras...</p>
                    </div>
                </div>

                <div class="card rounded-xl">
                    <div class="p-4 border-b border-dark-600 flex justify-between items-center">
                        <h2 class="text-xl font-semibold">Recent Activity</h2>
                        <button onclick="acknowledgeAll()" class="text-accent text-sm hover:underline">Mark all read</button>
                    </div>
                    <div id="activity-feed" class="p-4 max-h-96 overflow-y-auto">
                        <p class="text-gray-500 text-center py-8">No recent events</p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <div id="toast-container"></div>

    <script>
        // Update datetime
        function updateDateTime() {
            const now = new Date();
            document.getElementById('datetime').textContent = now.toLocaleString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();

        // API helper with credentials
        async function api(path, options = {}) {
            const response = await fetch(path, {
                ...options,
                credentials: 'include',
                headers: { 'Content-Type': 'application/json', ...options.headers }
            });
            if (response.status === 401) {
                window.location.href = '/login';
                return null;
            }
            return response;
        }

        // Fetch user info
        async function fetchUser() {
            try {
                const response = await api('/api/v1/auth/me');
                if (response && response.ok) {
                    const user = await response.json();
                    document.getElementById('user-info').textContent = user.full_name;
                }
            } catch (e) {
                console.error('Failed to fetch user:', e);
            }
        }

        // Fetch stats
        async function fetchStats() {
            try {
                const response = await api('/api/v1/stats/summary');
                if (!response || !response.ok) return;
                const data = await response.json();

                document.getElementById('violations-count').textContent = data.violations_today;
                document.getElementById('active-cameras').textContent = data.active_cameras;
                document.getElementById('total-cameras').textContent = data.total_cameras;
                document.getElementById('ai-scanned').textContent = data.ai_scanned.toLocaleString();

                const changeEl = document.getElementById('violations-change');
                if (data.violations_change_percent > 0) {
                    changeEl.textContent = `+${data.violations_change_percent}% from yesterday`;
                    changeEl.className = 'text-sm text-red-400 mt-1';
                } else if (data.violations_change_percent < 0) {
                    changeEl.textContent = `${data.violations_change_percent}% from yesterday`;
                    changeEl.className = 'text-sm text-green-400 mt-1';
                } else {
                    changeEl.textContent = 'Same as yesterday';
                    changeEl.className = 'text-sm text-gray-400 mt-1';
                }
            } catch (e) {
                console.error('Failed to fetch stats:', e);
            }
        }

        // Fetch cameras
        async function fetchCameras() {
            try {
                const response = await api('/api/v1/cameras');
                if (!response || !response.ok) return;
                const data = await response.json();

                const grid = document.getElementById('camera-grid');
                if (data.cameras.length === 0) {
                    grid.innerHTML = '<p class="text-gray-500 col-span-2 text-center py-8">No cameras configured</p>';
                    return;
                }

                grid.innerHTML = data.cameras.map(cam => `
                    <div class="camera-feed relative">
                        <img src="/api/v1/stream/${cam.id}" alt="${cam.name}" class="w-full aspect-video object-cover bg-dark-900">
                        <div class="absolute top-2 left-2 flex items-center gap-2">
                            <span class="zone-tag zone-${cam.zone.toLowerCase()}">${cam.zone}</span>
                        </div>
                        <div class="absolute bottom-2 left-2 right-2 flex justify-between items-center">
                            <span class="text-sm font-medium">${cam.name}</span>
                            <span class="text-xs text-gray-400">${cam.fps.toFixed(1)} FPS</span>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch cameras:', e);
            }
        }

        // Fetch events
        async function fetchEvents() {
            try {
                const response = await api('/api/v1/events/live?limit=10');
                if (!response || !response.ok) return;
                const data = await response.json();

                const feed = document.getElementById('activity-feed');
                if (data.events.length === 0) {
                    feed.innerHTML = '<p class="text-gray-500 text-center py-8">No recent events</p>';
                } else {
                    feed.innerHTML = data.events.map(event => `
                        <div class="event-item ${event.severity}">
                            <div class="flex items-start gap-3">
                                <div class="w-8 h-8 bg-red-500/20 rounded flex items-center justify-center flex-shrink-0">
                                    <svg class="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                                    </svg>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <p class="text-sm font-medium">${event.message}</p>
                                    <p class="text-xs text-gray-500">${new Date(event.timestamp).toLocaleTimeString()}</p>
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Failed to fetch events:', e);
            }
        }

        // Acknowledge all
        async function acknowledgeAll() {
            await api('/api/v1/events/acknowledge-all', { method: 'POST' });
            fetchEvents();
        }

        // Logout
        async function logout() {
            await api('/api/v1/auth/logout', { method: 'POST' });
            window.location.href = '/login';
        }

        // Show toast
        function showToast(message) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.innerHTML = `
                <div class="flex items-center gap-3">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92z"/>
                    </svg>
                    <span>${message}</span>
                </div>
            `;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }

        // SSE for real-time events
        const eventSource = new EventSource('/api/v1/sse/events', { withCredentials: true });
        eventSource.addEventListener('violation', (e) => {
            const data = JSON.parse(e.data);
            showToast(data.message);
            fetchEvents();
            fetchStats();
        });

        // Initial fetch
        fetchUser();
        fetchStats();
        fetchCameras();
        fetchEvents();

        // Periodic refresh
        setInterval(fetchStats, 10000);
        setInterval(fetchEvents, 5000);
    </script>
</body>
</html>
"""

LIVE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SafetyVision - Live View</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f0f1a', 800: '#1a1a2e', 700: '#252542', 600: '#2f2f4a' },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
        .sidebar { background-color: #1a1a2e; }
        .camera-feed { border: 2px solid #2f2f4a; border-radius: 8px; overflow: hidden; position: relative; }
        .camera-feed:hover { border-color: #00d4aa; }
        .zone-tag { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; }
        .zone-warehouse { background-color: rgba(255, 165, 0, 0.3); color: #ffa500; }
        .zone-production { background-color: rgba(0, 255, 0, 0.3); color: #00ff00; }
        .zone-common { background-color: rgba(0, 255, 255, 0.3); color: #00ffff; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #00ff00; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body class="text-white min-h-screen">
    <div class="flex">
        <nav class="sidebar w-64 min-h-screen p-4 fixed left-0 top-0">
            <div class="flex items-center gap-3 mb-8">
                <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                </div>
                <span class="text-xl font-semibold">SafetyVision</span>
            </div>

            <div class="space-y-2">
                <a href="/dashboard" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 6a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
                    </svg>
                    Dashboard
                </a>
                <a href="/live" class="flex items-center gap-3 p-3 bg-dark-700 rounded-lg text-accent">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/>
                    </svg>
                    Live View
                </a>
                <a href="/cameras/setup" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                        <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"/>
                    </svg>
                    Camera Setup
                </a>
            </div>

            <div class="absolute bottom-4 left-4 right-4">
                <button onclick="logout()" class="w-full flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7z"/>
                    </svg>
                    Logout
                </button>
            </div>
        </nav>

        <main class="ml-64 flex-1 p-6">
            <div class="flex justify-between items-center mb-6">
                <div>
                    <h1 class="text-3xl font-bold">Live View</h1>
                    <p class="text-gray-400 mt-1">Real-time camera feeds with AI detection</p>
                </div>
                <div class="flex items-center gap-4">
                    <select id="layout-select" class="bg-dark-700 border border-dark-600 rounded-lg px-4 py-2">
                        <option value="2x2">2x2 Grid</option>
                        <option value="3x2">3x2 Grid</option>
                        <option value="1x1">Single View</option>
                    </select>
                    <span id="datetime" class="text-gray-400"></span>
                </div>
            </div>

            <div id="camera-grid" class="grid grid-cols-2 gap-6"></div>
        </main>
    </div>

    <script>
        function updateDateTime() {
            const now = new Date();
            document.getElementById('datetime').textContent = now.toLocaleString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();

        async function fetchCameras() {
            try {
                const response = await fetch('/api/v1/cameras', { credentials: 'include' });
                if (response.status === 401) {
                    window.location.href = '/login';
                    return;
                }
                const data = await response.json();

                const grid = document.getElementById('camera-grid');
                if (data.cameras.length === 0) {
                    grid.innerHTML = '<p class="text-gray-500 col-span-2 text-center py-8">No cameras configured</p>';
                    return;
                }

                grid.innerHTML = data.cameras.map(cam => `
                    <div class="camera-feed">
                        <img src="/api/v1/stream/${cam.id}" alt="${cam.name}" class="w-full aspect-video object-cover bg-dark-900">
                        <div class="absolute top-3 left-3 flex items-center gap-2">
                            <div class="status-dot"></div>
                            <span class="zone-tag zone-${cam.zone.toLowerCase()}">${cam.zone}</span>
                        </div>
                        <div class="absolute top-3 right-3 bg-black/50 px-2 py-1 rounded text-xs">
                            ${cam.fps.toFixed(1)} FPS
                        </div>
                        <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
                            <h3 class="font-semibold">${cam.name}</h3>
                            <p class="text-sm text-gray-400">Camera ${cam.id.substring(0, 8)}</p>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to fetch cameras:', e);
            }
        }

        document.getElementById('layout-select').addEventListener('change', (e) => {
            const grid = document.getElementById('camera-grid');
            switch (e.target.value) {
                case '1x1': grid.className = 'grid grid-cols-1 gap-6'; break;
                case '2x2': grid.className = 'grid grid-cols-2 gap-6'; break;
                case '3x2': grid.className = 'grid grid-cols-3 gap-6'; break;
            }
        });

        async function logout() {
            await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
            window.location.href = '/login';
        }

        fetchCameras();
    </script>
</body>
</html>
"""

CAMERA_SETUP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SafetyVision - Camera Setup</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f0f1a', 800: '#1a1a2e', 700: '#252542', 600: '#2f2f4a' },
                        accent: '#00d4aa',
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0f0f1a; }
        .sidebar { background-color: #1a1a2e; }
        .camera-card { background-color: #1a1a2e; border: 1px solid #2f2f4a; }
        .camera-card:hover { border-color: #00d4aa; }
    </style>
</head>
<body class="text-white min-h-screen">
    <div class="flex">
        <nav class="sidebar w-64 min-h-screen p-4 fixed left-0 top-0">
            <div class="flex items-center gap-3 mb-8">
                <div class="w-10 h-10 bg-accent rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-dark-900" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                </div>
                <span class="text-xl font-semibold">SafetyVision</span>
            </div>

            <div class="space-y-2">
                <a href="/dashboard" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 6a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zm11-1a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
                    </svg>
                    Dashboard
                </a>
                <a href="/live" class="flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/>
                    </svg>
                    Live View
                </a>
                <a href="/cameras/setup" class="flex items-center gap-3 p-3 bg-dark-700 rounded-lg text-accent">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                        <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"/>
                    </svg>
                    Camera Setup
                </a>
            </div>

            <div class="absolute bottom-4 left-4 right-4">
                <button onclick="logout()" class="w-full flex items-center gap-3 p-3 hover:bg-dark-700 rounded-lg text-gray-400 hover:text-white transition">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7z"/>
                    </svg>
                    Logout
                </button>
            </div>
        </nav>

        <main class="ml-64 flex-1 p-6">
            <div class="flex justify-between items-center mb-6">
                <div>
                    <h1 class="text-3xl font-bold">Camera Setup</h1>
                    <p class="text-gray-400 mt-1">Configure and manage your camera feeds</p>
                </div>
                <button onclick="showAddModal()" class="bg-accent text-dark-900 px-4 py-2 rounded-lg font-medium hover:bg-accent/90 transition flex items-center gap-2">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z"/>
                    </svg>
                    Add Camera
                </button>
            </div>

            <div id="camera-list" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <p class="text-gray-500 col-span-full text-center py-8">Loading cameras...</p>
            </div>
        </main>
    </div>

    <!-- Add/Edit Camera Modal -->
    <div id="camera-modal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50">
        <div class="bg-dark-800 rounded-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <h2 id="modal-title" class="text-xl font-semibold mb-6">Add Camera</h2>

            <div id="modal-error" class="hidden bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg mb-4"></div>

            <input type="hidden" id="camera-id">

            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-2">Camera Name</label>
                    <input type="text" id="camera-name" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="e.g., Entrance Camera">
                </div>

                <div>
                    <label class="block text-sm text-gray-400 mb-2">Zone</label>
                    <input type="text" id="camera-zone" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="e.g., Production, Warehouse">
                </div>

                <div>
                    <label class="block text-sm text-gray-400 mb-2">Source Type</label>
                    <select id="source-type" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" onchange="toggleSourceFields()">
                        <option value="rtsp">RTSP Stream</option>
                        <option value="file">Demo/Placeholder</option>
                    </select>
                </div>

                <div id="rtsp-fields">
                    <div class="mb-4">
                        <label class="block text-sm text-gray-400 mb-2">RTSP URL</label>
                        <input type="text" id="rtsp-url" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="rtsp://192.168.1.100:554/stream">
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm text-gray-400 mb-2">Username</label>
                            <input type="text" id="rtsp-user" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none">
                        </div>
                        <div>
                            <label class="block text-sm text-gray-400 mb-2">Password</label>
                            <input type="password" id="rtsp-pass" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none">
                        </div>
                    </div>
                </div>

                <div id="file-fields" class="hidden">
                    <label class="block text-sm text-gray-400 mb-2">Placeholder Video URL</label>
                    <input type="text" id="placeholder-url" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none" placeholder="https://example.com/demo.mp4">
                    <p class="text-xs text-gray-500 mt-1">Leave empty to use a generated placeholder stream</p>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm text-gray-400 mb-2">Target FPS</label>
                        <select id="target-fps" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none">
                            <option value="0.5">0.5 FPS (Low CPU)</option>
                            <option value="1">1 FPS (Balanced)</option>
                            <option value="2">2 FPS (Responsive)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gray-400 mb-2">Detection Mode</label>
                        <select id="detection-mode" class="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-3 focus:border-accent focus:outline-none">
                            <option value="ppe">PPE Detection</option>
                            <option value="zone">Zone Monitoring</option>
                        </select>
                    </div>
                </div>

                <div>
                    <label class="block text-sm text-gray-400 mb-2">Confidence Threshold</label>
                    <input type="range" id="confidence" min="0.1" max="0.9" step="0.05" value="0.25" class="w-full" oninput="document.getElementById('conf-value').textContent = this.value">
                    <div class="flex justify-between text-xs text-gray-500 mt-1">
                        <span>More detections</span>
                        <span id="conf-value">0.25</span>
                        <span>Higher accuracy</span>
                    </div>
                </div>
            </div>

            <div class="flex gap-4 mt-6">
                <button onclick="hideModal()" class="flex-1 bg-dark-700 text-white px-4 py-3 rounded-lg font-medium hover:bg-dark-600 transition">Cancel</button>
                <button onclick="saveCamera()" class="flex-1 bg-accent text-dark-900 px-4 py-3 rounded-lg font-medium hover:bg-accent/90 transition">Save Camera</button>
            </div>
        </div>
    </div>

    <script>
        async function api(url, options = {}) {
            const response = await fetch(url, {
                ...options,
                credentials: 'include',
                headers: { 'Content-Type': 'application/json', ...options.headers },
            });
            if (response.status === 401) {
                window.location.href = '/login';
                return null;
            }
            return response;
        }

        async function fetchCameras() {
            try {
                const response = await api('/api/v1/cameras');
                const data = await response.json();
                renderCameras(data.cameras);
            } catch (e) {
                console.error('Failed to fetch cameras:', e);
            }
        }

        function renderCameras(cameras) {
            const list = document.getElementById('camera-list');
            if (cameras.length === 0) {
                list.innerHTML = `
                    <div class="col-span-full text-center py-12">
                        <svg class="w-16 h-16 text-gray-600 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                            <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"/>
                        </svg>
                        <p class="text-gray-400 mb-4">No cameras configured yet</p>
                        <button onclick="showAddModal()" class="bg-accent text-dark-900 px-6 py-2 rounded-lg font-medium hover:bg-accent/90 transition">Add Your First Camera</button>
                    </div>
                `;
                return;
            }

            list.innerHTML = cameras.map(cam => `
                <div class="camera-card rounded-xl p-4 transition">
                    <div class="flex items-start justify-between mb-3">
                        <div>
                            <h3 class="font-semibold">${cam.name}</h3>
                            <p class="text-sm text-gray-400">${cam.zone}</p>
                        </div>
                        <span class="px-2 py-1 text-xs rounded ${cam.status === 'online' ? 'bg-green-500/20 text-green-400' : cam.status === 'error' ? 'bg-red-500/20 text-red-400' : 'bg-gray-500/20 text-gray-400'}">
                            ${cam.status}
                        </span>
                    </div>
                    <div class="text-sm text-gray-400 space-y-1 mb-4">
                        <p>Source: ${cam.source_type}</p>
                        <p>Mode: ${cam.detection_mode}</p>
                        <p>FPS: ${cam.target_fps}</p>
                        ${cam.error_message ? `<p class="text-red-400">Error: ${cam.error_message}</p>` : ''}
                    </div>
                    <div class="flex gap-2">
                        <button onclick="editCamera('${cam.id}')" class="flex-1 bg-dark-700 text-white px-3 py-2 rounded-lg text-sm hover:bg-dark-600 transition">Edit</button>
                        <button onclick="deleteCamera('${cam.id}')" class="bg-red-500/20 text-red-400 px-3 py-2 rounded-lg text-sm hover:bg-red-500/30 transition">Delete</button>
                    </div>
                </div>
            `).join('');
        }

        function toggleSourceFields() {
            const type = document.getElementById('source-type').value;
            document.getElementById('rtsp-fields').classList.toggle('hidden', type !== 'rtsp');
            document.getElementById('file-fields').classList.toggle('hidden', type !== 'file');
        }

        function showAddModal() {
            document.getElementById('modal-title').textContent = 'Add Camera';
            document.getElementById('camera-id').value = '';
            document.getElementById('camera-name').value = '';
            document.getElementById('camera-zone').value = '';
            document.getElementById('source-type').value = 'rtsp';
            document.getElementById('rtsp-url').value = '';
            document.getElementById('rtsp-user').value = '';
            document.getElementById('rtsp-pass').value = '';
            document.getElementById('placeholder-url').value = '';
            document.getElementById('target-fps').value = '0.5';
            document.getElementById('detection-mode').value = 'ppe';
            document.getElementById('confidence').value = '0.25';
            document.getElementById('conf-value').textContent = '0.25';
            toggleSourceFields();
            document.getElementById('camera-modal').classList.remove('hidden');
            document.getElementById('camera-modal').classList.add('flex');
        }

        async function editCamera(id) {
            const response = await api(`/api/v1/cameras/${id}`);
            const cam = await response.json();

            document.getElementById('modal-title').textContent = 'Edit Camera';
            document.getElementById('camera-id').value = cam.id;
            document.getElementById('camera-name').value = cam.name;
            document.getElementById('camera-zone').value = cam.zone;
            document.getElementById('source-type').value = cam.source_type;
            document.getElementById('rtsp-url').value = cam.rtsp_url || '';
            document.getElementById('placeholder-url').value = cam.placeholder_video || '';
            document.getElementById('target-fps').value = cam.target_fps.toString();
            document.getElementById('detection-mode').value = cam.detection_mode;
            document.getElementById('confidence').value = cam.confidence_threshold;
            document.getElementById('conf-value').textContent = cam.confidence_threshold;
            toggleSourceFields();
            document.getElementById('camera-modal').classList.remove('hidden');
            document.getElementById('camera-modal').classList.add('flex');
        }

        function hideModal() {
            document.getElementById('camera-modal').classList.add('hidden');
            document.getElementById('camera-modal').classList.remove('flex');
            document.getElementById('modal-error').classList.add('hidden');
        }

        async function saveCamera() {
            const id = document.getElementById('camera-id').value;
            const sourceType = document.getElementById('source-type').value;

            const data = {
                name: document.getElementById('camera-name').value,
                zone: document.getElementById('camera-zone').value,
                source_type: sourceType,
                target_fps: parseFloat(document.getElementById('target-fps').value),
                detection_mode: document.getElementById('detection-mode').value,
                confidence_threshold: parseFloat(document.getElementById('confidence').value),
            };

            if (sourceType === 'rtsp') {
                data.rtsp_url = document.getElementById('rtsp-url').value;
                const user = document.getElementById('rtsp-user').value;
                const pass = document.getElementById('rtsp-pass').value;
                if (user && pass) {
                    data.credentials = `${user}:${pass}`;
                }
            } else {
                data.use_placeholder = true;
                data.placeholder_video = document.getElementById('placeholder-url').value || null;
            }

            try {
                const url = id ? `/api/v1/cameras/${id}` : '/api/v1/cameras';
                const method = id ? 'PUT' : 'POST';
                const response = await api(url, { method, body: JSON.stringify(data) });

                if (!response.ok) {
                    const error = await response.json();
                    document.getElementById('modal-error').textContent = error.detail || 'Failed to save camera';
                    document.getElementById('modal-error').classList.remove('hidden');
                    return;
                }

                hideModal();
                fetchCameras();
            } catch (e) {
                document.getElementById('modal-error').textContent = 'Network error';
                document.getElementById('modal-error').classList.remove('hidden');
            }
        }

        async function deleteCamera(id) {
            if (!confirm('Are you sure you want to delete this camera?')) return;

            try {
                await api(`/api/v1/cameras/${id}`, { method: 'DELETE' });
                fetchCameras();
            } catch (e) {
                console.error('Failed to delete camera:', e);
            }
        }

        async function logout() {
            await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
            window.location.href = '/login';
        }

        fetchCameras();
    </script>
</body>
</html>
"""
