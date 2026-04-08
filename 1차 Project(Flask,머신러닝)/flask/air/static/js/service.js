// 페이지 로드 시 자치구 리스트 채우기
function initializeDistrictMenu() {
    const districts = [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
        "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
    ];

    const $menu = $('#districtMenu');
    $menu.empty(); // 기존 내용 삭제

    districts.forEach(dist => {
        $menu.append(`<li><a class="dropdown-item district-item" href="#">${dist}</a></li>`);
    });
}

// 질병 타입(감기/천식) 변경 이벤트 리스너
$('input[name="modelType"]').on('change', function() {
    const selectedModel = $(this).val(); // 'cold' 또는 'asthma'
    applySliderSettings(selectedModel);
});

function applySliderSettings(mode) {
    const isCold = (mode === 'cold');

    // 1. 질병별 설정값 정의
    const config = {
        max: isCold ? 10000 : 1000,   // 감기 최대 10,000 / 천식 최대 1,000 (10단위 조절용)
        step: isCold ? 100 : 10,      // 감기 100단위 / 천식 10단위
        defaultVal: isCold ? 2500 : 150 // 초기 권장값
    };

    // 2. 대상 슬라이더들 (lag1, lag2, lag3) 루프 처리
    for (let i = 1; i <= 3; i++) {
        const rangeEl = $(`#lag${i}_range`);
        const inputEl = $(`#lag${i}`);

        // 속성 및 값 변경
        rangeEl.attr({
            'max': config.max,
            'step': config.step
        }).val(config.defaultVal);

        inputEl.val(config.defaultVal);
    }

    console.log(`${isCold ? '감기(100단위)' : '천식(10단위)'} 설정 적용 완료`);
}

$(document).ready(function() {
    // 1. 차트 인스턴스 초기화
    const mapChart = echarts.init(document.getElementById('map'));

    const ctx = document.getElementById('forecastChart').getContext('2d');
    let forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['3일전', '2일전', '1일전', '오늘', '내일', '모레', '3일후'],
            datasets: [{
                label: '환자수',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: false }, x: { grid: { display: false } } }
        }
    });

    // 시뮬레이션 변수들
    const initialMode = $('input[name="modelType"]:checked').val() || 'cold';

    // 2. 상태 관리 변수 (원본 유지)
    let currentDistrict = "강남구";
    let currentModel = 'cold';
    let currentDateIndex = 3;
    let seoulGeoJson = null;

    // 3. 변수 동기화
    $('input[type="range"]').on('input', function() { $(this).next('input').val($(this).val()); });
    $('input[type="number"]').on('input', function() { $(this).prev('input[type="range"]').val($(this).val()); });

    // 4. [중요] 지도 렌더링 함수 (사용자가 준 원본 코드 그대로 복구)
    function renderMap(mapData, statusLabel, mapMin, mapMax) {
        if (seoulGeoJson) {
            drawChart(mapData, statusLabel);
        } else {
            $.getJSON("/service/seoul-geo", function(geoJson) {
                seoulGeoJson = geoJson;
                echarts.registerMap('seoul', geoJson);
                drawChart(mapData, statusLabel);
            });
        }

        function drawChart(data, label) {
            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'item',
                    formatter: function(params) {
                        if (params.data) {
                            const riskPercent = (params.data.value * 100).toFixed(1);
                            return `<div style="font-family: Pretendard; padding: 5px;">
                                        <b style="font-size: 14px;">${params.name}</b><br/>
                                        <span style="color: #4f46e5;">예측 환자: <b>${params.data.cnt}</b>명</span><br/>
                                        <small>발생률: ${params.data.realRate.toFixed(2)}</small><br/>
                                        <small style="color: #ef4444;">위험지수: 평균의 ${riskPercent}%</small>
                                    </div>`;
                        }
                        return params.name;
                    }
                },
                visualMap: {
                    min: mapMin || 0.8,
                    max: mapMax || (currentModel === 'cold' ? 1.3 : 2.0),
                    show: true,
                    right: 0, bottom: 0,
                    itemWidth: 20, itemHeight: 120,
                    inRange: {
                        color: currentModel === 'cold'
                        ? ['#ffffff', '#fee2e2', '#ef4444', '#991b1b']
                        : ['#ffffff', '#fef3c7', '#fbbf24', '#92400e']
                    },
                    text: ['높음', '낮음'],
                    textStyle: { fontFamily: 'Pretendard', fontSize: 11, color: '#64748b' },
                    formatter: function(value) { return (value * 100).toFixed(0) + '%'; },
                },
                graphic: [{
                    type: 'text',
                    right: 4, top: 4, z: 100,
                    silent: true,
                    style: {
                        text: `선택된 구 : ${currentDistrict}`,
                        font: 'bold 18px Pretendard',
                        fill: '#1e293b',
                        textAlign: 'right',
                        textVerticalAlign: 'top'
                    }
                }],
                series: [{
                    name: '서울시 위험도',
                    type: 'map', map: 'seoul', roam: false,
                    nameProperty: 'SIG_KOR_NM',
                    layoutCenter: ['48%', '50%'], layoutSize: '130%',
                    aspectScale: 0.9,
                    label: {
                        show: true,
                        formatter: function(params) {
                            return params.name === currentDistrict ? `{s|${params.name}}` : params.name;
                        },
                        rich: {
                            s: { fontSize: 18, fontWeight: '900', color: '#1e293b', textBorderColor: '#fff', textBorderWidth: 3, fontFamily: 'Pretendard' }
                        },
                        color: '#64748b', fontWeight: '600', fontSize: 13, fontFamily: 'Pretendard'
                    },
                    itemStyle: { areaColor: '#ffffff', borderColor: '#cbd5e0', borderWidth: 0.5 },
                    data: data
                }]
            };
            mapChart.setOption(option, true);
        }
    }

    // 5. 통합 데이터 로직 (원본 유지)
    function getMergedData(disease, index, district) {
        if (index < 3) return prevData[disease][index][district] || null;
        return rawData[disease][index - 3][district] || null;
    }

    function updateDisplay() {
        if (typeof rawData === 'undefined' || typeof prevData === 'undefined') return;

        const diseaseKey = currentModel === 'cold' ? '감기' : '천식';
        const seoulAvg = currentModel === 'cold' ? 62.44 : 3.6;

        // 텍스트/라벨 동기화
        $('#dynamicTitle').text(`서울시 자치구별 ${diseaseKey} 위험도`);
        $('#chartTitle').text(`${diseaseKey} Multi-step 예측`);
        $('#label_lag1').text(`1일 전 ${diseaseKey} 환자`);
        $('#label_lag2').text(`2일 전 ${diseaseKey} 환자`);
        $('#label_lag3').text(`3일 전 ${diseaseKey} 환자`);

        // 상단 카드 & Chart.js 데이터 수집
        const chartValues = [];
        for(let i=0; i<7; i++) {
            const d = getMergedData(diseaseKey, i, currentDistrict);
            const val = d ? d.pred_cnt : 0;
            const rate = d ? d.pred_rate : 0;
            chartValues.push(val);

            // 상단 카드 갱신 (오늘~3일후: 인덱스 3, 4, 5, 6)
            if (i >= 3) {
                const $cardVal = $(`.summary-val:eq(${i-2})`); // 카드 엘리먼트 선택
                $cardVal.text(`${val}명`);

                // --- [추가] 위험도 기반 색상 변경 로직 ---
                const riskRatio = (rate / seoulAvg) * 100;
                $cardVal.removeClass('status-safe status-normal status-caution status-danger');

                if (riskRatio >= 150) {
                    $cardVal.addClass('status-danger');   // 매우 위험
                } else if (riskRatio >= 110) {
                    $cardVal.addClass('status-caution');  // 주의
                } else if (riskRatio >= 80) {
                    $cardVal.addClass('status-normal');   // 보통
                } else {
                    $cardVal.addClass('status-safe');     // 안전
                }
                // ---------------------------------------
            }

            // 첫 번째 카드는 미세먼지 수치(x값)이므로 별도 처리
            if (i === 3) {
                 $(`.summary-val:eq(0)`).text($('#pm10').val());
            }
        }

        // Chart.js 갱신
        const mainColor = currentModel === 'cold' ? '#3b82f6' : '#f59e0b';
        forecastChart.data.datasets[0].data = chartValues;
        forecastChart.data.datasets[0].borderColor = mainColor;
        forecastChart.data.datasets[0].backgroundColor = mainColor + '22';
        forecastChart.update();

        // [중요] 지도 데이터 생성 및 원본 renderMap 호출
        const targetDayObj = (currentDateIndex < 3) ? prevData[diseaseKey][currentDateIndex] : rawData[diseaseKey][currentDateIndex - 3];
        const filteredData = Object.entries(targetDayObj).map(([distName, details]) => ({
            name: distName,
            value: details.pred_rate / seoulAvg,
            realRate: details.pred_rate,
            cnt: details.pred_cnt,
            itemStyle: distName === currentDistrict ? { shadowBlur: 5, shadowColor: 'rgba(0, 0, 0, 0.4)', areaColor: null } : { shadowBlur: 0 }
        }));

        const values = filteredData.map(d => d.value);
        renderMap(filteredData, `${diseaseKey} 위험도`, Math.min(...values), Math.max(...values));

        // 우측 체감형 지표
        const selectedInfo = getMergedData(diseaseKey, currentDateIndex, currentDistrict);
        if (selectedInfo) {
            const riskRatio = (selectedInfo.pred_rate / seoulAvg) * 100;

            // 1. 상단 카드와 100% 동일한 기준 적용
            let level = '';
            let colorClass = '';
            let barClass = '';

            if (riskRatio >= 150) {
                level = '위험';
                colorClass = 'status-danger';
                barClass = 'bar-danger';
            } else if (riskRatio >= 110) {
                level = '주의';
                colorClass = 'status-caution';
                barClass = 'bar-caution'; // 주황색 느낌을 위해 warning 유지
            } else if (riskRatio >= 80) {
                level = '보통';
                colorClass = 'status-normal';
                barClass = 'bar-normal';    // 보통 단계는 하늘색/파란색 계열 바
            } else {
                level = '안전';
                colorClass = 'status-safe';
                barClass = 'bar-safe';
            }

            $('#risk-progress-section').html(`
                <div class="mb-4">
                    <div class="d-flex justify-content-between small mb-2">
                        <span class="fw-bold" style="color: #334155;">${currentDistrict}</span>
                        <span class="${colorClass} fw-bolder">
                            ${level} (${riskRatio.toFixed(0)}%)
                        </span>
                    </div>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar ${barClass}" style="width: ${Math.min(riskRatio, 100)}%"></div>
                    </div>
                </div>
            `);
        }
    }

    // 6. 이벤트 핸들러 (원본 유지)
    // 지도 클릭 시 구 선택 변경
    mapChart.on('click', p => {
        currentDistrict = p.name; // 전역 변수 업데이트

        // [추가] 드롭다운 버튼 텍스트도 클릭한 구 이름으로 변경
        $('#districtSelect').text(p.name);

        updateDisplay(); // 차트 및 상세 지표 갱신
        console.log(`지도 클릭으로 구 선택: ${p.name}`);
    });
    $('input[name="modelType"]').on('change', function() { currentModel = $(this).val(); updateDisplay(); });
    $('.date-btn').on('click', function() {
        $('.date-btn').removeClass('active btn-primary');
        $(this).addClass('active btn-primary');
        currentDateIndex = parseInt($(this).data('date')) + 3;
        updateDisplay();
    });

    // 시뮬레이션 결과 반영시키기
    $('#predictBtn').on('click', function() {
        const dist_name = currentDistrict; // 현재 선택된 구
        const disease_type = currentModel;  // 현재 선택된 질병 (cold/asthma)

        // 1. 폼 데이터 가져오기
        let formElement = document.getElementById('predictionForm');
        let formData = new FormData(formElement);

        // 2. 추가 데이터 깔끔하게 append
        formData.append('dist_name', dist_name);
        formData.append('disease_type', disease_type);

        $.ajax({
            url: '/service/simulate',
            type: 'POST',
            headers: {'X-CSRFToken': $('meta[name="csrf-token"]').attr('content')},
            data: formData,
            processData: false,  // 중요: 데이터를 쿼리 스트링으로 변환하지 않음
            contentType: false,  // 중요: 브라우저가 알아서 Boundary를 설정하게 함
            success: function(response) {
                const diseaseKey = disease_type === 'cold' ? '감기' : '천식';

                // [A] 과거 데이터 수정 (사용자가 입력한 lag값들로 해당 구 데이터만 갱신)
                // 파이썬에서 넘겨준 input 값을 그대로 써도 되고, 여기서 직접 폼 값을 읽어도 됩니다.
                prevData[diseaseKey][2][dist_name].pred_cnt = parseFloat($('input[name="lag1"]').val()) || 0;
                prevData[diseaseKey][1][dist_name].pred_cnt = parseFloat($('input[name="lag2"]').val()) || 0;
                prevData[diseaseKey][0][dist_name].pred_cnt = parseFloat($('input[name="lag3"]').val()) || 0;

                // [B] 미래 데이터 수정 (서버에서 계산된 4일치 결과 반영)
                if (response.predictions) {
                    for (let i = 0; i < 4; i++) {
                        rawData[diseaseKey][i][dist_name].pred_cnt = response.predictions[i].cnt;
                        rawData[diseaseKey][i][dist_name].pred_rate = response.predictions[i].rate;
                    }
                }

                // [C] UI 업데이트 (차트 & 지도 갱신)
                updateDisplay();
                console.log(`${dist_name} 시뮬레이션 완료`);
            }
        });
    });

    // 자치구 드롭다운 항목 클릭 이벤트
    $(document).on('click', '.district-item', function(e) {
        e.preventDefault(); // 페이지 최상단 이동 방지

        const selectedDist = $(this).text().trim();

        // 1. 전역 변수 업데이트
        currentDistrict = selectedDist;

        // 2. 버튼 텍스트 변경 (현재 선택된 구 표시)
        $('#districtSelect').text(selectedDist);

        // 3. 화면 갱신 (차트, 지도 강조 등)
        updateDisplay();

        console.log(`자치구 선택 변경: ${selectedDist}`);
    });

    initializeDistrictMenu();
    updateDisplay();
    applySliderSettings(initialMode);
    window.addEventListener('resize', () => mapChart.resize());
});