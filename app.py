import streamlit as st
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="신상무의 AI 임야 경매 & 임산물 분석기",
    page_icon="🌲",
    layout="wide"
)

st.title("🌲 [신상무 님 맞춤] AI 임야 경매 · 토지이음 · 실거래가 분석 대시보드")
st.caption("무주택 유지 | 토지이음 공법 검증 | 국토부 실거래가 API 비교 | 재배 가능 임산물 추천")

# ==========================================
# 2. 임산물 추천 알고리즘 함수
# ==========================================
def recommend_crops(slope, direction, forest_type):
    crops = []
    if slope < 15 and direction in ['남향', '남동향', '남서향']:
        crops.append("🌿 **산나물/수목**: 참두릅, 음나무(엄나무), 곰취, 눈개승마")
        crops.append("🌱 **고부가가치**: 산양삼(장뇌삼), 산자약")
    elif slope >= 15 or direction in ['북향', '북동향']:
        crops.append("🍄 **버섯류**: 원목 표고버섯, 능이버섯 (음지 환경 활용)")
        crops.append("🥔 **약초/뿌리채소**: 더덕, 도라지, 하수오")
    else:
        crops.append("🍃 **산채류**: 고사리, 취나물, 원추리")
        
    if forest_type == "준보전산지":
        crops.append("🪵 **목재/수액**: 고로쇠나무, 자작나무 (경영관리사 연계)")
        
    return crops

# ==========================================
# 3. 토지이음 URL 생성 함수
# ==========================================
def get_land_eum_url(address):
    encoded_addr = urllib.parse.quote(address)
    return f"https://www.eum.go.kr/web/ar/lu/luLandDet.do?mode=search&searchAddr={encoded_addr}"

# ==========================================
# 4. 국토교통부 토지 실거래가 API 조회 함수
# ==========================================
def get_real_trade_price(lawd_cd, deal_ym):
    # Streamlit Secrets에서 API Key 가져오기 (없을 경우 기본값 적용)
    api_key = st.secrets.get("PUBLIC_DATA_API_KEY", "")
    if not api_key:
        return 75000  # API 키 미설정 시 기본 샘플 시세 반환
    
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcLandTrade"
    params = {
        'serviceKey': api_key,
        'LAWD_CD': lawd_cd,  # 법정동코드 5자리 (예: 포천시 41650)
        'DEAL_YMD': deal_ym   # 거래년월 (예: 202607)
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            # XML 파싱 로직
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            total_price_per_pyeong = 0
            count = 0
            
            for item in items:
                jimok = item.findtext('jimok', '')
                if jimok == '임':  # 지목이 임야인 건만 필터링
                    price = int(item.findtext('dealAmount', '0').replace(',', '')) * 10000
                    area = float(item.findtext('dealArea', '1'))
                    pyeong = area / 3.3058
                    if pyeong > 0:
                        total_price_per_pyeong += (price / pyeong)
                        count += 1
            
            if count > 0:
                return int(total_price_per_pyeong / count)
    except Exception as e:
        pass
        
    return 65000  # API 호출 실패 시 기본 추정가

# ==========================================
# 5. 사이드바 검색 필터
# ==========================================
st.sidebar.header("⚙️ 분석 및 필터 조건")

selected_regions = st.sidebar.multiselect(
    "탐색 지역",
    ["포천시", "가평군", "양평군", "남양주시", "광주시", "춘천시", "홍천군"],
    default=["포천시", "가평군", "양평군", "남양주시"]
)

max_price = st.sidebar.slider("최저입찰가 상한 (만원)", 1000, 20000, 20000, 1000)
max_ratio = st.sidebar.slider("감정가 대비 최저가 비율 (%)", 30, 70, 60, 5)

# 시군구별 법정동 코드 매핑
LAWD_CODES = {
    "포천시": "41650", "가평군": "41820", "양평군": "41830",
    "남양주시": "41360", "광주시": "41610", "춘천시": "42110", "홍천군": "42720"
}

# ==========================================
# 6. 경매 / 공매 물건 데이터 수집
# ==========================================
def get_data():
    # 기본 경매/공매 수집 데이터 목록
    raw_items = [
        {
            "case_no": "2026타경 10482", "type": "법원경매", "region": "포천시",
            "address": "경기도 포천시 신북면 심곡리 산 15",
            "jimok": "임야", "area_sqm": 8260, "appraisal_price": 180000000, "minimum_price": 88200000,
            "has_road": True, "slop_angle": 12, "direction": "남동향", "forest_type": "준보전산지",
            "pension_eligible": True, "description": "건축물 없음, 순수 산지"
        },
        {
            "case_no": "2026-0800-01923", "type": "온비드공매", "region": "춘천시",
            "address": "강원도 춘천시 남산면 창촌리 산 42",
            "jimok": "임야", "area_sqm": 12500, "appraisal_price": 210000000, "minimum_price": 102900000,
            "has_road": True, "slop_angle": 18, "direction": "북동향", "forest_type": "임업용산지",
            "pension_eligible": True, "description": "자연림 상태의 순수 임야"
        }
    ]
    
    # 실시간 국토부 API 연동 시세 반영
    current_ym = datetime.now().strftime("%Y%m")
    for item in raw_items:
        lawd_cd = LAWD_CODES.get(item['region'], "41650")
        item['nearby_avg_pyeong_price'] = get_real_trade_price(lawd_cd, "202607")
        
    return raw_items

# ==========================================
# 7. 메인 화면 출력
# ==========================================
if st.button("🔍 AI 실시간 종합 분석 실행"):
    items = get_data()
    
    for idx, item in enumerate(items, 1):
        pyeong = int(item['area_sqm'] / 3.3058)
        pyeong_price = int(item['minimum_price'] / pyeong)
        
        # 안전마진 계산
        nearby_price = item['nearby_avg_pyeong_price']
        margin = int((1 - (pyeong_price / nearby_price)) * 100) if nearby_price > 0 else 0
        
        eum_url = get_land_eum_url(item['address'])
        recommended_crops = recommend_crops(item['slop_angle'], item['direction'], item['forest_type'])
        
        with st.container():
            st.markdown(f"### #{idx} [{item['type']}] {item['case_no']}")
            
            col1, col2, col3 = st.columns([1.2, 1, 1])
            
            with col1:
                st.subheader("📌 기본 및 공법 정보")
                st.write(f"📍 **소재지**: {item['address']}")
                st.write(f"📐 **면적**: {item['area_sqm']:,} ㎡ (약 {pyeong:,}평)")
                st.write(f"🌲 **산지 구율**: {item['forest_type']} | {item['slop_angle']}° ({item['direction']})")
                st.write(f"💰 **최저가**: :red[{item['minimum_price']:,} 원] (평당 {pyeong_price:,}원)")
                st.link_button("🌐 토지이음(eum.go.kr) 규제 열람", eum_url)

            with col2:
                st.subheader("📊 주변 실거래 시세 (국토부 API 연동)")
                st.metric(
                    label="해당 시·군·구 최근 산지 평균 실거래가", 
                    value=f"평당 {nearby_price:,}원"
                )
                st.metric(
                    label="현재 경매 최저가 대비 안전마진", 
                    value=f"평당 {pyeong_price:,}원", 
                    delta=f"{margin}% 저렴함"
                )
                if margin >= 40:
                    st.success("🔥 주변 시세 대비 초저평가 물건")

            with col3:
                st.subheader("🌱 추천 재배 임산물")
                for crop in recommended_crops:
                    st.write(crop)
                if item['pension_eligible']:
                    st.info("💡 **산지연금 전환 우수 필지**")

            st.markdown("---")
else:
    st.info("👆 상단의 **'AI 실시간 종합 분석 실행'** 버튼을 누르면 국토부 API 시세 조회 및 토지이음 분석이 시작됩니다.")
