
function getCookie(name) {
    const cookies = document.cookie
        ? document.cookie.split(';')
        : [];

    for (const cookie of cookies) {
        const item = cookie.trim();

        if (item.startsWith(name + '=')) {
            return decodeURIComponent(
                item.substring(name.length + 1)
            );
        }
    }

    return null;
}

const API = {
    accessToken: localStorage.getItem('access'),

    refreshPromise: null,

    async request(url, options = {}) {
        const headers = new Headers(options.headers || {});
        const method = (options.method || 'GET').toUpperCase();

        if (this.accessToken) {
            headers.set(
                'Authorization',
                `Bearer ${this.accessToken}`
            );
        }

        if (
            options.body &&
            !(options.body instanceof FormData) &&
            typeof options.body === 'string' &&
            !headers.has('Content-Type')
        ) {
            headers.set('Content-Type', 'application/json');
        }

        if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
            const csrfToken = getCookie('csrftoken');

            if (csrfToken) {
                headers.set('X-CSRFToken', csrfToken);
            }
        }

        return fetch(url, {
            ...options,
            method,
            headers,
            credentials: 'same-origin'
        });
    },

    saveAccessToken(token) {
        this.accessToken = token || null;

        if (token) {
            localStorage.setItem('access', token);
        } else {
            localStorage.removeItem('access');
        }
    },

    async login(email, password) {
        // Ensure CSRF cookie is available before POST.
        await fetch('/accounts/api/csrf/', {
            method: 'GET',
            credentials: 'same-origin'
        });

        const response = await this.request(
            '/accounts/api/token/',
            {
                method: 'POST',
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.message ||
                'Login failed. Check your credentials.'
            );
        }

        if (data.access) {
            this.saveAccessToken(data.access);
        }

        return data;
    },

    async refreshAccessToken() {
        // Prevent multiple simultaneous refresh requests.
        if (this.refreshPromise) {
            return this.refreshPromise;
        }

        this.refreshPromise = (async () => {
            try {
                // Refresh endpoint must accept the refresh token
                // in the format configured by the Django backend.
                const response = await this.request(
                    '/accounts/api/token/refresh/',
                    {
                        method: 'POST',
                        body: JSON.stringify({})
                    }
                );

                if (!response.ok) {
                    this.saveAccessToken(null);
                    return false;
                }

                const data = await response.json();

                if (!data.access) {
                    this.saveAccessToken(null);
                    return false;
                }

                this.saveAccessToken(data.access);
                return true;
            } catch (error) {
                console.error('Token refresh failed:', error);
                this.saveAccessToken(null);
                return false;
            } finally {
                this.refreshPromise = null;
            }
        })();

        return this.refreshPromise;
    },

    async fetch(url, options = {}) {
        let response = await this.request(url, options);

        // Retry once after refreshing an expired access token.
        if (response.status === 401) {
            const refreshed = await this.refreshAccessToken();

            if (refreshed) {
                response = await this.request(url, options);
            }
        }

        return response;
    },

    async logout() {
        try {
            await this.request(
                '/accounts/api/logout/',
                {
                    method: 'POST',
                    body: JSON.stringify({})
                }
            );
        } catch (error) {
            console.error('Logout request failed:', error);
        } finally {
            this.saveAccessToken(null);
        }
    }
};


// Initialize CSRF and attempt to restore the access token
// when a page is opened or refreshed.
window.API = API;

API.ready = (async () => {
    try {
        await fetch('/accounts/api/csrf/', {
            credentials: 'same-origin'
        });

        return await API.refreshAccessToken();
    } catch (error) {
        console.error('Authentication initialization failed:', error);
        return false;
    }
})();