document.addEventListener("DOMContentLoaded", function() {
    const container = document.querySelector('.scroll-container');
    const navbar = document.querySelector('.navbar-air');
    const firstSection = document.querySelector('.scroll-section');
    const topBtn = document.getElementById('backToTop');

    // 현재 페이지가 메인 페이지인지 확인
    const isMainPage = navbar && navbar.classList.contains('is-main-nav');

    // --- [1] 메인 페이지 전용 로직 ---
    if (container) {
        // 1-1. 데스크톱 휠 로직 (수정)
        // CSS에서 scroll-snap-type을 사용하므로,
        // JS에서 직접 위치를 계산(wheel 이벤트)할 필요가 없어졌습니다.
        // JS로 강제 계산하면 CSS Snap과 충돌하여 화면이 덜덜 떨릴 수 있습니다.
        // 대신, TOP 버튼 표시 로직만 남깁니다.

        if (topBtn) {
            container.addEventListener('scroll', () => {
                // 컨테이너 내부 스크롤이 300px 이상일 때 표시
                if (container.scrollTop > 300) {
                    topBtn.style.opacity = "1";
                    topBtn.style.display = 'flex';
                } else {
                    topBtn.style.opacity = "0";
                    setTimeout(() => { if(container.scrollTop <= 300) topBtn.style.display = 'none'; }, 300);
                }
            });
        }
    }
    // --- [2] 일반 페이지용 로직 (서비스 페이지 등) ---
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

    // --- [3] 공통 및 조건별 로직 ---

    // 3-1. TOP 버튼 클릭 (부드러운 이동)
    if (topBtn) {
        topBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (container && window.innerWidth >= 992) {
                // 데스크톱 풀페이지 모드일 때는 컨테이너를 올림
                container.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                // 모바일이나 일반 페이지는 윈도우 자체를 올림
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    // 3-2. 모바일 네비바 배경색 전환 (IntersectionObserver)
    if (isMainPage && navbar && firstSection) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                // 992px 미만(모바일)에서만 배경색 전환 작동
                if (window.innerWidth < 992) {
                    if (entry.isIntersecting) {
                        // 첫 섹션(캐러셀)이 보일 때는 투명
                        navbar.classList.add('mobile-transparent');
                        navbar.classList.remove('mobile-white');
                    } else {
                        // 첫 섹션을 벗어나면 흰색 배경
                        navbar.classList.remove('mobile-transparent');
                        navbar.classList.add('mobile-white');
                    }
                }
            });
        }, {
            threshold: 0.1 // 10%만 가려져도 바로 작동
        });
        observer.observe(firstSection);
    }

    // 3-3. 창 크기 조절 시 리셋 (모바일 <-> 데스크톱 전환 대응)
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 992 && navbar) {
            navbar.classList.remove('mobile-transparent', 'mobile-white');
        }
    });
});