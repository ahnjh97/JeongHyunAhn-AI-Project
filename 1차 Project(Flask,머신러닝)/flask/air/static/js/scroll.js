document.addEventListener("DOMContentLoaded", function() {
    const container = document.querySelector('.scroll-container');
    const navbar = document.querySelector('.navbar-air');
    const firstSection = document.querySelector('.scroll-section');
    const topBtn = document.getElementById('backToTop');

    let isScrolling = false;

    // --- [1] 메인 페이지용 로직 (scroll-container가 존재할 때) ---
    if (container) {
        // 1-1. 데스크톱 휠 스크롤 (0.6초 입력 방지)
        if (window.innerWidth >= 992) {
            container.addEventListener('wheel', (e) => {
                e.preventDefault();
                if (isScrolling) return;

                const direction = e.deltaY > 0 ? 1 : -1;
                const scrollHeight = window.innerHeight;
                const currentScroll = container.scrollTop;

                let target = Math.round(currentScroll / scrollHeight) + direction;
                const sections = document.querySelectorAll('.scroll-section, .main-footer');
                target = Math.max(0, Math.min(target, sections.length - 1));

                isScrolling = true;
                container.scrollTo({ top: target * scrollHeight, behavior: 'smooth' });
                setTimeout(() => { isScrolling = false; }, 600);
            }, { passive: false });
        }

        // 1-2. 메인 페이지용 TOP 버튼 감시 (컨테이너 스크롤 감시)
        if (topBtn) {
            container.addEventListener('scroll', () => {
                if (container.scrollTop > 300) {
                    topBtn.style.display = 'flex';
                } else {
                    topBtn.style.display = 'none';
                }
            });
        }
    }
    // --- [2] 일반 페이지용 로직 (scroll-container가 없을 때) ---
    else {
        if (topBtn) {
            window.addEventListener('scroll', () => {
                if (window.scrollY > 300) {
                    topBtn.style.display = 'flex';
                } else {
                    topBtn.style.display = 'none';
                }
            });
        }
    }

    // --- [3] 공통 로직 (어느 페이지에서나 작동) ---

    // 3-1. TOP 버튼 클릭 이벤트 (대상에 맞춰 스크롤)
    if (topBtn) {
        topBtn.addEventListener('click', () => {
            if (container) {
                container.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    // 3-2. 모바일 네비바 색상 감시 (Intersection Observer)
    if (navbar && firstSection) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (window.innerWidth < 992) {
                    if (entry.isIntersecting) {
                        navbar.classList.add('mobile-transparent');
                        navbar.classList.remove('mobile-white');
                    } else {
                        navbar.classList.remove('mobile-transparent');
                        navbar.classList.add('mobile-white');
                    }
                }
            });
        }, { threshold: 0.1 });
        observer.observe(firstSection);
    }
});