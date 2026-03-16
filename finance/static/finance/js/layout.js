document.addEventListener('DOMContentLoaded', () => {
    function initAccountMenus() {
        const menus = document.querySelectorAll('[data-account-menu]');
        if (!menus.length) return;

        const closeMenu = (menu) => {
            const panel = menu.querySelector('[data-account-menu-panel]');
            const trigger = menu.querySelector('[data-account-menu-toggle]');
            if (panel) panel.hidden = true;
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        };

        const openMenu = (menu) => {
            menus.forEach((node) => closeMenu(node));
            const panel = menu.querySelector('[data-account-menu-panel]');
            const trigger = menu.querySelector('[data-account-menu-toggle]');
            if (!panel || !trigger) return;
            panel.hidden = false;
            trigger.setAttribute('aria-expanded', 'true');
        };

        document.addEventListener('click', (event) => {
            const toggle = event.target.closest('[data-account-menu-toggle]');
            if (toggle) {
                const menu = toggle.closest('[data-account-menu]');
                const panel = menu ? menu.querySelector('[data-account-menu-panel]') : null;
                const willOpen = !!(panel && panel.hidden);
                if (menu && willOpen) openMenu(menu);
                else if (menu) closeMenu(menu);
                return;
            }
            menus.forEach((menu) => {
                if (!menu.contains(event.target)) closeMenu(menu);
            });
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                menus.forEach((menu) => closeMenu(menu));
            }
        });

    }

    function initLogoutTriggers() {
        document.addEventListener('click', (evt) => {
            const trigger = evt.target.closest('[data-logout-trigger="true"]');
            if (!trigger) return;

            evt.preventDefault();
            evt.stopPropagation();

            const formId = trigger.dataset.logoutFormId;
            if (!formId) return;
            const logoutForm = document.getElementById(formId);
            if (!logoutForm) return;
            logoutForm.submit();
        }, true);
    }

    function createTransitionOverlay() {
        let overlay = document.querySelector('.page-transition-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'page-transition-overlay';
            document.body.appendChild(overlay);
        }
        return overlay;
    }

    function isInternalNavigableLink(anchor) {
        if (!anchor || !anchor.href) return false;
        if (anchor.target && anchor.target.toLowerCase() === '_blank') return false;
        if (anchor.hasAttribute('download')) return false;
        if (anchor.dataset.noTransition === 'true') return false;
        if (anchor.getAttribute('href').startsWith('#')) return false;
        if (anchor.getAttribute('href').startsWith('javascript:')) return false;
        if (anchor.getAttribute('href').startsWith('mailto:')) return false;
        if (anchor.getAttribute('href').startsWith('tel:')) return false;
        if (anchor.hasAttribute('data-bs-toggle')) return false;
        const url = new URL(anchor.href, window.location.origin);
        if (url.origin !== window.location.origin) return false;
        // File download endpoints should not trigger page-leaving overlays.
        if (url.pathname.endsWith('/finance/export/')) return false;
        if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return false;
        return true;
    }

    function initPageTransitions() {
        const overlay = createTransitionOverlay();
        overlay.classList.add('enter');
        window.requestAnimationFrame(() => {
            overlay.classList.add('enter-active');
            window.setTimeout(() => {
                overlay.classList.remove('enter', 'enter-active');
            }, 380);
        });

        let leaving = false;
        document.addEventListener('click', (evt) => {
            const anchor = evt.target.closest('a');
            if (!anchor) return;
            if (evt.defaultPrevented) return;
            if (evt.metaKey || evt.ctrlKey || evt.shiftKey || evt.altKey || evt.button !== 0) return;
            if (!isInternalNavigableLink(anchor)) return;
            if (leaving) return;

            evt.preventDefault();
            leaving = true;
            const to = anchor.href;
            document.body.classList.add('page-leaving');
            overlay.classList.add('leave');
            window.setTimeout(() => {
                window.location.assign(to);
            }, 300);
        }, true);
    }

    function initToasts() {
        const stack = document.querySelector('.app-toast-stack');
        if (!stack) return;

        function dismissToast(toast) {
            if (!toast || !toast.parentNode) return;
            toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            setTimeout(() => {
                if (toast.parentNode) toast.remove();
            }, 260);
        }

        Array.from(stack.querySelectorAll('.app-toast')).forEach((toast, index) => {
            const closeBtn = toast.querySelector('.btn-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => dismissToast(toast));
            }
            setTimeout(() => dismissToast(toast), 5000 + index * 400);
        });
    }

    initAccountMenus();
    initLogoutTriggers();
    initPageTransitions();
    initToasts();
});
