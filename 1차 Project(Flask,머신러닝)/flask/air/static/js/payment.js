document.addEventListener('DOMContentLoaded', function() {
    const payBtn = document.getElementById('btn-payment');

    if (payBtn) {
        payBtn.addEventListener('click', async function(e) {
            e.preventDefault();

            try {
                const uniqueId = `AIR-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

                // V2 신규 결제 요청 방식
                const response = await PortOne.requestPayment({
                    storeId: "store-f08e3c4f-9747-4a14-bb95-1248d572788b", // 상점 ID
                    channelKey: "channel-key-3616e108-455c-482b-a283-b2f405e72114", // 채널 키
                    paymentId: uniqueId,
                    orderName: "AIR 서비스 Pro 구독 (1개월)",
                    totalAmount: 1900,
                    currency: "CURRENCY_KRW",
                    payMethod: "CARD", // 대문자로 작성
                    customer: {
                        fullName: "홍길동",
                        email: "test@example.com",
                        phoneNumber: "010-1234-5678",
                    },
                });

                // 결제 종료 후 처리
                if (response.code != null) {
                    // 오류 발생 시 code가 존재함
                    alert("결제 실패: " + response.message);
                } else {
                    // 성공 시
                    console.log("결제 성공:", response);
                    alert("🎉 결제가 성공했습니다!");
                }
            } catch (error) {
                console.error("결제 프로세스 에러:", error);
                alert("결제창을 불러오는 중 오류가 발생했습니다.");
            }
        });
    }
});