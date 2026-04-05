document.addEventListener("DOMContentLoaded", function() {
    const container = document.querySelector('.scroll-container');
    const topBtn = document.getElementById('backToTop');

    // --- 2. TOP 버튼 표시 로직 ---
    const handleScroll = () => {
        const scrollPos = container ? container.scrollTop : window.scrollY;
        if (topBtn) {
            if (scrollPos > 300) {
                topBtn.style.display = 'flex';
            } else {
                topBtn.style.display = 'none';
            }
        }
    };

    if (container) {
        container.addEventListener('scroll', handleScroll);
    } else {
        window.addEventListener('scroll', handleScroll);
    }

    // --- 3. TOP 버튼 클릭 시 최상단 이동 ---
    if (topBtn) {
        topBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // 스냅 컨테이너가 있으면 해당 컨테이너를, 없으면 window를 스크롤
            const target = (container && window.innerWidth >= 992) ? container : window;
            target.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});