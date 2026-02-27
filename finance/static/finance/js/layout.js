document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('sidebarToggleBtn');
    if (!btn) return;

    const storageKey = 'tango_sidebar_collapsed';
    const icon = btn.querySelector('i');

    function updateIcon() {
        const collapsed = document.body.classList.contains('sidebar-collapsed');
        if (!icon) return;
        icon.className = collapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
    }

    const saved = window.localStorage.getItem(storageKey);
    if (saved === '1') {
        document.body.classList.add('sidebar-collapsed');
    }
    updateIcon();

    btn.addEventListener('click', () => {
        document.body.classList.toggle('sidebar-collapsed');
        const collapsed = document.body.classList.contains('sidebar-collapsed');
        window.localStorage.setItem(storageKey, collapsed ? '1' : '0');
        updateIcon();
    });
});
