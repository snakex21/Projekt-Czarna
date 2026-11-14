/**
 * Autoryzacja panelu admina (P2.5 Etap 12) — wydzielona z admin.js.
 *
 * Moduł obsługuje status auth, logowanie, wylogowanie i stan localStorage.
 * Shell panelu (ekran logowania, panel admina, ładowanie dashboardu) pozostaje
 * w admin.js i jest przekazywany przez callbacki.
 */
(function () {
    'use strict';

    const API = window.AdminAPI;
    const { showToast } = window.AdminNotifications;

    let elements = {
        loginForm: null,
        loginError: null,
        logoutBtn: null,
    };
    let callbacks = {
        showLoginScreen: function () {},
        showAdminPanel: function () {},
    };
    let currentUser = null;

    function initAuth(options) {
        const config = options || {};
        elements = Object.assign({}, elements, config.elements || {});
        callbacks = Object.assign({}, callbacks, config.callbacks || {});
    }

    async function checkAuth() {
        try {
            // Zapytaj serwer, czy autoryzacja jest w ogóle włączona.
            const response = await fetch(API.authStatus, { credentials: 'same-origin' });
            if (!response.ok) throw new Error('Nie można sprawdzić statusu autoryzacji.');

            const authConfig = await response.json();

            if (!authConfig.enabled) {
                // Autoryzacja jest WYŁĄCZONA.
                if (elements.logoutBtn) elements.logoutBtn.classList.add('hidden');
                callbacks.showAdminPanel();
                return;
            }

            // Autoryzacja jest WŁĄCZONA.
            if (elements.logoutBtn) elements.logoutBtn.classList.remove('hidden');

            if (authConfig.setup_required) {
                // Brak skonfigurowanego hasła admina - logowanie niemożliwe.
                callbacks.showLoginScreen();
                if (elements.loginError) {
                    elements.loginError.textContent = authConfig.setup_instructions
                        || 'Hasło administratora nie jest skonfigurowane.';
                    elements.loginError.classList.remove('hidden');
                }
                return;
            }

            // Stan sesji sprawdzamy na serwerze (token może wygasnąć);
            // localStorage służy tylko jako podpowiedź UI.
            const sessionResponse = await fetch(API.checkAuth, { credentials: 'same-origin' });
            const session = sessionResponse.ok ? await sessionResponse.json() : { authenticated: false };
            if (session.authenticated) {
                localStorage.setItem('adminLoggedIn', 'true');
                callbacks.showAdminPanel();
            } else {
                const hadSession = localStorage.getItem('adminLoggedIn') === 'true';
                localStorage.removeItem('adminLoggedIn');
                callbacks.showLoginScreen();
                if (hadSession) showToast('info', 'Sesja wygasła - zaloguj się ponownie');
            }
        } catch (error) {
            // W przypadku błędu sieci bezpieczniej jest pokazać ekran logowania.
            console.error('Błąd podczas sprawdzania autoryzacji:', error);
            if (elements.logoutBtn) elements.logoutBtn.classList.add('hidden');
            callbacks.showLoginScreen();
            if (elements.loginError) {
                elements.loginError.textContent = 'Błąd połączenia z serwerem. Spróbuj odświeżyć stronę.';
                elements.loginError.classList.remove('hidden');
            }
        }
    }

    async function handleLogin(event) {
        event.preventDefault();
        const login = document.getElementById('login').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch(API.login, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ username: login, password: password }),
            });

            const data = await response.json();

            if (data.status === 'ok') {
                localStorage.setItem('adminLoggedIn', 'true');
                currentUser = login;
                if (elements.loginError) elements.loginError.classList.add('hidden');
                callbacks.showAdminPanel();
                showToast('success', 'Zalogowano pomyślnie');
            } else if (elements.loginError) {
                elements.loginError.textContent = data.message || 'Błędne dane logowania';
                elements.loginError.classList.remove('hidden');
            }
        } catch (error) {
            if (elements.loginError) {
                elements.loginError.textContent = 'Błąd połączenia z serwerem';
                elements.loginError.classList.remove('hidden');
            }
        }
    }

    async function handleLogout() {
        if (confirm('Czy na pewno chcesz się wylogować?')) {
            try {
                await fetch(API.logout, { method: 'POST', credentials: 'same-origin' });
            } catch (error) {
                console.error('Błąd wylogowania:', error);
            }

            localStorage.removeItem('adminLoggedIn');
            currentUser = null;
            callbacks.showLoginScreen();
            showToast('info', 'Wylogowano z systemu');
        }
    }

    window.AdminAuth = Object.freeze({
        init: initAuth,
        checkAuth: checkAuth,
        login: handleLogin,
        logout: handleLogout,
    });
})();
