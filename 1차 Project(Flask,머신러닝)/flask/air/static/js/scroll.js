document.addEventListener("DOMContentLoaded", function() {
    const container = document.querySelector('.scroll-container');
    const topBtn = document.getElementById('backToTop');

    const handleScroll = () => {
        // [수정] 컨테이너 스크롤 값과 윈도우 스크롤 값 중 존재하는 것을 선택
        const containerScroll = container ? container.scrollTop : 0;
        const windowScroll = window.pageYOffset || document.documentElement.scrollTop;
        const scrollPos = Math.max(containerScroll, windowScroll);

        if (topBtn) {
            if (scrollPos > 300) {
                topBtn.style.display = 'flex';
                topBtn.style.zIndex = '9999'; // 레이어 순위 강제 상향
            } else {
                topBtn.style.display = 'none';
            }
        }
    };

    // [핵심] 컨테이너와 윈도우 양쪽에 모두 리스너를 걸어버립니다.
    if (container) {
        container.addEventListener('scroll', handleScroll);
    }
    window.addEventListener('scroll', handleScroll);

    // TOP 버튼 클릭 시 최상단 이동
    if (topBtn) {
        topBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // 두 타겟 모두 0으로 보냅니다.
            if (container) {
                container.scrollTo({ top: 0, behavior: 'smooth' });
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});