// static/js/table_expand.js
(function() {
    function initTableExpand() {
        document.querySelectorAll('.table-row').forEach(row => {
            const expandBtn = row.querySelector('.expand-btn');
            const id = row.getAttribute('data-id');
            const content = document.getElementById(`content-${id}`);
            if (!content) return;

            const toggle = (e) => {
                // Не реагируем, если клик по ссылке предписания или кнопке редактирования
                if (e.target.closest('.prescription-link') || e.target.closest('.edit-btn')) return;
                row.classList.toggle('active');
                content.classList.toggle('active');
            };

            row.addEventListener('click', toggle);
            if (expandBtn) expandBtn.addEventListener('click', toggle);
        });
    }

    // Инициализация при загрузке
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTableExpand);
    } else {
        initTableExpand();
    }
})();