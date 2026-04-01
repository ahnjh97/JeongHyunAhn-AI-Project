$(document).ready(function() {
    // 1. 차트 인스턴스 초기화
    const mapChart = echarts.init(document.getElementById('map'));
    const coldChart = echarts.init(document.getElementById('forecastChart1'));
    const asthmaChart = echarts.init(document.getElementById('forecastChart2'));

    // 2. 상태 관리 변수
    let currentDistrict = "강남구";
    let currentModel = 'cold';      // 'cold' or 'asthma'
    let currentDateIndex = 0;       // 0:오늘, 1:내일, 2:2일뒤, 3:3일뒤
    let seoulGeoJson = null;        // 지형 데이터 캐싱용 변수

    // 3. Navbar 드롭다운 메뉴 채우기
    const districts = ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"];
    const $menu = $('#districtMenu');
    if($menu.length) {
        $menu.empty();
        districts.forEach(d => {
            $menu.append(`<li><a class="dropdown-item district-option" style="cursor:pointer;">${d}</a></li>`);
        });
    }

    // 4. 지도 렌더링 함수
    function renderMap(mapData, statusLabel) {
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
            const districtData = data.find(item => item.name === currentDistrict);
            const patientCount = (districtData && districtData.rate) ? districtData.rate : 0;

            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'item',
                    formatter: '{b}: {c}명',
                    transitionDuration: 0,
                    textStyle: { fontFamily: 'Pretendard' }
                },
                visualMap: {
                    min: 0, max: 200, show: true,
                    right: 0, bottom: 0,
                    padding: [0, 0, 10, 0],
                    itemWidth: 20, itemHeight: 120,
                    inRange: {
                        color: currentModel === 'cold'
                            ? ['#ffffff', '#fee2e2', '#f87171', '#ef4444', '#991b1b']
                            : ['#ffffff', '#fef3c7', '#f59e0b', '#d97706', '#92400e']
                    },
                    textStyle: { fontSize: 10, color: '#64748b', fontFamily: 'Pretendard' }
                },
                // [수정] 박스 없이 우측 상단 텍스트만 배치 (클릭 방지 포함)
                graphic: [{
                    type: 'text',
                    right: 4,
                    top: 4,
                    z: 100,       // [핵심] 다른 모든 요소보다 위에 배치 (레이어 우선순위 최고)
                    silent: true, // 클릭 이벤트 무시 (지도 클릭 방해 금지)
                    style: {
                        text: `예측 환자 : ${patientCount}명`,
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
                    layoutCenter: ['50%', '50%'], layoutSize: '130%',
                    aspectScale: 0.9, selectedMode: false,
                    animationDurationUpdate: 300,
                    label: {
                        show: true,
                        formatter: function(params) {
                            return params.name === currentDistrict ? `{s|${params.name}}` : params.name;
                        },
                        rich: {
                            s: { fontSize: 18, fontWeight: '900', color: '#000', textBorderColor: '#fff', textBorderWidth: 3, fontFamily: 'Pretendard' }
                        },
                        color: '#64748b', fontWeight: '600', fontSize: 13, fontFamily: 'Pretendard'
                    },
                    itemStyle: { areaColor: '#ffffff', borderColor: '#cbd5e0', borderWidth: 1 },
                    emphasis: {
                        label: { show: true, fontWeight: '900', color: '#000000', fontFamily: 'Pretendard' },
                        itemStyle: { areaColor: null, borderColor: '#4f46e5', borderWidth: 2 }
                    },
                    data: data.map(item => {
                        const isSelected = item.name === currentDistrict;
                        return {
                            name: item.name,
                            value: item.rate,
                            itemStyle: isSelected ? {
                                borderColor: '#4f46e5', borderWidth: 4,
                                shadowBlur: 10, shadowColor: 'rgba(79, 70, 229, 0.5)'
                            } : {}
                        };
                    })
                }]
            };

            mapChart.setOption(option, { notMerge: false, lazyUpdate: true });
        }
    }

    function updateDisplay() {
        $('#districtSelect').text(currentDistrict);
        const modelLabel = currentModel === 'cold' ? '감기' : '천식';
        $('#dynamicTitle').text(`서울시 자치구별 ${modelLabel} 위험도`);
        const dateLabels = ['오늘', '내일', '모레', '3일 후'];
        const statusText = `${modelLabel} | ${dateLabels[currentDateIndex]}`;

        renderMap(rawData, statusText);
    }

    // 이벤트 리스너
    mapChart.on('click', function(params) {
        currentDistrict = params.name;
        updateDisplay();
    });

    $(document).on('click', '.district-option', function() {
        currentDistrict = $(this).text();
        updateDisplay();
    });

    $('input[name="modelType"]').on('change', function() {
        currentModel = $(this).val();
        updateDisplay();
    });

    $('.date-btn').on('click', function() {
        $('.date-btn').removeClass('active btn-primary');
        $(this).addClass('active btn-primary');
        currentDateIndex = parseInt($(this).data('date'));
        updateDisplay();
    });

    // 7. 선 그래프 설정 (폰트 Pretendard 적용)
    function createStepOption(title, data, mainColor) {
        return {
            grid: { top: '15%', left: '5%', right: '10%', bottom: '15%', containLabel: true },
            tooltip: {
                trigger: 'axis',
                textStyle: { fontFamily: 'Pretendard' }
            },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: ['3일전', '2일전', '1일전', '오늘', '내일', '모레', '글피'],
                axisLabel: { fontSize: 10, fontFamily: 'Pretendard' }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { type: 'dashed' } },
                axisLabel: { fontFamily: 'Pretendard' }
            },
            series: [{
                name: title, type: 'line', step: 'start', symbol: 'circle', symbolSize: 8, data: data,
                itemStyle: { color: mainColor }, lineStyle: { width: 3, color: mainColor },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: mainColor + '66' }, { offset: 1, color: mainColor + '00' }]) },
                markLine: { symbol: ['none', 'none'], label: { show: false }, data: [{ xAxis: '오늘', lineStyle: { color: '#cbd5e0', type: 'dashed', width: 1 } }] }
            }]
        };
    }
    coldChart.setOption(createStepOption('감기 환자수', [120, 130, 115, 145, 160, 175, 190], '#3b82f6'));
    asthmaChart.setOption(createStepOption('천식 환자수', [90, 85, 95, 110, 135, 150, 165], '#f59e0b'));

    updateDisplay();

    window.addEventListener('resize', function() {
        mapChart.resize(); coldChart.resize(); asthmaChart.resize();
    });
});