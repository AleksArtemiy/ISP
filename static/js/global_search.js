// static/js/global_search.js
(function() {
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
        globalSearch.addEventListener('input', function() {
            const term = this.value.toLowerCase();
            document.querySelectorAll('.school-card, .table-row:not(.expanded-content)').forEach(el => {
                const text = el.innerText.toLowerCase();
                el.style.display = text.includes(term) ? '' : 'none';
            });
        });
    }
})();