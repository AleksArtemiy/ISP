// static/js/prescriptions.js

// Раскрытие строки с нарушениями
document.querySelectorAll('.table-row').forEach(row => {
    row.addEventListener('click', (e) => {
        // Не реагируем, если клик был по ссылке или кнопке внутри
        if (e.target.closest('.prescription-link') || e.target.closest('.edit-btn')) return;
        const id = row.dataset.id;
        const content = document.getElementById(`content-${id}`);
        if (!content) return;
        row.classList.toggle('active');
        content.classList.toggle('active');
    });
});

// Фильтрация (заглушка, позже заменим на отправку формы или AJAX)
const filterButton = document.querySelector('.filter-button');
const searchInput = document.querySelector('.search-box input');
const institutionSelect = document.querySelectorAll('.select-box')[0];
const statusSelect = document.querySelectorAll('.select-box')[1];
const authoritySelect = document.querySelectorAll('.select-box')[2];

function applyFilters() {
    // Здесь будет логика фильтрации (сейчас просто выводим в консоль)
    console.log('Фильтр:', {
        search: searchInput?.value,
        institution: institutionSelect?.innerText,
        status: statusSelect?.innerText,
        authority: authoritySelect?.innerText,
    });
    // В реальном проекте – отправка GET-запроса с параметрами
    // ========== РАСКРЫТИЕ СТРОК ПРЕДПИСАНИЙ ==========
    document.querySelectorAll('.table-row').forEach(row => {
        const expandBtn = row.querySelector('.expand-btn');
        if (!expandBtn) return;

        const handleToggle = (e) => {
            // Не реагируем, если клик по ссылке или кнопке редактирования
            if (e.target.closest('.prescription-link') || e.target.closest('.edit-btn')) return;
            
            const id = row.getAttribute('data-id');
            const content = document.getElementById(`content-${id}`);
            if (!content) return;
            
            row.classList.toggle('active');
            content.classList.toggle('active');
        };

        row.addEventListener('click', handleToggle);
        // Чтобы кнопка раскрытия тоже работала (если кликнуть именно по иконке)
        if (expandBtn) expandBtn.addEventListener('click', handleToggle);
    });
}

if (filterButton) {
    filterButton.addEventListener('click', applyFilters);
}
if (searchInput) {
    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') applyFilters();
    });
}