import streamlit as st
import urllib.parse
import pandas as pd

# ==========================================
# 1. 페이지 및 CSS 설정 (원스톱 Dashboard UI)
# ==========================================
st.set_page_config(
    page_title="AI 농지(전) 경·공매 & 농지연금 통합 플랫폼",
    page_icon="🌾",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    h1 { font-size: 1.7rem !important; font-weight: 700; color: #15803D; }
    h2 { font-size: 1.3rem !important; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.3rem; margin-top: 1rem; }
    h3 { font-size: 1.05rem !important; font-weight: 600; }
    .stDataFrame { font-size: 11.5px !important; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem !important; font-weight: 700; }
    div[data-testid="stMetricLabel"] { font-size: 0.82rem !important; color: #4B5563; }
    .card-box {
        background-color: #F0FDF4;
        border: 1px solid #DCFCE7;
        border-radius: 8px;
        padding: 14px;
        margin-top: 8px;
        margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🌾 AI 농지(전) 경·공매 & 농지연금·임대 통합 플랫폼")
st.caption("Screening ➔ Valuation ➔ Farmland Pension & Lease Plan : 60세 농지연금 극대화 원스톱 분석기")

# ==========================================
# 2. 데이터 처리 및 백엔드 유틸리티 함수
# ==========================================
def fmt_price(total_price, pyeong):
    """총가격과 평당가격을 동시에 보기 좋게 포맷팅"""
    if not pyeong or pyeong <= 0:
        return f"{total_price:,.0f}원"
    
    per_pyeong = int(total_price / pyeong)
    
    if total_price >= 100000000:
        uk = int(total_price // 100000000)
        man = int((total_price % 100000000) // 10000)
        total_str = f"{uk}억 {man:,.0f}만원" if man > 0 else f"{uk}억원"
    elif total_price >= 10000:
        total_str = f"{int(total_price // 10000):,.0f}만원"
    else:
        total_str = f"{total_price:,.0f}원"
        
    if per_pyeong >= 10000:
        p_str = f"평당 {per_pyeong / 10000:,.1f}만원"
    else:
        p_str = f"평당 {per_pyeong:,.0f}원"
        
    return f"{total_str} ({p_str})"

def calc_farmland_pension(appraisal_price):
    """농지연금 추정액 산정 (감정가의 90% 반영 기준, 종신정액형/60세 기준 대략적 월 수령액)"""
    pension_base = appraisal_price * 0.90
    # 60세 가입 기준 감정가 1억원당 약 월 35~38만원 추산 (상한선 월 300만원 제한)
    est_monthly_pension = min(int((pension_base / 100000000) * 360000), 3000000)
    return pension_base, est_monthly_pension

def fetch_mock_farmland_database():
    """용도 '전' 중심의 경·공매 농지 샘플 데이터"""
    return [
        {
            "case_no": "2026타경 12048", "type": "법원경매", "region": "남양주시", 
            "address": "경기도 남양주시 진접읍 팔야리 105-3 ('전')", "area_sqm": 1320, # 약 400평
            "appraisal_price": 360000000, "minimum_price": 141120000, # 약 39% 낙찰 타겟
            "distance_km": 12.5, "ownership": "단독소유", "road_status": "🟢 접함 (포장도로)",
            "lease_est_annual": 1200000, "is_30km_ok": True
        },
        {
            "case_no": "온비드-2026-04102", "type": "온비드공매", "region": "포천시", 
            "address": "경기도 포천시 소흘읍 이동교리 412 ('전')", "area_sqm": 1650, # 약 500평
            "appraisal_price": 380000000, "minimum_price": 152000000, # 40% 수준
            "distance_km": 21.0, "ownership": "단독소유", "road_status": "🟢 접함 (농로)",
            "lease_est_annual": 1500000, "is_30km_ok": True
        },
        {
            "case_no": "2026타경 50921", "type": "법원경매", "region": "가평군", 
            "address": "경기도 가평군 청평면 대성리 88 ('전')", "area_sqm": 1050, # 약 318평 (1,000sqm 이상 경영체 가능)
            "appraisal_price": 320000000, "minimum_price": 128000000, # 40% 수준
            "distance_km": 28.5, "ownership": "단독소유", "road_status": "🟢 접함 (현황도로)",
            "lease_est_annual": 1000000, "is_30km_ok": True
        },
        {
            "case_no": "2026타경 33109", "type": "법원경매", "region": "양평군", 
            "address": "경기도 양평군 양서면 신원리 204 ('전')", "area_sqm": 1980, # 약 600평
            "appraisal_price": 450000000, "minimum_price": 180000000, 
            "distance_km": 34.0, "ownership": "단독소유", "road_status": "🟡 진입로 협소",
            "lease_est_annual": 1800000, "is_30km_ok": False # 30km 초과 리스크
        }
    ]

# ==========================================
# 3. 사이드바 검색 필터 (Form 수동 실행)
# ==========================================
with st.sidebar.form(key="search_form"):
    st.header("⚙️ 농지(전) 검색 필터")
    
    selected_regions = st.multiselect(
        "탐색 지역 선택 (거주지 인접)",
        ["남양주시", "포천시", "가평군", "양평군", "광주시"],
        default=["남양주시", "포천시", "가평군"]
    )

    show_court = st.checkbox("⚖️ 대법원 법원경매", value=True)
    show_onbid = st.checkbox("🌐 온비드 공매", value=True)
    only_30km = st.checkbox("📍 30km 이내 (농지연금 필수요건) 물건만 보기", value=True)
    max_price = st.slider("최저입찰가 상한 (만원)", 1000, 30000, 20000, 1000)

    search_submitted = st.form_submit_button("🔍 농지 검색 실행", type="primary", use_container_width=True)

# ==========================================
# 4. 데이터 가공
# ==========================================
raw_data = fetch_mock_farmland_database()
processed_list = []

for item in raw_data:
    if item['region'] not in selected_regions: continue
    if item['type'] == '법원경매' and not show_court: continue
    if item['type'] == '온비드공매' and not show_onbid: continue
    if only_30km and not item['is_30km_ok']: continue
    if item['minimum_price'] > (max_price * 10000): continue

    pyeong = int(item['area_sqm'] / 3.3058)
    p_base, est_monthly_p = calc_farmland_pension(item['appraisal_price'])

    item_dict = {
        **item,
        "pyeong": pyeong,
        "pension_base": p_base,
        "est_monthly_p": est_monthly_p
    }
    processed_list.append(item_dict)

# ==========================================
# [대분류 1] 농지 물건 요약 스크리닝
# ==========================================
st.subheader("1️⃣ [스크리닝] 경·공매 농지('전') 요약 비교")

if not processed_list:
    st.warning("선택 조건에 해당하는 농지 물건이 없습니다. 사이드바 조건을 조정 후 [🔍 농지 검색 실행]을 눌러주세요.")
else:
    df_master = pd.DataFrame(processed_list)
    
    df_display = pd.DataFrame({
        "유형": df_master['type'],
        "사건/물건번호": df_master['case_no'],
        "소재지 (지목: 전)": df_master['address'],
        "면적": df_master['pyeong'].apply(lambda x: f"{x:,}평 ({x*3.3:.0f}㎡)"),
        "거리 (30km 법칙)": df_master.apply(lambda r: f"🟢 {r['distance_km']}km (적합)" if r['is_30km_ok'] else f"🔴 {r['distance_km']}km (초과)", axis=1),
        "감정가": df_master.apply(lambda r: fmt_price(r['appraisal_price'], r['pyeong']), axis=1),
        "최저가 (낙찰 타겟)": df_master.apply(lambda r: f"{fmt_price(r['minimum_price'], r['pyeong'])} ({r['minimum_price']/r['appraisal_price']*100:.0f}%)", axis=1),
        "60세 예상 연금액": df_master['est_monthly_p'].apply(lambda x: f"월 약 {x/10000:,.0f}만원"),
        "도로/진입 여부": df_master['road_status']
    })

    st.dataframe(df_display, use_container_width=True, height=200)

    st.markdown("---")

    # ==========================================
    # 상세 분석 대상 농지 선택
    # ==========================================
    case_options = [f"[{r['type']}] {r['case_no']} - {r['address']} (감정가 대비 {r['minimum_price']/r['appraisal_price']*100:.0f}%)" for r in processed_list]
    selected_idx = st.selectbox("🔍 **상세 농지연금 & 위탁임대 분석을 수행할 농지를 선택하세요:**", range(len(case_options)), format_func=lambda x: case_options[x])
    
    target = processed_list[selected_idx]

    st.markdown(f"## 🎯 농지 심층 분석 리포트: {target['case_no']} (`{target['address']}`)")

    # ==========================================
    # [대분류 2] 가치평가 및 입찰 수지분석
    # ==========================================
    st.subheader("2️⃣ [가치평가] 입찰 전략 및 농지연금 평가액 분석")
    
    v_col1, v_col2, v_col3, v_col4 = st.columns(4)
    v_col1.metric("감정평가액", fmt_price(target['appraisal_price'], target['pyeong']))
    v_col2.metric("최저입찰가 (40% 수준)", fmt_price(target['minimum_price'], target['pyeong']))
    v_col3.metric("농지연금 인정 가치 (감정가 90%)", fmt_price(target['pension_base'], target['pyeong']))
    v_col4.metric("거주지 거리 (30km 법칙)", f"{target['distance_km']} km", delta="연금 가입 적합" if target['is_30km_ok'] else "거리 초과 주의")

    st.markdown("<div class='card-box'>", unsafe_allow_html=True)
    st.markdown("### 💡 AI 추천 3단계 농지 입찰 전략")
    
    conservative_bid = int(target['minimum_price'] * 1.02)
    optimal_bid = int(target['minimum_price'] * 1.08)
    aggressive_bid = int(target['appraisal_price'] * 0.48)

    bid_df = pd.DataFrame({
        "전략 구분": ["최저가 입찰 (유찰 노림)", "AI 추천 적정가 (낙찰 유력)", "공격적 입찰 (경쟁 시)"],
        "추천 입찰가 (총액 / 평당가)": [fmt_price(bid_val, target['pyeong']) for bid_val in [conservative_bid, optimal_bid, aggressive_bid]],
        "감정가 대비 비율": [f"{bid_val / target['appraisal_price'] * 100:.1f}%" for bid_val in [conservative_bid, optimal_bid, aggressive_bid]],
        "예상 투자금 대비 연금 평가비율": [f"{int((target['pension_base'] / bid_val) * 100)}%" for bid_val in [conservative_bid, optimal_bid, aggressive_bid]],
        "입찰 전략 해설": [
            "약 39~40%선 단독 낙찰을 노리는 보수적 전략",
            "경·공매 경쟁 감안시 가장 권장되는 2억 원 완결 입찰가",
            "입지 조건 및 진입 도로 양호 시 낙찰율 우위 전략"
        ]
    })
    st.table(bid_df)
    st.markdown("</div>", unsafe_allow_html=True)

    # 2-4. 입찰 소요 자금 & 기반시설 세팅 계산기
    with st.expander("💰 농지 취득 필요 총예산 산정 계산기 (총예산 2억 원 완결 플랜)"):
        calc_col1, calc_col2 = st.columns(2)
        with calc_col1:
            bid_price_input = st.number_input(
                "입찰 예정 금액 입력 (원)", 
                value=optimal_bid, 
                step=1000000,
                help="금액을 입력하시면 취득세, 기반시설 조성비가 포함된 총 예산이 계산됩니다."
            )
            st.caption(f"💡 입력 금액 환산: **{fmt_price(bid_price_input, target['pyeong'])}**")
            
            deposit = int(target['minimum_price'] * 0.10) if target['type'] == '법원경매' else int(bid_price_input * 0.10)
            acquisition_tax = int(bid_price_input * 0.034)  # 농지 취득세 3.4% (지방교육세 포함)
            infra_cost = 35000000  # 농막, 용수(지하수), 전기, 예초장비, 농지정지 작업비 약 3,500만원
            total_required = bid_price_input + acquisition_tax + infra_cost
        
        with calc_col2:
            st.write(f"- **입찰 보증금**: `{fmt_price(deposit, target['pyeong'])}`")
            st.write(f"- **농지 취득세 (3.4%)**: `{fmt_price(acquisition_tax, target['pyeong'])}`")
            st.write(f"- **기반시설 조성비 (농막/전기/지하수 등)**: `약 3,500 만원`")
            st.markdown(f"👉 **총 필요 예산 (매입+기반조성)**: **`{fmt_price(total_required, target['pyeong'])}`**")
            if total_required <= 200000000:
                st.success("✅ 목표 예산 2억 원 이내 완결 가능물건입니다!")
            else:
                st.warning("⚠️ 총 예산이 2억 원을 초과합니다. 입찰가를 조율하세요.")

    st.markdown("---")

    # ==========================================
    # [대분류 3] 60세 농지연금 & 위탁임대 출구전략
    # ==========================================
    st.subheader("3️⃣ [수익화] 만 60세 농지연금 & 농지은행 위탁임대 수지분석")

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("60세 도달 시 예상 월 연금 수령액", f"월 {target['est_monthly_p']/10000:,.0f} 만원", help="종신정액형 기준 추정치")
    m_col2.metric("농지은행 예상 연간 임대 수입", f"연 {target['lease_est_annual']/10000:,.0f} 만원/년")
    m_col3.metric("영농경력 / 보유기간 요건", "5년 / 2년 이상 필요")

    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        with st.expander("📌 만 60세 농지연금 신청을 위한 필수 3대 조건 점검"):
            st.markdown("1. **농지 보유 기간 2년 이상**: 취득 후 2년 경과 필수 (조기 매입 시 충족)")
            st.markdown("2. **영농 경력 5년 이상**: 농업경영체 등록 후 주말 투잡으로 5년 이력 유지")
            st.markdown(f"3. **거주지 거리 제한 (30km 법칙)**: 현재 {target['distance_km']}km로 **{'🟢 조건 충족' if target['is_30km_ok'] else '🔴 거리 초과 (가입 불가)'}**")

    with exp_col2:
        with st.expander("🚨 농지 경·공매 낙찰 필수 리스크 체크리스트"):
            st.write("1. **농취증(농지취득자격증명)**: 낙찰 후 7일 이내 제출 필수 (미제출 시 보증금 몰수)")
            st.write(f"2. **소유 형태**: {target['ownership']} (단독 소유 물건 필수)")
            st.write(f"3. **진입 도로 / 영농 가능성**: {target['road_status']}")

    # ==========================================
    # 5. 하단 버튼 및 외부 링크
    # ==========================================
    st.markdown("---")
    b_col1, b_col2 = st.columns([2, 1])
    
    with b_col1:
        encoded_addr = urllib.parse.quote(target['address'])
        st.markdown(f"🔗 **외부 데이터 바로가기**: [🗺️ 네이버지도 지도보기](https://map.naver.com/v5/search/{encoded_addr}) | [🌾 농지은행 연금산정](https://www.fbo.or.kr)")
    
    with b_col2:
        csv_data = pd.DataFrame([target]).to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 농지 심층 분석 리포트 다운로드 (CSV)",
            data=csv_data,
            file_name=f"농지분석_{target['case_no'].replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary"
        )
