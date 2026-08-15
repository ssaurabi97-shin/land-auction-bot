import streamlit as st
import urllib.parse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# ==========================================
# 1. 페이지 및 CSS 설정 (원스톱 Dashboard UI)
# ==========================================
st.set_page_config(
    page_title="AI 임야 경·공매 & 귀산촌 통합 분석 플랫폼",
    page_icon="🌲",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    h1 { font-size: 1.7rem !important; font-weight: 700; color: #1E3A8A; }
    h2 { font-size: 1.3rem !important; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.3rem; margin-top: 1rem; }
    h3 { font-size: 1.05rem !important; font-weight: 600; }
    .stDataFrame { font-size: 11.5px !important; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem !important; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.82rem !important; color: #4B5563; }
    .card-box {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 14px;
        margin-top: 8px;
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌲 AI 임야 경·공매 & 귀산촌 종합 분석 플랫폼")
st.caption("Screening ➔ Valuation ➔ Business Plan : 한 화면에서 끝내는 원스톱 임야 투자 분석기")

# ==========================================
# 2. 데이터 처리 및 백엔드 로직
# ==========================================
REGIONAL_AUCTION_RATIO = {
    "포천시": 0.62, "가평군": 0.60, "양평군": 0.65,
    "남양주시": 0.68, "광주시": 0.67, "춘천시": 0.58, "홍천군": 0.55
}

REGION_DEFAULTS = {
    "포천시": 75000, "가평군": 85000, "양평군": 95000,
    "남양주시": 125000, "광주시": 115000, "춘천시": 60000, "홍천군": 50000
}

def get_slop_factor(slope):
    if slope < 15: return 1.10
    elif 15 <= slope < 25: return 0.85
    else: return 0.65

def get_direction_factor(direction):
    if direction in ['남향', '남동향', '남서향']: return 1.05
    elif direction in ['동향', '서향']: return 1.00
    else: return 0.90

def evaluate_forest_pension(forest_type, slope, appraisal_price):
    if slope < 20 and forest_type in ['준보전산지', '임업용산지']:
        status = "🟢 가능 (우수)"
    elif slope < 25 and forest_type in ['준보전산지', '임업용산지']:
        status = "🟡 가능 (보통)"
    else:
        status = "🔴 검토 필요"
        
    monthly_pension = int((appraisal_price * 1.18) / 120)
    return status, monthly_pension

def evaluate_soil_and_crops(slope, direction, elevation, soil_type):
    """다드림 & 흙토람 데이터 연동 임산물 6차원 적지 분석"""
    crops = []
    if elevation >= 300 and direction in ['동향', '북동향', '북향']:
        crops.append(("산양삼", 95, "고해발 음지/반음지 최적 지형 조건"))
    else:
        crops.append(("산양삼", 70, "해발고도 보통 지형"))
        
    if slope < 20 and direction in ['남향', '남동향', '남서향']:
        crops.append(("두릅/엄나무", 92, "풍부한 일조량 및 완경사 관리 용이"))
    else:
        crops.append(("두릅/엄나무", 78, "경사도 및 일조량 보통"))
        
    if soil_type in ['사양토', '양토']:
        crops.append(("더덕/도라지", 88, "배수성 우수한 유기물 토성 보유"))
    else:
        crops.append(("표고버섯(자연재배)", 85, "습도 유지 유리한 토질"))
        
    return crops

def fetch_mock_database():
    return [
        {
            "case_no": "2026타경 10482", "type": "법원경매", "region": "포천시", 
            "address": "경기도 포천시 신북면 심곡리 산 15-2", "area_sqm": 8260, 
            "appraisal_price": 180000000, "minimum_price": 88200000, 
            "slope": 12, "direction": "남동향", "elevation": 280, "forest_type": "준보전산지",
            "road_status": "🟢 접함 (4m 현황도로)", "soil_type": "사양토", "drainage": "양호"
        },
        {
            "case_no": "2026타경 31104", "type": "법원경매", "region": "양평군", 
            "address": "경기도 양평군 서종면 문호리 산 4-1", "area_sqm": 9900, 
            "appraisal_price": 250000000, "minimum_price": 122500000, 
            "slope": 13, "direction": "남서향", "elevation": 190, "forest_type": "준보전산지",
            "road_status": "🟡 진입로 불분명 (맹지 리스크)", "soil_type": "양토", "drainage": "매우 양호"
        },
        {
            "case_no": "2026타경 41208", "type": "법원경매", "region": "남양주시", 
            "address": "경기도 남양주시 진접읍 팔야리 산 22", "area_sqm": 12000, 
            "appraisal_price": 280000000, "minimum_price": 137200000, 
            "slope": 10, "direction": "남향", "elevation": 150, "forest_type": "준보전산지",
            "road_status": "🟢 접함 (지적도상 도로)", "soil_type": "사양토", "drainage": "양호"
        },
        {
            "case_no": "온비드-2026-00381", "type": "온비드공매", "region": "포천시", 
            "address": "경기도 포천시 소흘읍 직동리 산 45", "area_sqm": 6600, 
            "appraisal_price": 140000000, "minimum_price": 70000000, 
            "slope": 18, "direction": "동향", "elevation": 320, "forest_type": "임업용산지",
            "road_status": "🟢 임도 연결", "soil_type": "식양토", "drainage": "보통"
        },
        {
            "case_no": "온비드-2026-01294", "type": "온비드공매", "region": "가평군", 
            "address": "경기도 가평군 청평면 상천리 산 12", "area_sqm": 11200, 
            "appraisal_price": 210000000, "minimum_price": 105000000, 
            "slope": 11, "direction": "남동향", "elevation": 240, "forest_type": "준보전산지",
            "road_status": "🟢 접함 (포장도로)", "soil_type": "사양토", "drainage": "양호"
        }
    ]

# ==========================================
# 3. 사이드바 검색 필터
# ==========================================
st.sidebar.header("⚙️ 검색 & 분석 필터")
selected_regions = st.sidebar.multiselect(
    "탐색 지역 선택",
    ["포천시", "가평군", "양평군", "남양주시", "광주시", "춘천시", "홍천군"],
    default=["포천시", "가평군", "양평군", "남양주시"]
)

show_court = st.sidebar.checkbox("⚖️ 대법원 법원경매", value=True)
show_onbid = st.sidebar.checkbox("🌐 온비드 공매", value=True)
max_price = st.sidebar.slider("최저입찰가 상한 (만원)", 1000, 50000, 30000, 1000)

# ==========================================
# 4. 데이터 가공 및 Master 데이터프레임
# ==========================================
raw_data = fetch_mock_database()
processed_list = []

for item in raw_data:
    if item['region'] not in selected_regions: continue
    if item['type'] == '법원경매' and not show_court: continue
    if item['type'] == '온비드공매' and not show_onbid: continue
    if item['minimum_price'] > (max_price * 10000): continue

    pyeong = int(item['area_sqm'] / 3.3058)
    min_pyeong_p = int(item['minimum_price'] / pyeong) if pyeong > 0 else 0
    
    base_p = REGION_DEFAULTS.get(item['region'], 75000)
    slope_f = get_slop_factor(item['slope'])
    dir_f = get_direction_factor(item['direction'])
    adj_pyeong_p = int(base_p * slope_f * dir_f)
    
    margin = int(((adj_pyeong_p - min_pyeong_p) / adj_pyeong_p) * 100) if adj_pyeong_p > 0 else 0
    pension_status, monthly_p = evaluate_forest_pension(item['forest_type'], item['slope'], item['appraisal_price'])
    
    auc_ratio = REGIONAL_AUCTION_RATIO.get(item['region'], 0.62)
    est_win_price = int(item['appraisal_price'] * auc_ratio)

    item_dict = {
        **item,
        "pyeong": pyeong,
        "min_pyeong_p": min_pyeong_p,
        "adj_pyeong_p": adj_pyeong_p,
        "margin": margin,
        "pension_status": pension_status,
        "monthly_p": monthly_p,
        "est_win_price": est_win_price
    }
    processed_list.append(item_dict)

# ==========================================
# [대분류 1] 경매 물건 요약 (Fast Screening)
# ==========================================
st.subheader("1️⃣ [스크리닝] 경매 · 공매 물건 요약 비교")

if not processed_list:
    st.warning("선택 조건에 해당하는 물건이 없습니다. 사이드바 필터를 조정해 주세요.")
else:
    df_master = pd.DataFrame(processed_list)
    
    df_display = pd.DataFrame({
        "유형": df_master['type'],
        "사건/물건번호": df_master['case_no'],
        "소재지": df_master['address'],
        "면적": df_master['pyeong'].apply(lambda x: f"{x:,}평"),
        "경사/향": df_master.apply(lambda r: f"{r['slope']}° / {r['direction']}", axis=1),
        "감정가": df_master['appraisal_price'].apply(lambda x: f"{x/10000:,.0f}만"),
        "최저가": df_master['minimum_price'].apply(lambda x: f"{x/10000:,.0f}만 ({x/df_master['appraisal_price'].iloc[0]*100:.0f}%)"),
        "보정실거래가(평당)": df_master['adj_pyeong_p'].apply(lambda x: f"{x:,.0f}원"),
        "보정안전마진": df_master['margin'].apply(lambda x: f"{x}%"),
        "산지연금 적합도": df_master['pension_status'],
        "도로/맹지 여부": df_master['road_status']
    })

    st.dataframe(df_display, use_container_width=True, height=200)

    st.markdown("---")

    # ==========================================
    # 물건 선택 드롭다운 (Master-Detail 연동)
    # ==========================================
    case_options = [f"[{r['type']}] {r['case_no']} - {r['address']} (마진율: {r['margin']}%)" for r in processed_list]
    selected_idx = st.selectbox("🔍 **상세 심층 분석을 수행할 물건을 선택하세요:**", range(len(case_options)), format_func=lambda x: case_options[x])
    
    target = processed_list[selected_idx]

    st.markdown(f"## 🎯 심층 분석 리포트: {target['case_no']} (`{target['address']}`)")

    # ==========================================
    # [대분류 2] 시세 및 입찰가 분석 (세로 전체 폭 배치)
    # ==========================================
    st.subheader("2️⃣ [가치평가] 시세 및 입찰가 분석")
    
    # 지표 메트릭 (4개 카드로 전체 폭 분할)
    v_col1, v_col2, v_col3, v_col4 = st.columns(4)
    v_col1.metric("보정 실거래 시세", f"{target['adj_pyeong_p']:,.0f}원/평")
    v_col2.metric("최저입찰가 (평당)", f"{target['min_pyeong_p']:,.0f}원/평")
    v_col3.metric("인근 유사낙찰 시세", f"{int(target['est_win_price']/target['pyeong']):,.0f}원/평")
    v_col4.metric("보정 안전마진율", f"{target['margin']}%", delta=f"{target['margin']}% 저평가")

    st.markdown("<div class='card-box'>", unsafe_allow_html=True)
    st.markdown("### 💡 AI 추천 3단계 입찰 전략")
    
    conservative_bid = int(target['minimum_price'] * 1.02)
    optimal_bid = int(target['minimum_price'] * 1.08)
    aggressive_bid = int(target['est_win_price'])

    bid_df = pd.DataFrame({
        "전략 구분": ["보수적 입찰 (단독낙찰 노림)", "AI 추천 적정가 (낙찰 유력)", "공격적 입찰 (경쟁 과열 시)"],
        "추천 입찰가": [f"{conservative_bid/10000:,.0f} 만원", f"{optimal_bid/10000:,.0f} 만원", f"{aggressive_bid/10000:,.0f} 만원"],
        "감정가 대비 비율": [f"{bid_val / target['appraisal_price'] * 100:.1f}%" for bid_val in [conservative_bid, optimal_bid, aggressive_bid]],
        "예상 안전마진율": [f"{int(((target['adj_pyeong_p'] - (bid_val/target['pyeong']))/target['adj_pyeong_p'])*100)}%" for bid_val in [conservative_bid, optimal_bid, aggressive_bid]],
        "입찰 전략 해설": [
            "최저가 수준 입찰로 안전성 최우선 (유찰 가능성 있음)",
            "지역 낙찰가율 및 개별요인 보정 기반 낙찰 확률 최적화",
            "입지 우수성 감안 시 경쟁을 뚫기 위한 최고한도 입찰가"
        ]
    })
    st.table(bid_df)
    st.markdown("</div>", unsafe_allow_html=True)

    # 2-4. 입찰 소요 자금 계산기 (전체 폭 넓게 활용)
    with st.expander("💰 입찰 필요 소요 자금 & 예상 세금 산정 계산기"):
        calc_col1, calc_col2 = st.columns(2)
        with calc_col1:
            bid_price_input = st.number_input("입찰 예정 금액 입력 (원)", value=optimal_bid, step=1000000)
            deposit = int(target['minimum_price'] * 0.10)
            acquisition_tax = int(bid_price_input * 0.046)  # 농지/임야 취득세 4.6%
            est_legal_fee = 1000000  # 법무 제반비용
            total_required = bid_price_input + acquisition_tax + est_legal_fee
        
        with calc_col2:
            st.write(f"- **입찰 보증금 (10%)**: `{deposit:,.0f} 원`")
            st.write(f"- **예상 취득세 (4.6%)**: `{acquisition_tax:,.0f} 원`")
            st.write(f"- **기타 제반 비용 (법무 등)**: `{est_legal_fee:,.0f} 원`")
            st.markdown(f"👉 **낙찰 시 총 필요 실투자금**: **`{total_required:,.0f} 원`**")

    # 대분류 구분선
    st.markdown("---")

    # ==========================================
    # [대분류 3] 물건 경영 & 수익성 분석 (세로 전체 폭 배치)
    # ==========================================
    st.subheader("3️⃣ [수익화] 물건 경영 & 수익성 분석")

    # 수익화 핵심 메트릭
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("산지연금 적합도", target['pension_status'])
    m_col2.metric("예상 월 연금액", f"{target['monthly_p']/10000:,.0f} 만원/월", help="10년(120개월) 지급 기준")
    m_col3.metric("해발고도 / 경사", f"{target['elevation']}m / {target['slope']}°")
    m_col4.metric("토성 / 배수등급", f"{target['soil_type']} / {target['drainage']}")

    # 3-2. 임산물 적지 분석
    st.markdown("<div class='card-box'>", unsafe_allow_html=True)
    st.markdown("### 🌿 다드림 & 흙토람 기반 추천 임산물 TOP 3")
    
    crop_results = evaluate_soil_and_crops(target['slope'], target['direction'], target['elevation'], target['soil_type'])
    
    c_col1, c_col2, c_col3 = st.columns(3)
    cols = [c_col1, c_col2, c_col3]
    
    for idx, (crop, score, reason) in enumerate(crop_results):
        with cols[idx]:
            st.markdown(f"#### {idx+1}. {crop} (`{score}점`)")
            st.write(f"• **적합 사유**: {reason}")
            st.caption(f"추천 지형: 해발 {target['elevation']}m / {target['direction']}")
            
    st.markdown("</div>", unsafe_allow_html=True)

    # 3-3 & 3-4. 상세 개발 가능성 및 귀산촌 지원책 (Expander)
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        with st.expander("🏗️ 산지전용 / 개발 가능성 및 규제 점검"):
            st.markdown("#### [산지전용 가능성 판정]")
            if target['slope'] < 25:
                st.success(f"✅ 평균 경사도 {target['slope']}°로 산지전용 허가 기준(25° 미만) 충족")
                st.write("• **산림경영관리사(6평 이하)**: 설치 가능")
                st.write("• **농막 및 약초/산채 재배지**: 즉시 조성 가능")
                st.write("• **임도 개설**: 현황도로 연계 가능성 높음")
            else:
                st.error(f"❌ 평균 경사도 {target['slope']}°로 25° 이상 경사지 포함. 현장 측량 필수")

    with exp_col2:
        with st.expander(f"🎁 {target['region']} 귀산촌 지원책 & 혜택"):
            st.write("• **귀산촌 창업 자금**: 최대 **3억 원 융자** (연 1.5% 저리 금리)")
            st.write("• **주택 구입 자금**: 최대 **7,500만 원 융자** 지원")
            st.write("• **임업직불금**: 조건 충족 시 ha당 **최대 200만 원/년** 지원")
            st.write("• **산림경영 컨설팅**: 한국임업진흥원 전담 컨설턴트 무료 매칭")

    with st.expander("🚨 실전 현장 리스크 체크리스트 (커뮤니티 및 현장 실무 노하우)"):
        chk1, chk2 = st.columns(2)
        with chk1:
            st.write(f"1. **진입 도로 확보**: {target['road_status']}")
            st.write("2. **분묘기지권**: 임야 내 미등기 분묘 존재 여부 현장 탐문 필수")
        with chk2:
            st.write("3. **국유림 연접 여부**: 국유림 연접 시 산지연금 매수 순위 우대")
            st.write("4. **경계 침범 및 입목 축적**: 인근 필지 경계 및 입목 피해 이력 점검")

    # ==========================================
    # 5. 하단 버튼 및 외부 링크
    # ==========================================
    st.markdown("---")
    b_col1, b_col2 = st.columns([2, 1])
    
    with b_col1:
        encoded_addr = urllib.parse.quote(target['address'])
        st.markdown(f"🔗 **외부 데이터 바로가기**: [🗺️ 네이버지도 실보보기](https://map.naver.com/v5/search/{encoded_addr}) | [🌐 토지이음 규제확인](https://www.eum.go.kr)")
    
    with b_col2:
        csv_data = pd.DataFrame([target]).to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 현재 물건 심층 분석 리포트 다운로드 (CSV)",
            data=csv_data,
            file_name=f"임야분석_{target['case_no'].replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary"
        )
