// static/js/profile_dropdown.js
(function() {
    const profileBtn = document.getElementById('profileBtn');
    const dropdown = document.getElementById('dropdown');
    
    if (profileBtn && dropdown) {
        profileBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('active');
        });
        
        document.addEventListener('click', function() {
            dropdown.classList.remove('active');
        });
    }
})();