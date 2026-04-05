$(document).ready(function() {
    // 1. 차트 인스턴스 초기화
    const mapChart = echarts.init(document.getElementById('map'));
    const coldChart = echarts.init(document.getElementById('forecastChart1'));
    const asthmaChart = echarts.init(document.getElementById('forecastChart2'));

    // 2. 상태 관리 변수 (통합 인덱스 사용)
    // 인덱스: 0(3일전), 1(2일전), 2(1일전), 3(오늘), 4(내일), 5(모레), 6(3일후)
    let currentDistrict = "강남구";
    let currentModel = 'cold';
    let currentDateIndex = 3; // 기본값: 오늘
    let seoulGeoJson = null;

    // 3. 자치구 리스트
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
                    formatter: function(value) { return (value * 100).toFixed(0) + '%'; }
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
                    layoutCenter: ['50%', '50%'], layoutSize: '130%',
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

    // 5. 통합 데이터 가져오기 함수 (과거+현재미래 통합)
    function getMergedData(disease, index, district) {
        // index 0,1,2 -> prevData / index 3,4,5,6 -> rawData
        if (index < 3) {
            return prevData[disease][index][district] || null;
        } else {
            return rawData[disease][index - 3][district] || null;
        }
    }

    function updateDisplay() {
        if (typeof rawData === 'undefined' || typeof prevData === 'undefined') return;

        const diseaseKey = currentModel === 'cold' ? '감기' : '천식';
        const seoulAvg = currentModel === 'cold' ? 62.44 : 3.6;

        $('#districtSelect').text(currentDistrict);
        $('#dynamicTitle').text(`서울시 자치구별 ${diseaseKey} 위험도`);

        // 상단 요약 카드 업데이트 (오늘~3일후 수치)
        $('.summary-val').each(function(index) {
            if (index === 0) return; // 미세먼지 패스
            const targetIdx = index + 2; // index 1(오늘)은 전체배열의 3번 인덱스
            const data = getMergedData(diseaseKey, targetIdx, currentDistrict);
            if (data) {
                $(this).text(`${data.pred_cnt}명`);
            }
        });

        // 라인 차트 업데이트
        updateLineCharts();

        // 현재 선택된 날짜의 지도 데이터 생성
        const targetDayObj = (currentDateIndex < 3) ? prevData[diseaseKey][currentDateIndex] : rawData[diseaseKey][currentDateIndex - 3];

        const filteredData = Object.entries(targetDayObj).map(([distName, details]) => ({
            name: distName,
            value: details.pred_rate / seoulAvg,
            realRate: details.pred_rate,
            cnt: details.pred_cnt,
            itemStyle: distName === currentDistrict ? {
                shadowBlur: 20,
                shadowColor: 'rgba(0, 0, 0, 0.4)',
                areaColor: null
            } : { shadowBlur: 0 }
        }));

        const values = filteredData.map(d => d.value);
        renderMap(filteredData, `${diseaseKey} 위험도`, Math.min(...values), Math.max(...values));

        // 우측 체감형 지표 (선택된 날짜 기준)
        const selectedInfo = getMergedData(diseaseKey, currentDateIndex, currentDistrict);
        if (selectedInfo) {
            const riskRatio = (selectedInfo.pred_rate / seoulAvg) * 100;
            const level = riskRatio > 120 ? '위험' : riskRatio > 90 ? '보통' : '안전';
            const colorClass = riskRatio > 120 ? 'text-danger' : riskRatio > 90 ? 'text-warning' : 'text-success';
            const barClass = riskRatio > 120 ? 'bg-danger' : riskRatio > 90 ? 'bg-warning' : 'bg-success';

            const dateLabels = ['3일전', '2일전', '1일전', '오늘', '내일', '모레', '3일후'];

            $('#risk-progress-section').html(`
                <div class="mb-4">
                    <div class="d-flex justify-content-between small mb-2">
                        <span class="fw-bold">${currentDistrict} (${dateLabels[currentDateIndex]})</span>
                        <span class="${colorClass} fw-bold">${level} (${riskRatio.toFixed(0)}%)</span>
                    </div>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar ${barClass}" style="width: ${Math.min(riskRatio, 100)}%"></div>
                    </div>
                </div>
            `);
        }
    }

    function updateLineCharts() {
        const diseases = ['감기', '천식'];
        const charts = [coldChart, asthmaChart];

        diseases.forEach((dis, idx) => {
            const fullData = [];
            for(let i=0; i<7; i++) {
                const d = getMergedData(dis, i, currentDistrict);
                fullData.push(d ? d.pred_cnt : 0);
            }
            charts[idx].setOption({ series: [{ data: fullData }] });
        });
    }

    // 6. 이벤트 리스너
    mapChart.on('click', function(params) {
        currentDistrict = params.name;
        updateDisplay();
    });

    $(document).on('click', '.district-option', function(e) {
        e.preventDefault();
        currentDistrict = $(this).text().trim();
        updateDisplay();
    });

    $('input[name="modelType"]').on('change', function() {
        currentModel = $(this).val();
        updateDisplay();
    });

    $('.date-btn').on('click', function() {
        $('.date-btn').removeClass('active btn-primary');
        $(this).addClass('active btn-primary');
        // HTML의 data-date(0~3)를 전체 인덱스(3~6)로 변환
        currentDateIndex = parseInt($(this).data('date')) + 3;
        updateDisplay();
    });

    // 7. 차트 초기화
    function createStepOption(title, mainColor) {
        return {
            grid: { top: '15%', left: '5%', right: '10%', bottom: '15%', containLabel: true },
            tooltip: { trigger: 'axis' },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: ['3일전', '2일전', '1일전', '오늘', '내일', '모레', '글피'],
                axisLabel: { fontSize: 10, color: '#64748b' }
            },
            yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
            series: [{
                name: title,
                type: 'line',
                smooth: true,
                symbolSize: 8,
                itemStyle: { color: mainColor },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: mainColor + '44' },
                        { offset: 1, color: mainColor + '00' }
                    ])
                }
            }]
        };
    }

    coldChart.setOption(createStepOption('감기 환자수', '#3b82f6'));
    asthmaChart.setOption(createStepOption('천식 환자수', '#f59e0b'));

    updateDisplay();

    window.addEventListener('resize', function() {
        mapChart.resize(); coldChart.resize(); asthmaChart.resize();
    });
});