import streamlit as st
import pandas as pd
import urllib.parse

# ==========================================
# 1. 페이지 및 UI 기본 설정
# ==========================================
st.set_page_config(
    page_title="농지 자경 및 농지연금 통합 분석기",
    page_icon="🌾",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    h1 { font-size: 1.6rem !important; font-weight: 700; color: #15803D; }
    h2 { font-size: 1.25rem !important; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.3rem; margin-top: 1rem; }
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

st.title("🌾 농지 자경(경영체 5년) & 농지연금 통합 플랫폼")
st.caption("1단계: 농지은행 임대 데이터 분석(자경 5년) ➔ 2단계: 경·공매 저가 낙찰을 통한 60세 농지연금 극대화")

# Helper Functions
def fmt_price(total_price):
    if not total_price or total_price <= 0:
        return "0원"
    if total_price >= 100000000:
        uk = int(total_price // 100000000)
        man = int((total_price % 100000000) // 10000)
        return f"{uk}억 {man:,.0f}만원" if man > 0 else f"{uk}억원"
    elif total_price >= 10000:
        return f"{int(total_price // 10000):,.0f}만원"
    return f"{total_price:,.0f}원"

# ==========================================
# 2. 탭(Tab) 구성을 통한 2단계 로드맵 제공
# ==========================================
tab1, tab2 = st.tabs([
    "🌱 [1단계] 농지은행 임대물건 탐색 (자경 5년 이력 구축)", 
    "⚖️ [2단계] 농지 경·공매 & 농지연금 플랜 (60세 연금 극대화)"
])

# ------------------------------------------
# TAB 1: 농지은행 임대물건 분석 (엑셀/CSV 업로드)
# ------------------------------------------
with tab1:
    st.subheader("🌱 [1단계] 농지은행 임대 데이터 직접 분석")
    st.markdown("""
    > **💡 이용 안내**: [농지은행 포털(fbo.or.kr)](https://www.fbo.or.kr)에서 다운로드한 **임대 물건 엑셀(CSV) 파일**을 업로드하세요.
    > 파일이 없는 경우, 아래 내장된 기본 샘플 데이터로 기능 테스트를 진행할 수 있습니다.
    """)

    uploaded_lease_file = st.file_uploader("📥 농지은행 임대물건 엑셀/CSV 파일 업로드", type=["csv", "xlsx"])

    if uploaded_lease_file is not None:
        try:
            if uploaded_lease_file.name.endswith('.csv'):
                df_lease_raw = pd.read_csv(uploaded_lease_file)
            else:
                df_lease_raw = pd.read_excel(uploaded_lease_file)
            st.success(f"✅ '{uploaded_lease_file.name}' 파일 업로드 완료 ({len(df_lease_raw)}건의 매물 파싱됨)")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
            df_lease_raw = None
    else:
        st.info("ℹ️ 업로드된 파일이 없어 테스트용 예시 데이터 세트가 제공됩니다.")
        df_lease_raw = pd.DataFrame([
            {"물건번호": "LEASE-2026-001", "소재지": "경기도 남양주시 진접읍 팔야리 210", "지목": "전", "면적_sqm": 1320, "연임대료": 600000, "거주지거리_km": 12.0, "관할지사": "경기지역본부 (1577-7770)"},
            {"물건번호": "LEASE-2026-002", "소재지": "경기도 포천시 소흘읍 직동리 145", "지목": "전", "면적_sqm": 1650, "연임대료": 750000, "거주지거리_km": 21.5, "관할지사": "포천울진지사 (031-538-8100)"},
            {"물건번호": "LEASE-2026-003", "소재지": "경기도 가평군 청평면 상천리 88", "지목": "전", "면적_sqm": 850, "연임대료": 400000, "거주지거리_km": 28.0, "관할지사": "가평지사 (031-580-1500)"}
        ])

    if df_lease_raw is not None and not df_lease_raw.empty:
        # 데이터 가공
        df_lease_raw['평수'] = (df_lease_raw['면적_sqm'] / 3.3058).astype(int)
        df_lease_raw['경영체등록가능'] = df_lease_raw['면적_sqm'].apply(lambda x: "🟢 가능 (1,000㎡ 이상)" if x >= 1000 else "🔴 불가능 (1,000㎡ 미만)")
        df_lease_raw['월임대료'] = (df_lease_raw['연임대료'] / 12).astype(int)

        # 요약 데이터프레임 시각화
        df_display = pd.DataFrame({
            "물건번호": df_lease_raw['물건번호'],
            "소재지": df_lease_raw['소재지'],
            "지목": df_lease_raw['지목'],
            "면적": df_lease_raw.apply(lambda r: f"{r['평수']:,}평 ({r['면적_sqm']:,}㎡)", axis=1),
            "연 임대료": df_lease_raw['연임대료'].apply(fmt_price),
            "월 임대 부담금": df_lease_raw['월임대료'].apply(lambda x: f"월 {x/10000:,.1f}만원"),
            "경영체 등록 자격": df_lease_raw['경영체등록가능'],
            "관할지사": df_lease_raw['관할지사']
        })

        st.dataframe(df_display, use_container_width=True, height=220)

        st.markdown("---")
        st.markdown("### 📋 임대 대상 농지 심층 자경검토")
        
        target_idx = st.selectbox(
            "자경 요건을 분석할 농지를 선택하세요:",
            range(len(df_lease_raw)),
            format_func=lambda x: f"{df_lease_raw.iloc[x]['소재지']} ({df_lease_raw.iloc[x]['평수']}평 / 연 {fmt_price(df_lease_raw.iloc[x]['연임대료'])})"
        )
        
        target = df_lease_raw.iloc[target_idx]

        c1, c2, c3 = st.columns(3)
        c1.metric("임대 면적", f"{target['평수']:,} 평 ({target['면적_sqm']:,} ㎡)")
        c2.metric("예상 월 임대 부담금", f"월 {target['월임대료']/10000:,.1f} 만원")
        c3.metric("농업경영체 등록 조건", "🟢 충족" if target['면적_sqm'] >= 1000 else "🔴 불가능")

        st.markdown("<div class='card-box'>", unsafe_allow_html=True)
        st.markdown(f"#### 📝 `{target['소재지']}` 자경 실행 계획")
        st.write(f"1. **경영체 요건**: 면적 **{target['면적_sqm']:,}㎡**로 법정 최소 기준인 1,000㎡(약 303평)를 **{'충족하여 경영체 등록이 가능합니다.' if target['면적_sqm'] >= 1000 else '미달합니다. (추가 농지 임차 필요)'}**")
        st.write(f"2. **계약 체결 문의**: 관할 지사(`{target['관할지사']}`)로 문의하여 농지은행 임대차 계약 체결")
        st.write("3. **주말 농업 경영**: 두릅, 엄나무 등 손이 적게 가는 다년생 작물 재배 ➔ 농산물품질관리원에 **농업경영체 등록 후 5년 경력 축적**")
        st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------
# TAB 2: 농지 경·공매 & 농지연금 플랜 (파일 업로드 및 직관 분석)
# ------------------------------------------
with tab2:
    st.subheader("⚖️ [2단계] 만 60세 농지연금 극대화를 위한 경·공매 저가 낙찰 분석")
    st.markdown("""
    > **💡 핵심 전략**: 감정가 대비 **35~40% 수준(약 1.4억~1.6억 원)**으로 유찰된 농지를 낙찰받아, 
    > 만 60세 도달 시 **감정가 90% 기준 높은 농지연금**을 수령하는 수익성 구조를 분석합니다.
    """)

    uploaded_auc_file = st.file_uploader("📥 경·공매 농지 물건 엑셀/CSV 파일 업로드 (선택)", type=["csv", "xlsx"])

    if uploaded_auc_file is not None:
        try:
            if uploaded_auc_file.name.endswith('.csv'):
                df_auc_raw = pd.read_csv(uploaded_auc_file)
            else:
                df_auc_raw = pd.read_excel(uploaded_auc_file)
            st.success(f"✅ '{uploaded_auc_file.name}' 업로드 완료")
        except Exception as e:
            st.error(f"오류: {e}")
            df_auc_raw = None
    else:
        df_auc_raw = pd.DataFrame([
            {"사건번호": "2026타경 12048", "구분": "법원경매", "소재지": "경기도 남양주시 진접읍 팔야리 105-3 ('전')", "면적_sqm": 1320, "감정가": 360000000, "최저가": 141120000, "거리_km": 12.5, "도로상태": "🟢 포장도로 접함"},
            {"사건번호": "온비드-2026-04102", "구분": "온비드공매", "소재지": "경기도 포천시 소흘읍 이동교리 412 ('전')", "면적_sqm": 1650, "감정가": 380000000, "최저가": 152000000, "거리_km": 21.0, "도로상태": "🟢 농로 접함"},
            {"사건번호": "2026타경 50921", "구분": "법원경매", "소재지": "경기도 가평군 청평면 대성리 88 ('전')", "면적_sqm": 1050, "감정가": 320000000, "최저가": 128000000, "거리_km": 28.5, "도로상태": "🟢 현황도로 접함"}
        ])

    df_auc_raw['평수'] = (df_auc_raw['면적_sqm'] / 3.3058).astype(int)
    df_auc_raw['연금인정가'] = (df_auc_raw['감정가'] * 0.90).astype(int)
    df_auc_raw['예상월연금'] = df_auc_raw['연금인정가'].apply(lambda x: min(int((x / 100000000) * 360000), 3000000))

    # 요약 표
    df_auc_disp = pd.DataFrame({
        "구분": df_auc_raw['구분'],
        "사건/물건번호": df_auc_raw['사건번호'],
        "소재지": df_auc_raw['소재지'],
        "면적": df_auc_raw['평수'].apply(lambda x: f"{x:,}평"),
        "감정가": df_auc_raw['감정가'].apply(fmt_price),
        "최저가 (낙찰 타겟)": df_auc_raw.apply(lambda r: f"{fmt_price(r['최저가'])} ({r['최저가']/r['감정가']*100:.0f}%)", axis=1),
        "60세 연금 인정가 (90%)": df_auc_raw['연금인정가'].apply(fmt_price),
        "예상 월 연금액": df_auc_raw['예상월연금'].apply(lambda x: f"월 약 {x/10000:,.0f}만원"),
        "30km 법칙": df_auc_raw['거리_km'].apply(lambda x: "🟢 적합" if x <= 30 else "🔴 초과")
    })

    st.dataframe(df_auc_disp, use_container_width=True, height=200)

    st.markdown("---")
    auc_target_idx = st.selectbox(
        "🔍 상세 수익성 및 입찰 예산을 산정할 농지를 선택하세요:",
        range(len(df_auc_raw)),
        format_func=lambda x: f"[{df_auc_raw.iloc[x]['구분']}] {df_auc_raw.iloc[x]['사건번호']} - {df_auc_raw.iloc[x]['소재지']}"
    )

    auc_target = df_auc_raw.iloc[auc_target_idx]

    st.markdown(f"### 🎯 농지연금 심층 분석: {auc_target['사건번호']}")

    ac1, ac2, ac3, ac4 = st.columns(4)
    ac1.metric("감정평가액", fmt_price(auc_target['감정가']))
    ac2.metric("최저입찰가 (40%선)", fmt_price(auc_target['최저가']))
    ac3.metric("농지연금 평가액 (90%)", fmt_price(auc_target['연금인정가']))
    ac4.metric("60세 예상 월 연금 수령액", f"월 {auc_target['예상월연금']/10000:,.0f} 만원")

    st.markdown("<div class='card-box'>", unsafe_allow_html=True)
    st.markdown("#### 💰 총 투자 예산 대비 연금 가치 평가")
    bid_est = int(auc_target['최저가'] * 1.05)
    total_required = bid_est + 35000000  # 취득세 + 기반시설비 약 3,500만원
    st.write(f"• **예상 낙찰가 (최저가 대비 105%)**: `{fmt_price(bid_est)}`")
    st.write(f"• **총 필요 예산 (낙찰가 + 기반시설/세금 3.5천)**: **`{fmt_price(total_required)}`**")
    st.write(f"• **만 60세 농지연금 담보 인정액**: **`{fmt_price(auc_target['연금인정가'])}`**")
    st.write(f"👉 **자산 가치 증대율**: 투입예산 대비 **`{int((auc_target['연금인정가'] / total_required) * 100)}%` 인정** (2억 원 이내 완결 플랜 적합)")
    st.markdown("</div>", unsafe_allow_html=True)
