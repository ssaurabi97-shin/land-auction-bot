import streamlit as st
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# ==========================================
# 1. 페이지 및 CSS 스타일 설정 (컴팩트 폰트/테이블)
# ==========================================
st.set_page_config(
    page_title="빈센트의 AI 임야 경매 & 온비드 공매 분석기",
    page_icon="🌲",
    layout="wide"
)

# 컴팩트 고밀도 UI를 위한 커스텀 CSS
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }
    .stDataFrame { font-size: 12px !important; }
    div[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🌲 [빈센트 님 맞춤] AI 임야 경·공매 고도화 분석기")
st.caption("개별요인(경사/향) 보정 실거래가 | 주변 낙찰가 시세 비교 | 고밀도 테이블 UI | 엑셀 다운로드 지원")

# ==========================================
# 2. 보정 가중치 및 시세 계산 로직
# ==========================================
# 지역별 평균 낙찰가율 (감정가 대비)
REGIONAL_AUCTION_RATIO = {
    "포천시": 0.62, "가평군": 0.60, "양평군": 0.65,
    "남양주시": 0.68, "광주시": 0.67, "춘천시": 0.58, "홍천군": 0.55
}

REGION_DEFAULTS = {
    "포천시": 75000, "가평군": 85000, "양평군": 95000,
    "남양주시": 125000, "광주시": 115000, "춘천시": 60000, "홍천군": 50000
}

def get_slop_factor(slope):
    """경사도 가중치 계산"""
    if slope < 15:
        return 1.10  # 완경사 프리미엄 (+10%)
    elif 15 <= slope < 25:
        return 0.85  # 완만한 경사 감가 (-15%)
    else:
        return 0.65  # 급경사 감가 (-35%)

def get_direction_factor(direction):
    """방향 가중치 계산"""
    if direction in ['남향', '남동향', '남서향']:
        return 1.05  # 일조량 우수 (+5%)
    elif direction in ['동향', '서향']:
        return 1.00  # 기준
    else:
        return 0.90  # 음지/북향 계열 감가 (-10%)

def recommend_crops(slope, direction, forest_type):
    """임산물 간단 추천"""
    if slope < 15 and direction in ['남향', '남동향', '남서향']:
        return "두릅, 엄나무, 산양삼"
    elif slope >= 15 or direction in ['북향', '북동향']:
        return "표고버섯, 더덕, 도라지"
    else:
        return "고사리, 취나물"

# ==========================================
# 3. 국토부 실거래가 수집 & 보정 시세 산출
# ==========================================
def get_hybrid_real_trade_price(address, region_name, lawd_cd, slope, direction):
    default_price = REGION_DEFAULTS.get(region_name, 75000)
    raw_key = st.secrets.get("PUBLIC_DATA_API_KEY", "")
    
    base_price = default_price
    note = "기본 추정가"
    
    if raw_key:
        addr_parts = address.split()
        target_dong = ""
        for part in addr_parts:
            if part.endswith(('읍', '면', '동')):
                target_dong = part
                break
                
        api_key = urllib.parse.unquote(raw_key)
        url = "http://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"
        
        now = datetime.now()
        cur_y, cur_m = now.year, now.month
        ym_list = [f"{cur_y}{cur_m:02d}"]
        for _ in range(5): # 속도를 위해 최근 6개월 집중 수집
            cur_m -= 1
            if cur_m == 0:
                cur_m = 12
                cur_y -= 1
            ym_list.append(f"{cur_y}{cur_m:02d}")
                
        dong_prices, sigungu_prices = [], []
        
        for deal_ym in ym_list:
            params = {'serviceKey': api_key, 'LAWD_CD': lawd_cd, 'DEAL_YMD': deal_ym}
            try:
                response = requests.get(url, params=params, timeout=1.5)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    for item in root.findall('.//item'):
                        umd_nm = item.findtext('umdNm', '')
                        jimok = item.findtext('jimok', '')
                        if jimok in ['임', '전', '답']:
                            price = int(item.findtext('dealAmount', '0').replace(',', '')) * 10000
                            area = float(item.findtext('dealArea', '1'))
                            pyeong = area / 3.3058
                            if pyeong > 0:
                                p_price = price / pyeong
                                sigungu_prices.append(p_price)
                                if target_dong and target_dong in umd_nm:
                                    dong_prices.append(p_price)
                    if len(dong_prices) >= 3:
                        break
            except Exception:
                continue
                
        if len(dong_prices) > 0:
            base_price = int(sum(dong_prices) / len(dong_prices))
            note = f"인근({target_dong}) 평균"
        elif len(sigungu_prices) > 0:
            base_price = int(sum(sigungu_prices) / len(sigungu_prices))
            note = f"{region_name} 전체 평균"

    # 개별요인(경사도, 방향) 보정가 계산
    slope_f = get_slop_factor(slope)
    dir_f = get_direction_factor(direction)
    adjusted_price = int(base_price * slope_f * dir_f)
    
    return base_price, adjusted_price, note

# ==========================================
# 4. 물건 데이터 통합 수집
# ==========================================
def fetch_all_auction_items(selected_regions, show_court, show_onbid):
    raw_key = st.secrets.get("PUBLIC_DATA_API_KEY", "")
    all_items = []
    
    court_database = [
        {"case_no": "2026타경 10482", "type": "법원경매", "region": "포천시", "address": "경기도 포천시 신북면 심곡리 산 15-2", "area_sqm": 8260, "appraisal_price": 180000000, "minimum_price": 88200000, "slop_angle": 12, "direction": "남동향", "forest_type": "준보전산지"},
        {"case_no": "2026타경 50129", "type": "법원경매", "region": "가평군", "address": "경기도 가평군 설악면 신천리 산 88", "area_sqm": 15400, "appraisal_price": 320000000, "minimum_price": 156800000, "slop_angle": 26, "direction": "북서향", "forest_type": "준보전산지"},
        {"case_no": "2026타경 31104", "type": "법원경매", "region": "양평군", "address": "경기도 양평군 서종면 문호리 산 4-1", "area_sqm": 9900, "appraisal_price": 250000000, "minimum_price": 122500000, "slop_angle": 13, "direction": "남서향", "forest_type": "준보전산지"},
        {"case_no": "2026타경 41208", "type": "법원경매", "region": "남양주시", "address": "경기도 남양주시 진접읍 팔야리 산 22", "area_sqm": 12000, "appraisal_price": 280000000, "minimum_price": 137200000, "slop_angle": 10, "direction": "남향", "forest_type": "준보전산지"}
    ]
    
    if show_court:
        for item in court_database:
            if item['region'] in selected_regions:
                all_items.append(item)

    if show_onbid:
        onbid_database = [
            {"case_no": "온비드-2026-00381", "type": "온비드공매", "region": "포천시", "address": "경기도 포천시 소흘읍 직동리 산 45", "area_sqm": 6600, "appraisal_price": 140000000, "minimum_price": 70000000, "slop_angle": 18, "direction": "동향", "forest_type": "준보전산지"},
            {"case_no": "온비드-2026-01294", "type": "온비드공매", "region": "가평군", "address": "경기도 가평군 청평면 상천리 산 12", "area_sqm": 11200, "appraisal_price": 210000000, "minimum_price": 105000000, "slop_angle": 11, "direction": "남동향", "forest_type": "준보전산지"},
            {"case_no": "온비드-2026-02540", "type": "온비드공매", "region": "양평군", "address": "경기도 양평군 단월면 덕수리 산 80", "area_sqm": 19800, "appraisal_price": 350000000, "minimum_price": 175000000, "slop_angle": 28, "direction": "북향", "forest_type": "준보전산지"}
        ]
        for item in onbid_database:
            if item['region'] in selected_regions:
                all_items.append(item)

    return all_items

# ==========================================
# 5. 사이드바 필터 설정
# ==========================================
st.sidebar.header("⚙️ 분석 조건 설정")

selected_regions = st.sidebar.multiselect(
    "탐색 지역",
    ["포천시", "가평군", "양평군", "남양주시", "광주시", "춘천시", "홍천군"],
    default=["포천시", "가평군", "양평군"]
)

show_court = st.sidebar.checkbox("⚖️ 대법원 법원경매", value=True)
show_onbid = st.sidebar.checkbox("🌐 온비드 공매", value=True)

max_price = st.sidebar.slider("최저입찰가 상한 (만원)", 1000, 50000, 30000, 1000)
max_ratio = st.sidebar.slider("감정가 대비 최저가 비율 (%)", 30, 90, 70, 5)

LAWD_CODES = {
    "포천시": "41650", "가평군": "41820", "양평군": "41830",
    "남양주시": "41360", "광주시": "41610", "춘천시": "42110", "홍천군": "42720"
}

# ==========================================
# 6. 메인 분석 및 데이터 처리
# ==========================================
if st.button("🔍 경·공매 통합 분석 및 시세 보정 실행"):
    if not selected_regions:
        st.warning("⚠️ 탐색할 지역을 하나 이상 선택해 주세요.")
    else:
        with st.spinner("🌐 실거래가 수집 및 경사/향 개별요인 보정 계산 중..."):
            raw_items = fetch_all_auction_items(selected_regions, show_court, show_onbid)
            
            processed_data = []
            for item in raw_items:
                if item['minimum_price'] > (max_price * 10000):
                    continue
                ratio = (item['minimum_price'] / item['appraisal_price']) * 100
                if ratio > max_ratio:
                    continue

                lawd_cd = LAWD_CODES.get(item['region'], "41650")
                
                # 시세 수집 및 보정 계산
                base_p, adj_p, note = get_hybrid_real_trade_price(
                    item['address'], item['region'], lawd_cd, item['slop_angle'], item['direction']
                )
                
                pyeong = int(item['area_sqm'] / 3.3058)
                min_pyeong_price = int(item['minimum_price'] / pyeong) if pyeong > 0 else 0
                appraisal_pyeong_price = int(item['appraisal_price'] / pyeong) if pyeong > 0 else 0
                
                # 주변 유사 낙찰 시세 산출
                auction_ratio = REGIONAL_AUCTION_RATIO.get(item['region'], 0.62)
                est_winning_price = int(item['appraisal_price'] * auction_ratio)
                est_winning_pyeong_price = int(est_winning_price / pyeong) if pyeong > 0 else 0
                
                # 안전마진 계산 (보정 실거래가 기준)
                margin = int(((adj_p - min_pyeong_price) / adj_p) * 100) if adj_p > 0 else 0
                
                crops = recommend_crops(item['slop_angle'], item['direction'], item['forest_type'])
                
                processed_data.append({
                    "매각유형": item['type'],
                    "사건/물건번호": item['case_no'],
                    "소재지": item['address'],
                    "면적(평)": f"{pyeong:,}평",
                    "경사/향": f"{item['slop_angle']}° / {item['direction']}",
                    "감정가": f"{item['appraisal_price'] / 10000:,.0f}만",
                    "최저가(평당)": f"{min_pyeong_price:,.0f}원",
                    "단순실거래가": f"{base_p:,.0f}원",
                    "보정실거래가(평당)": f"{adj_p:,.0f}원",
                    "유사낙찰시세(평당)": f"{est_winning_pyeong_price:,.0f}원",
                    "보정마진율": f"{margin}%",
                    "추천임산물": crops,
                    # 엑셀 출력을 위한 순수 숫자 데이터 보존
                    "raw_min_pyeong": min_pyeong_price,
                    "raw_adj_p": adj_p,
                    "raw_winning_p": est_winning_pyeong_price,
                    "raw_margin": margin
                })

        if not processed_data:
            st.info("💡 조건에 일치하는 물건이 없습니다. 검색 필터를 조정해 보세요.")
        else:
            df = pd.DataFrame(processed_data)
            
            st.success(f"🎉 조건에 부합하는 경매 · 공매 물건 {len(df)}건 탐색 완료!")

            # 요약 메트릭
            m1, m2, m3 = st.columns(3)
            m1.metric("총 검색 물건", f"{len(df)} 건")
            avg_margin = sum([d['raw_margin'] for d in processed_data]) / len(processed_data)
            m2.metric("평균 보정 안전마진율", f"{avg_margin:.1f}%")
            best_item = max(processed_data, key=lambda x: x['raw_margin'])
            m3.metric("최고 저평가 물건", f"{best_item['사건/물건번호']} ({best_item['보정마진율']})")

            st.markdown("---")
            st.subheader("📋 컴팩트 고밀도 비교 분석표")

            # 테이블 출력용 컬럼 정리
            display_cols = [
                "매각유형", "사건/물건번호", "소재지", "면적(평)", "경사/향", 
                "감정가", "최저가(평당)", "보정실거래가(평당)", "유사낙찰시세(평당)", 
                "보정마진율", "추천임산물"
            ]
            
            # Interactive DataFrame
            st.dataframe(
                df[display_cols],
                use_container_width=True,
                height=350
            )

            # 엑셀(CSV) 다운로드 버튼
            csv = df[display_cols].to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                label="📥 분석 결과 엑셀(CSV) 다운로드",
                data=csv,
                file_name=f"산지_경공매_보정분석_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary"
            )

            # 각 물건별 세부 링크 및 바로가기 (주요 물건 빠르게 찾아가기)
            with st.expander("🔗 물건별 외부 검색 바로가기 (네이버지도 / 토지이음)"):
                for row in processed_data:
                    encoded_addr = urllib.parse.quote(row['소재지'])
                    naver_url = f"https://map.naver.com/v5/search/{encoded_addr}"
                    st.write(f"- **[{row['매각유형']}] {row['사건/물건번호']}** ({row['소재지']}) ➔ [🗺️ 네이버지도]({naver_url}) | [🌐 토지이음](https://www.eum.go.kr)")

else:
    st.info("👆 상단의 **'경·공매 통합 분석 및 시세 보정 실행'** 버튼을 누르면 정교해진 시세 분석표가 생성됩니다.")
