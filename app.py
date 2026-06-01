import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
import google.generativeai as genai # 💡 구글 AI 라이브러리 추가

# 1. 페이지 기본 설정
st.set_page_config(page_title="Pro Quant Dashboard", layout="wide")

# 사이드바 설정
st.sidebar.header("⚙️ 포트폴리오 설정")
tickers = st.sidebar.multiselect("분석할 종목", ["QQQ", "SPY", "NVDA", "AAPL", "BTC-USD", "ETH-USD"], default=["QQQ", "BTC-USD"])
start_date = st.sidebar.date_input("시작일", date.today() - timedelta(days=365))
end_date = st.sidebar.date_input("종료일", date.today())

@st.cache_data
def get_data(tickers, start, end):
    return yf.download(tickers, start=start, end=end)['Close']

if not tickers:
    st.warning("종목을 선택해 주세요!")
    st.stop()

df = get_data(tickers, start_date, end_date)

# ---------------------------------------------------------
# 상단 KPI 요약 패널
# ---------------------------------------------------------
st.title("⚡ Pro 퀀트 통합 대시보드")
st.markdown("---")

cols = st.columns(len(tickers)) 
for i, ticker in enumerate(tickers):
    with cols[i]:
        valid_data = df[ticker].dropna()
        if len(valid_data) >= 2:
            latest_price = valid_data.iloc[-1]
            prev_price = valid_data.iloc[-2]
            change_pct = ((latest_price - prev_price) / prev_price) * 100
            st.metric(label=f"💰 {ticker} 현재가", value=f"${latest_price:,.2f}", delta=f"{change_pct:.2f}%")
        else:
            st.metric(label=f"💰 {ticker} 현재가", value="데이터 대기 중", delta="-")

st.markdown("---")

# ---------------------------------------------------------
# 5개의 분석 탭 구성
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 과거 가격 흐름", 
    "🔥 자산 상관관계", 
    "🎲 몬테카를로 시뮬레이션", 
    "📰 실시간 시장 뉴스",
    "🎯 백테스트 리포트"
])

with tab1:
    st.line_chart(df, height=400)

with tab2:
    if len(tickers) >= 2:
        corr_matrix = df.pct_change().dropna().corr()
        fig_corr = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='RdBu_r', zmin=-1, zmax=1)
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("상관관계를 보려면 종목을 2개 이상 선택하세요.")

with tab3:
    st.subheader("미래 30일 주가 경로 시뮬레이션 (Monte Carlo)")
    target_ticker = st.selectbox("시뮬레이션 타겟 종목", tickers)
    
    days_to_simulate = 30
    num_simulations = 100
    daily_returns = df[target_ticker].pct_change().dropna()
    mu = daily_returns.mean()
    sigma = daily_returns.std()
    last_price = df[target_ticker].iloc[-1]
    
    simulation_df = pd.DataFrame()
    for x in range(num_simulations):
        price_series = [last_price]
        for y in range(days_to_simulate):
            next_price = price_series[-1] * (1 + np.random.normal(mu, sigma))
            price_series.append(next_price)
        simulation_df[f"Sim_{x}"] = price_series
        
    fig_mc = go.Figure()
    for col in simulation_df.columns:
        fig_mc.add_trace(go.Scatter(x=np.arange(days_to_simulate+1), y=simulation_df[col], 
                                    mode='lines', line=dict(color='gray', width=1), opacity=0.2))
        
    fig_mc.add_hline(y=last_price, line_dash="dash", line_color="red", annotation_text="현재가")
    fig_mc.update_layout(showlegend=False, xaxis_title="미래 경과 일수(Days)", yaxis_title="예측 가격($)", height=500)
    st.plotly_chart(fig_mc, use_container_width=True)

# ---------------------------------------------------------
# 📰 [업그레이드된 탭 4] 실시간 시장 뉴스 + AI 요약 에이전트
# ---------------------------------------------------------
with tab4:
    st.subheader("📡 타겟 종목 실시간 글로벌 뉴스 & AI 요약")
    news_target = st.selectbox("뉴스 검색 종목 선택", tickers, key='news_selectbox')
    news_data = yf.Ticker(news_target).news
    
    if news_data:
        # 💡 [핵심] AI 요약 버튼 추가
        if st.button(f"✨ '{news_target}' 최신 영문 뉴스 AI 3줄 요약하기"):
            with st.spinner("월스트리트 AI 애널리스트가 기사들을 분석 중입니다..."):
                try:
                    # API 키 불러오기 (비밀 금고에서)
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # 뉴스 헤드라인들을 텍스트로 하나로 묶기
                    news_titles = "\n".join([article.get('title') or article.get('content', {}).get('title') or "" for article in news_data[:5]])
                    
                    # AI에게 내릴 프롬프트(명령어) 작성
                    prompt = f"""
                    너는 월스트리트의 전문 퀀트 애널리스트야. 다음은 오늘 '{news_target}' 종목에 대한 최신 영문 뉴스 헤드라인들이야.
                    
                    {news_titles}
                    
                    이 뉴스들의 전반적인 맥락을 분석해서, 현재 이 종목의 시장 분위기와 핵심 호재/악재를 일반 투자자가 이해하기 쉽게 한국어로 딱 3개 불릿 포인트(•)로 요약해줘.
                    """
                    
                    # AI에게 질문 던지고 답변 받기
                    response = model.generate_content(prompt)
                    
                    # 결과 예쁘게 출력
                    st.success("🤖 **AI 애널리스트 브리핑 완료**")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"⚠️ AI 연결에 실패했습니다. (API 키를 확인하세요!) 에러: {e}")
                    
        st.markdown("---")
        
        # 기존 뉴스 원문 리스트 출력
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
        st.info("현재 해당 종목에 대한 최신 뉴스 데이터가 수집되지 않았습니다.")

with tab5:
    st.subheader("📊 20일 / 50일 이동평균선 교차 전략 검증")
    bt_target = st.selectbox("백테스트 대상 종목 선택", tickers, key='bt_selectbox')
    bt_df = pd.DataFrame(df[bt_target]).dropna()
    bt_df.columns = ['Close']
    bt_df['SMA_20'] = bt_df['Close'].rolling(window=20).mean()
    bt_df['SMA_50'] = bt_df['Close'].rolling(window=50).mean()
    bt_df = bt_df.dropna()
    bt_df['Signal'] = np.where(bt_df['SMA_20'] > bt_df['SMA_50'], 1, 0)
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
    fig_price.add_trace(go.Scatter(x=bt_df.index, y=bt_df['SMA_20'], mode='lines', name='20일 이동평균 (단기)', line=dict(color='blue', width=1.5)))
    fig_price.add_trace(go.Scatter(x=bt_df.index, y=bt_df['SMA_50'], mode='lines', name='50일 이동평균 (장기)', line=dict(color='orange', width=1.5)))
    fig_price.update_layout(title=f"🔍 {bt_target} 주가 및 이동평균선 흐름", xaxis_title="날짜", yaxis_title="가격 ($)", height=400)
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