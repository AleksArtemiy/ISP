// обработка выпадающего меню профиля
const profileBtn = document.getElementById('profileBtn');
const dropdown = document.getElementById('dropdown');

if (profileBtn && dropdown) {
    profileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('active');
    });

    document.addEventListener('click', () => {
        dropdown.classList.remove('active');
    });
}

// поиск по учреждениям (фильтрация карточек)
const searchInput = document.getElementById('searchInput');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        const cards = document.querySelectorAll('.school-card');
        cards.forEach(card => {
            const title = card.querySelector('.school-title').innerText.toLowerCase();
            if (title.includes(query)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    });
}

// клик по карточке учреждения – переход на детальную страницу
document.querySelectorAll('.school-card').forEach(card => {
    card.addEventListener('click', (e) => {
        // не реагируем, если клик был внутри кнопки или ссылки
        if (e.target.closest('.finance') || e.target.closest('.school-tag')) return;
        const instId = card.getAttribute('data-id');
        if (instId) {
            window.location.href = `/institution/${instId}/`;
        }
    });
});