$(document).ready(function() {
    // 1. 차트 인스턴스 초기화
    const mapChart = echarts.init(document.getElementById('map'));
    const coldChart = echarts.init(document.getElementById('forecastChart1'));
    const asthmaChart = echarts.init(document.getElementById('forecastChart2'));

    // 2. 상태 관리 변수
    let currentDistrict = "강남구";
    let currentModel = 'cold';
    let currentDateIndex = 0;
    let seoulGeoJson = null;

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
            const districtData = data.find(item => item.name === currentDistrict);
            const patientDisplay = (districtData && districtData.cnt) ? districtData.cnt : 0;

            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'item',
                    formatter: function(params) {
                        if (params.data) {
                            // [수정] 상대 지수(value)를 백분율로 표시하여 위험도 체감 강조
                            const riskPercent = (params.data.value * 100).toFixed(1);
                            return `<div style="font-family: Pretendard; padding: 5px;">
                                        <b style="font-size: 14px;">${params.name}</b><br/>
                                        <span style="color: #4f46e5;">예측 환자: <b>${params.data.cnt}</b>명</span><br/>
                                        <small>발생률: ${params.data.realRate.toFixed(2)} (1만명 당)</small><br/>
                                        <small style="color: #ef4444;">위험지수: 평균의 ${riskPercent}%</small>
                                    </div>`;
                        }
                        return params.name;
                    },
                    transitionDuration: 0,
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderWidth: 0,
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 0, 0, 0.1)',
                    textStyle: { color: '#1e293b', fontFamily: 'Pretendard' }
                },
                visualMap: {
                    // [수정] 절대 수치가 아닌 '상대 지수(Ratio)' 기준으로 척도 설정
                    // 1.0(평균)을 중심으로 0.8(낮음) ~ 1.5(높음) 범위를 강조
                    // 천식의 경우 8.0(평균 3.6의 약 2.2배)이 들어오면 아주 진한 색이 됩니다.
                    min: mapMin || 0.8,
                    max: mapMax || currentModel === 'cold' ? 1.3 : 2.0,
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
                    formatter: function(value) { return (value * 100).toFixed(0) + '%'; }
                },
                graphic: [{
                    type: 'text',
                    right: 4, top: 4, z: 100,
                    silent: true,
                    style: {
                        text: `예측 환자 : ${patientDisplay}명`,
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
                        itemStyle: { areaColor: null, borderColor: '#4f46e5', borderWidth: 2 , z: 5 }
                    },
                    data: data.map(item => ({
                        name: item.name,
                        value: item.value, // [수정] 색상 결정은 riskIndex(상대지수) 기준
                        realRate: item.realRate, // 툴팁용 실제값 보존
                        cnt: item.cnt,
                        itemStyle: item.name === currentDistrict ? {
                            borderColor: '#4f46e5', borderWidth: 4, z: 10 // 선택된 구 레이어 최상단
                        } : {}
                    }))
                }]
            };

            mapChart.setOption(option, { notMerge: false, lazyUpdate: true });
        }
    }

    function updateDisplay() {
        if (typeof rawData === 'undefined' || !rawData) {
            console.warn("데이터가 아직 로드되지 않았습니다.");
            return;
        }

        const modelLabel = currentModel === 'cold' ? '감기' : '천식';
        const diseaseKey = currentModel === 'cold' ? '감기' : '천식';

        // [수정] SQL로 구한 서울시 전체 기간 평균 발생률 (1만명 당)
        const seoulAvg = currentModel === 'cold' ? 62.44 : 3.6;

        $('#districtSelect').text(currentDistrict);
        $('#dynamicTitle').text(`서울시 자치구별 ${modelLabel} 위험도`);

        const targetObj = (rawData[diseaseKey] && rawData[diseaseKey][currentDateIndex])
                          ? rawData[diseaseKey][currentDateIndex]
                          : null;

        if (!targetObj) {
            console.error(`${diseaseKey}의 ${currentDateIndex}일 데이터가 없습니다.`, rawData);
            return;
        }

        // [수정] 데이터를 상대 지수(Index) 형태로 가공
        const filteredData = Object.entries(targetObj).map(([distName, details]) => {
            const rate = details.pred_rate;
            // 위험 지수 = 현재 구의 예측 발생률 / 서울 전체 평균
            const riskIndex = rate / seoulAvg;

            return {
                name: distName,
                value: riskIndex,      // visualMap 매핑용 (1.0 기준)
                realRate: rate,        // 실제 발생률 (예: 8.0)
                cnt: details.pred_cnt
            };
        });

        // [추가] 데이터의 실제 범위를 구해서 visualMap에 강제로 대비를 줌
        const values = filteredData.map(d => d.value);
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);

        // 편차가 거의 없는 경우를 위해 보정 (값이 완전히 같을 때 에러 방지)
        let mapMin, mapMax;
        if (minVal === maxVal) {
            mapMin = minVal * 0.7;
            mapMax = maxVal * 1.3;
        } else {
            // [핵심] 범위를 데이터에 딱 맞게(Tight) 설정하여 색상 차이를 극대화
            mapMin = minVal;
            mapMax = maxVal;
        }

        const dateLabels = ['오늘', '내일', '모레', '3일 후'];
        const statusText = `${modelLabel} | ${dateLabels[currentDateIndex]}`;

        renderMap(filteredData, statusText, mapMin, mapMax);
    }

    // 이벤트 리스너 (기존 로직 유지)
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