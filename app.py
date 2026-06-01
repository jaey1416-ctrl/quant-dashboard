import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
import google.generativeai as genai

st.set_page_config(page_title="Pro Quant Dashboard", layout="wide")

# ---------------------------------------------------------
# 💡 [핵심] 한글 이름 매핑 딕셔너리 (UI 디테일 업그레이드)
# ---------------------------------------------------------
TICKER_MAP = {
    "QQQ": "QQQ (나스닥 기술주)",
    "SPY": "SPY (S&P 500)",
    "NVDA": "엔비디아 (NVDA)",
    "AAPL": "애플 (AAPL)",
    "BTC-USD": "비트코인 (BTC)",
    "ETH-USD": "이더리움 (ETH)",
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스"
}

# ⚙️ 사이드바 설정
st.sidebar.header("⚙️ 포트폴리오 설정")

# 유저에게는 예쁜 한글(value)을 보여주고, 코드 내부적으로는 진짜 티커(key)를 씁니다.
raw_tickers = st.sidebar.multiselect(
    "분석할 종목", 
    options=list(TICKER_MAP.keys()), 
    default=["QQQ", "005930.KS"],
    format_func=lambda x: TICKER_MAP[x]
)

start_date = st.sidebar.date_input("시작일", date.today() - timedelta(days=365))
end_date = st.sidebar.date_input("종료일", date.today())

if not raw_tickers:
    st.warning("종목을 선택해 주세요!")
    st.stop()

# 대시보드 전체에서 쓰일 한글 이름 리스트 생성
display_tickers = [TICKER_MAP[t] for t in raw_tickers]

@st.cache_data
def get_data(tickers, start, end):
    data = yf.download(tickers, start=start, end=end)['Close']
    # 1개 종목만 선택했을 때 데이터 구조가 깨지는 것 방지
    if isinstance(data, pd.Series):
        data = pd.DataFrame(data, columns=[tickers[0]])
    return data

df = get_data(raw_tickers, start_date, end_date)
# 다운로드한 데이터프레임의 영어 열(Column) 이름을 모두 한글로 교체!
df.rename(columns=TICKER_MAP, inplace=True)

# ---------------------------------------------------------
# 상단 KPI 요약 패널
# ---------------------------------------------------------
st.title("⚡ Pro 퀀트 통합 대시보드")
st.markdown("---")

cols = st.columns(len(display_tickers)) 
for i, ticker in enumerate(display_tickers):
    with cols[i]:
        valid_data = df[ticker].dropna()
        if len(valid_data) >= 2:
            latest_price = valid_data.iloc[-1]
            prev_price = valid_data.iloc[-2]
            change_pct = ((latest_price - prev_price) / prev_price) * 100
            # 한국 주식은 소수점이 없으므로 통화 단위를 섞어서 표기
            st.metric(label=f"💰 {ticker} 현재가", value=f"{latest_price:,.2f}", delta=f"{change_pct:.2f}%")
        else:
            st.metric(label=f"💰 {ticker} 현재가", value="데이터 대기 중", delta="-")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 과거 가격 흐름", 
    "🔥 자산 상관관계", 
    "🎲 몬테카를로 시뮬레이션", 
    "📰 실시간 시장 뉴스",
    "🎯 백테스트 리포트"
])

with tab1:
    st.subheader("📊 선택 자산의 장기 주가 추세")
    chart_mode = st.radio(
        "👁️ 차트 보기 모드 선택",
        options=["1. 종목별 개별 차트 분리 (권장)", "2. 정규화 수익률 비교 (출발선 0% 통일)", "3. 단순 통합 차트 (원본 가격)"],
        horizontal=True
    )
    if chart_mode == "1. 종목별 개별 차트 분리 (권장)":
        st.info("💡 **가이드:** 각 자산의 고유한 가격 변동성을 왜곡 없이 볼 수 있도록 분리된 차트를 제공합니다.")
        fig_1 = make_subplots(rows=len(display_tickers), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=display_tickers)
        for i, ticker in enumerate(display_tickers):
            fig_1.add_trace(go.Scatter(x=df.index, y=df[ticker], name=ticker), row=i+1, col=1)
        fig_1.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig_1.update_layout(height=300 * len(display_tickers), showlegend=False)
        st.plotly_chart(fig_1, use_container_width=True)
    elif chart_mode == "2. 정규화 수익률 비교 (출발선 0% 통일)":
        st.info("💡 **가이드:** 모든 자산의 첫날을 0%로 맞추어, 동일 기간 동안 어떤 자산이 가장 높은 수익률(%)을 기록했는지 공정하게 겨룹니다.")
        clean_df = df.dropna()
        norm_df = (clean_df / clean_df.iloc[0] - 1) * 100 
        fig_2 = px.line(norm_df, labels={'value': '누적 수익률 (%)', 'Date': '날짜'})
        fig_2.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig_2.update_layout(height=500)
        st.plotly_chart(fig_2, use_container_width=True)
    else:
        st.info("💡 **가이드:** 자산들의 실제 가격(또는 원화)을 그대로 겹쳐서 보여줍니다. 체급이 다르면 차트가 왜곡됩니다.")
        fig_3 = px.line(df, labels={'value': '원본 가격', 'Date': '날짜'})
        fig_3.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig_3.update_layout(height=500)
        st.plotly_chart(fig_3, use_container_width=True)

with tab2:
    st.subheader("🧬 포트폴리오 자산 간 상관관계 분석")
    if len(display_tickers) >= 2:
        st.info("💡 **차트 해석 가이드:** 붉은색(+1)에 가까울수록 똑같이 움직이고, 푸른색(-1)에 가까울수록 반대로 움직여 위험 방어(헤징) 효과가 큽니다.")
        corr_matrix = df.pct_change().dropna().corr()
        fig_corr = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='RdBu_r', zmin=-1, zmax=1)
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("상관관계 매트릭스를 확인하려면 좌측 사이드바에서 종목을 2개 이상 선택해 주세요.")

with tab3:
    st.subheader("🎲 미래 30일 주가 경로 및 자산 시뮬레이션")
    target_ticker = st.selectbox("시뮬레이션 타겟 종목", display_tickers)
    
    init_investment = st.number_input(f"💵 '{target_ticker}'에 투자할 금액을 입력하세요 (달러/원화)", min_value=10, value=1000, step=100)
    
    st.info(f"""
    💡 **차트 해석 가이드:**
    1. **상단 차트 (주가 추세 예측):** 과거 1년 통계를 바탕으로 미래 30일 동안 주가가 움직일 수 있는 확률적 범위를 보여줍니다.
    2. **하단 차트 (내 자산 가치 변화):** 입력하신 초기 투자금 **{init_investment:,.2f}**이 주가 파동에 따라 30일 뒤 최종적으로 얼마까지 불어나거나 줄어들 수 있는지 가치 변화 경로를 100번 시뮬레이션한 결과입니다.
    """)
    
    daily_returns = df[target_ticker].pct_change().dropna()
    mu = daily_returns.mean()
    sigma = daily_returns.std()
    last_price = df[target_ticker].dropna().iloc[-1]
    
    days_to_simulate = 30
    num_simulations = 100
    
    price_sim_df = pd.DataFrame()     
    asset_sim_df = pd.DataFrame()      
    
    for x in range(num_simulations):
        price_series = [last_price]
        for y in range(days_to_simulate):
            next_price = price_series[-1] * (1 + np.random.normal(mu, sigma))
            price_series.append(next_price)
            
        price_sim_df[f"Sim_{x}"] = price_series
        asset_sim_df[f"Sim_{x}"] = (np.array(price_series) / last_price) * init_investment
        
    fig_mc = go.Figure()
    for col in price_sim_df.columns:
        fig_mc.add_trace(go.Scatter(x=np.arange(days_to_simulate+1), y=price_sim_df[col], 
                                    mode='lines', line=dict(color='gray', width=1), opacity=0.2))
        
    fig_mc.add_hline(y=last_price, line_dash="dash", line_color="red", annotation_text="현재가")
    fig_mc.update_layout(title=f"📈 {target_ticker} 미래 주가 시나리오 예측 (100회)", showlegend=False, xaxis_title="미래 경과 일수(Days)", yaxis_title="예측 주가", height=400)
    st.plotly_chart(fig_mc, use_container_width=True)
    
    st.markdown("---")
    
    fig_asset = go.Figure()
    for col in asset_sim_df.columns:
        fig_asset.add_trace(go.Scatter(x=np.arange(days_to_simulate+1), y=asset_sim_df[col], 
                                       mode='lines', line=dict(color='darkturquoise', width=1), opacity=0.15))
        
    fig_asset.add_hline(y=init_investment, line_dash="dash", line_color="red", annotation_text="초기 투자 원금")
    fig_asset.update_layout(title=f"💰 주가 변동에 따른 투자 자산 가치 추정 시나리오 (원금: {init_investment:,.2f})", showlegend=False, xaxis_title="미래 경과 일수(Days)", yaxis_title="예측 자산 가치", height=400)
    st.plotly_chart(fig_asset, use_container_width=True)

with tab4:
    st.subheader("📡 타겟 종목 실시간 글로벌 뉴스 & AI 요약")
    st.info("💡 **기능 가이드:** 아래 버튼을 누르면 AI 애널리스트가 영문 뉴스들을 읽고 시장 분위기를 한국어 3줄로 즉시 요약해 줍니다.")
    
    news_target_display = st.selectbox("뉴스 검색 종목 선택", display_tickers, key='news_selectbox')
    
    # 디스플레이용 한글 이름을 다시 야후 파이낸스용 영어 티커로 변환하여 뉴스 검색
    news_target_raw = [k for k, v in TICKER_MAP.items() if v == news_target_display][0]
    news_data = yf.Ticker(news_target_raw).news
    
    if news_data:
        if st.button(f"✨ '{news_target_display}' 최신 영문 뉴스 AI 3줄 요약하기"):
            with st.spinner("월스트리트 AI 애널리스트가 기사들을 분석 중입니다..."):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    news_titles = "\n".join([article.get('title') or article.get('content', {}).get('title') or "" for article in news_data[:5]])
                    prompt = f"너는 월스트리트의 전문 퀀트 애널리스트야. 다음은 오늘 '{news_target_display}' 종목에 대한 최신 영문 뉴스 헤드라인들이야.\n\n{news_titles}\n\n이 뉴스들의 전반적인 맥락을 분석해서, 현재 이 종목의 시장 분위기와 핵심 호재/악재를 일반 투자자가 이해하기 쉽게 한국어로 딱 3개 불릿 포인트(•)로 요약해줘."
                    
                    response = model.generate_content(prompt)
                    st.success("🤖 **AI 애널리스트 브리핑 완료**")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"⚠️ AI 연결에 실패했습니다. 에러: {e}")
                    
        st.markdown("---")
        
        for article in news_data[:5]: 
            title = article.get('title') or article.get('content', {}).get('title') or "제목 없음"
            publisher = article.get('publisher') or article.get('content', {}).get('provider', {}).get('displayName') or "출처 알 수 없음"
            link = article.get('link')
            if not link:
                url_dict = article.get('content', {}).get('clickThroughUrl', {})
                link = url_dict.get('url', '#') if isinstance(url_dict, dict) else '#'
                
            pub_time = article.get('providerPublishTime') or article.get('content', {}).get('pubDate')
            try:
                if isinstance(pub_time, (int, float)):
                    date_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(pub_time, str):
                    date_str = pd.to_datetime(pub_time).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_str = "시간 정보 없음"
            except Exception:
                date_str = "시간 변환 실패"
            
            st.markdown(f"#### 🔗 [{title}]({link})")
            st.caption(f"🏢 매체: **{publisher}** | 🕒 발행: {date_str}")
            st.markdown("---")
    else:
        st.info("현재 해당 종목에 대한 최신 뉴스 데이터가 수집되지 않았습니다. (※ 한국 주식은 야후 파이낸스 영문 뉴스 제공이 제한적일 수 있습니다.)")

with tab5:
    st.subheader("🎯 이동평균선 크로스오버 백테스트 엔진")
    st.info("""
    📚 **이동평균선(MA) 교차 매매를 왜 하고, 무엇을 얻을 수 있나요?**
    * **사용 이유 (노이즈 제거):** 주가 차트에는 매일 무작위적인 가격 '노이즈(소음)'가 낍니다. 이동평균선은 과거 가격을 평균 내어 이 소음을 걷어내고, 현재 자산이 상승 가도를 달리는지 하락 구렁텅이로 빠지는지 **'진짜 우상향 추세'**를 시각화해 줍니다.
    * **얻을 수 있는 이득 (자산 보호와 리스크 차단):** 주식 투자에서 가장 무서운 것은 인간의 욕심과 공포입니다. 이 전략은 감정을 배제하고 수학적 선 교차에만 맞춰 **'무릎에서 사고 어깨에서 파는 기계적 규칙'**을 제공합니다. 특히 대공황이나 코로나 폭락 같은 **'대형 하락장(MDD)'이 시작될 때 자산을 전량 현금화하여 내 원금을 안전하게 지켜내는 것**이 이 전략의 가장 압도적인 이득입니다.
    """)
    
    st.markdown("### ⚡ 월스트리트 검증 3대 황금 조합 프리셋")
    st.caption("버튼을 누르면 아래 전략 변수 슬라이더가 해당 조합의 숫자로 자동 세팅됩니다.")
    
    if 'short_ma' not in st.session_state: st.session_state['short_ma'] = 20
    if 'long_ma' not in st.session_state: st.session_state['long_ma'] = 50

    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("🚀 초단기 트레이딩 모드 (5일 / 20일)"):
            st.session_state['short_ma'] = 5
            st.session_state['long_ma'] = 20
            st.rerun()
    with btn_col2:
        if st.button("💼 중단기 밸런스 모드 (20일 / 60일)"):
            st.session_state['short_ma'] = 20
            st.session_state['long_ma'] = 60
            st.rerun()
    with btn_col3:
        if st.button("🐳 장기 거시경제 모드 (50일 / 200일)"):
            st.session_state['short_ma'] = 50
            st.session_state['long_ma'] = 200
            st.rerun()
            
    st.markdown("---")
    st.markdown("### ⚙️ 전략 변수 미세 조절 및 조합별 성격")
    
    param_col1, param_col2 = st.columns(2)
    with param_col1:
        short_ma = st.slider("단기 이동평균선 기준일 (일)", min_value=5, max_value=50, key='short_ma', step=1)
    with param_col2:
        long_ma = st.slider("장기 이동평균선 기준일 (일)", min_value=20, max_value=200, key='long_ma', step=1)
        
    st.info(f"""
    🧬 **현재 설정된 조합 ({short_ma}일 / {long_ma}일)의 통계적 성격:**
    * **짧은 조합 (예: 5/20):** 하락세에 엄청나게 빠르게 반응해 돈을 빼내지만, 주가가 횡보할 때 가짜 신호(휩쏘)에 속아 **사고팔기를 반복하며 수수료만 날리는 리스크**가 있습니다. (비트코인,성장주 등 고변동성 자산에 유리)
    * **긴 조합 (예: 50/200):** 자잘한 소음은 완벽히 무시하고 굵직한 메인 상승장만 가져갑니다. 다만 대응 속도가 한참 느려서 **폭락이 이미 시작되고 한참 뒤에나 매도 신호가 뜨는 뒷북 리스크**가 있습니다. (지수 ETF나 초장기 가치투자에 유리)
    """)
    
    st.markdown("---")
    
    bt_target = st.selectbox("백테스트 대상 종목 선택", display_tickers, key='bt_selectbox')
    bt_df = pd.DataFrame(df[bt_target]).dropna()
    bt_df.columns = ['Close']
    
    bt_df['SMA_Short'] = bt_df['Close'].rolling(window=short_ma).mean()
    bt_df['SMA_Long'] = bt_df['Close'].rolling(window=long_ma).mean()
    bt_df = bt_df.dropna()
    
    bt_df['Signal'] = np.where(bt_df['SMA_Short'] > bt_df['SMA_Long'], 1, 0)
    bt_df['Position'] = bt_df['Signal'].shift(1).fillna(0)
    
    bt_df['Asset_Return'] = bt_df['Close'].pct_change().fillna(0) 
    bt_df['Strategy_Return'] = bt_df['Asset_Return'] * bt_df['Position'] 
    
    bt_df['Cum_Asset_Return'] = (1 + bt_df['Asset_Return']).cumprod() - 1
    bt_df['Cum_Strategy_Return'] = (1 + bt_df['Strategy_Return']).cumprod() - 1
    
    fig_bt = go.Figure()
    fig_bt.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Cum_Asset_Return'] * 100, mode='lines', name='단순 보유 (Buy & Hold)', line=dict(color='gray', width=1.5)))
    fig_bt.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Cum_Strategy_Return'] * 100, mode='lines', name='이평선 교차 전략 (Strategy)', line=dict(color='green', width=2.5)))
    fig_bt.update_layout(title=f"📈 {bt_target} 누적 수익률 비교", xaxis_title="날짜", yaxis_title="누적 수익률 (%)", height=400)
    st.plotly_chart(fig_bt, use_container_width=True)
    
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(x=bt_df.index, y=bt_df['Close'], mode='lines', name='실제 주가', line=dict(color='lightgray', width=1)))
    fig_price.add_trace(go.Scatter(x=bt_df.index, y=bt_df['SMA_Short'], mode='lines', name=f'{short_ma}일 이동평균 (단기)', line=dict(color='blue', width=1.5)))
    fig_price.add_trace(go.Scatter(x=bt_df.index, y=bt_df['SMA_Long'], mode='lines', name=f'{long_ma}일 이동평균 (장기)', line=dict(color='orange', width=1.5)))
    fig_price.update_layout(title=f"🔍 {bt_target} 주가 및 이동평균선 흐름", xaxis_title="날짜", yaxis_title="가격", height=400)
    st.plotly_chart(fig_price, use_container_width=True)
    
    final_asset_ret = bt_df['Cum_Asset_Return'].iloc[-1] * 100
    final_strat_ret = bt_df['Cum_Strategy_Return'].iloc[-1] * 100
    alpha = final_strat_ret - final_asset_ret 
    
    st.markdown("### 🏆 백테스트 최종 성과 지표")
    score_col1, score_col2, score_col3 = st.columns(3)
    with score_col1:
        st.metric(label="💼 단순 보유 최종 수익률", value=f"{final_asset_ret:.1f}%")
    with score_col2:
        st.metric(label="🚀 전략 적용 최종 수익률", value=f"{final_strat_ret:.1f}%")
    with score_col3:
        st.metric(label="🔥 알파 (초과 수익률)", value=f"{alpha:.1f}%p", delta=f"{alpha:.1f}%p" if alpha >= 0 else f"{alpha:.1f}%p", delta_color="normal" if alpha >= 0 else "inverse")