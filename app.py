import streamlit as st
import pandas as pd
import datetime
import uuid
import time
from supabase import create_client, Client

# --- 1. 데이터베이스 설정 (Supabase 연동) ---
# Streamlit Cloud의 Settings -> Secrets에 설정된 정보를 가져옵니다.
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"🚨 Supabase 연결 설정(Secrets)을 확인해주세요: {e}")
    st.stop()

# --- 2. 외부 데이터 로드 (교직원 및 메뉴) ---
@st.cache_data
def load_external_data():
    try:
        staff = pd.read_csv('staff.csv')
        menu = pd.read_csv('menu.csv')
        return staff, menu
    except FileNotFoundError:
        # 파일이 없을 경우를 대비한 샘플 데이터 (실제 운영시 csv 파일 업로드 필수)
        st.warning("⚠️ staff.csv 또는 menu.csv 파일을 찾을 수 없어 샘플 데이터를 로드합니다.")
        s_sample = pd.DataFrame({'name': ['홍길동'], 'department': ['교무부']})
        m_sample = pd.DataFrame({'restaurant': ['장강'], 'item_name': ['짜장면'], 'price': [7000]})
        return s_sample, m_sample

staff_df, menu_df = load_external_data()

# --- 3. 앱 기본 설정 ---
st.set_page_config(page_title='인천생활과학고 "밥먹고 초근하자"', page_icon="🍱", layout="wide")
today = datetime.date.today()
today_str = today.strftime('%Y-%m-%d')

# 실시간 데이터 불러오기 함수 (DB와 화면 동기화 핵심)
def fetch_today_data():
    try:
        res = supabase.table("orders").select("*").eq("order_date", today_str).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"데이터 불러오기 실패: {e}")
        return pd.DataFrame()

st.title('🍱 인천생활과학고 "밥먹고 초근하자"')
st.markdown(f"### 📅 오늘은 **{today_str}** 입니다.")

tab1, tab2, tab3 = st.tabs(["🍴 맛있는 주문", "📋 관리자 데스크", "📜 지난 기록"])

# --- [Tab 1: 주문하기] ---
with tab1:
    st.info("💡 부서 → 이름 → 식당 순으로 선택 후 주문하세요. (마감 16:30)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        dept_options = sorted(staff_df['department'].unique().tolist())
        dept = st.selectbox("🏢 부서 선택", ["--- 부서 선택 ---"] + dept_options)
    
    with col2:
        if dept != "--- 부서 선택 ---":
            names = sorted(staff_df[staff_df['department']==dept]['name'].tolist())
            user_name = st.selectbox("👤 이름 선택", ["--- 이름 선택 ---"] + names)
        else:
            user_name = st.selectbox("👤 이름 선택", ["부서 먼저 선택"])
    
    with col3:
        if user_name not in ["--- 이름 선택 ---", "부서 먼저 선택"]:
            res_options = sorted(menu_df['restaurant'].unique().tolist())
            selected_res = st.selectbox("🏪 식당 선택", ["--- 식당 선택 ---"] + res_options)
        else:
            selected_res = st.selectbox("🏪 식당 선택", ["이름 먼저 선택"])

    if selected_res not in ["--- 식당 선택 ---", "이름 먼저 선택"]:
        res_menu = menu_df[menu_df['restaurant'] == selected_res]
        menu_options = [f"{row['item_name']} ({row['price']:,}원)" for _, row in res_menu.iterrows()]
        selected_items = st.multiselect("📝 메뉴 선택", menu_options)
        
        if selected_items and st.button("🚀 주문 확정하기", type="primary", use_container_width=True):
            now = datetime.datetime.now()
            if now.hour >= 16 and now.minute > 30:
                st.error("🚫 16:30 이후에는 시스템 주문이 불가합니다.")
            else:
                # 1. 중복 주문 확인
                existing = supabase.table("orders").select("*").eq("order_date", today_str).eq("user_name", user_name).execute()
                if len(existing.data) > 0:
                    st.error(f"❌ {user_name}님은 이미 오늘 주문 내역이 있습니다.")
                else:
                    # 2. 데이터 계산 및 전송
                    total_price = sum([int(s.split('(')[1].replace('원)', '').replace(',', '')) for s in selected_items])
                    items_only = ", ".join([s.split(' (')[0] for s in selected_items])
                    
                    order_data = {
                        "id": str(uuid.uuid4()),
                        "order_date": today_str,
                        "department": dept,
                        "user_name": user_name,
                        "restaurant": selected_res,
                        "items": items_only,
                        "total_price": int(total_price),
                        "status": "주문대기",
                        "delivery_fee": 0,
                        "over_price": 0,
                        "batch_id": ""
                    }
                    
                    try:
                        save_res = supabase.table("orders").insert(order_data).execute()
                        if save_res.data:
                            st.balloons()
                            st.success(f"✅ {user_name}님, 주문이 안전하게 저장되었습니다!")
                            time.sleep(1.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"🚨 DB 저장 실패: {e}\n(Supabase의 RLS 설정을 확인해주세요!)")

# --- [Tab 2: 관리자 데스크] ---
with tab2:
    today_df = fetch_today_data()
    
    if today_df.empty:
        st.info("오늘 접수된 주문이 없습니다.")
    else:
        pending = today_df[today_df['status'] == '주문대기']
        if not pending.empty:
            st.subheader("⏳ 확정 대기 목록")
            for res_name in pending['restaurant'].unique():
                res_orders = pending[pending['restaurant'] == res_name]
                order_count = len(res_orders)
                food_sum = pd.to_numeric(res_orders['total_price']).sum()
                
                with st.expander(f"📍 {res_name} (대기 {order_count}건)", expanded=True):
                    # 식당별 배달비 로직
                    if res_name == '아말피': d_fee = 3000 if order_count == 1 else 4000
                    elif res_name == '오르드브': d_fee = 2000 if order_count == 1 else 4000
                    elif res_name == '장강': d_fee = 0
                    else: d_fee = 4000
                    if res_name == '오르드브' and food_sum >= 50000: d_fee = 0
                    
                    per_fee = d_fee // order_count
                    st.write(f"💰 배달비: 총 {d_fee:,}원 (1인당 {per_fee:,}원)")
                    
                    to_confirm = []
                    for _, row in res_orders.iterrows():
                        if st.checkbox(f"{row['user_name']} | {row['items']} ({row['total_price']:,}원)", key=row['id']):
                            to_confirm.append(row['id'])
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(f"✅ {res_name} 선택 확정", key=f"btn_c_{res_name}"):
                            if to_confirm:
                                # 차수 계산
                                confirmed_count = len(today_df[today_df['status'] == '주문완료']['batch_id'].unique())
                                b_id = f"{confirmed_count + 1}차({res_name})"
                                for tid in to_confirm:
                                    row_info = res_orders[res_orders['id'] == tid].iloc[0]
                                    over = max(0, (int(row_info['total_price']) + per_fee) - 9000)
                                    supabase.table("orders").update({
                                        "status": "주문완료", "batch_id": b_id,
                                        "delivery_fee": int(per_fee), "over_price": int(over)
                                    }).eq("id", tid).execute()
                                st.rerun()
                    with c2:
                        if st.button(f"🗑️ {res_name} 선택 삭제", key=f"btn_d_{res_name}"):
                            for tid in to_confirm:
                                supabase.table("orders").delete().eq("id", tid).execute()
                            st.rerun()

        # 오늘 확정된 내역
        done = today_df[today_df['status'] == '주문완료']
        if not done.empty:
            st.divider()
            st.subheader("✅ 오늘 주문 확정 내역")
            for batch in sorted(done['batch_id'].unique()):
                st.markdown(f"#### 🏷️ {batch}")
                batch_df = done[done['batch_id'] == batch].copy()
                st.table(batch_df[['department', 'user_name', 'items', 'total_price', 'delivery_fee', 'over_price']])

# --- [Tab 3: 지난 기록] ---
with tab3:
    search_date = st.date_input("날짜 선택", today)
    try:
        hist_res = supabase.table("orders").select("*").eq("order_date", str(search_date)).execute()
        if hist_res.data:
            st.write(f"### 📅 {search_date} 전체 내역")
            st.dataframe(pd.DataFrame(hist_res.data))
        else:
            st.info("해당 날짜의 기록이 없습니다.")
    except Exception as e:
        st.error(f"기록 조회 오류: {e}")

# 하단 새로고침 버튼
st.sidebar.divider()
if st.sidebar.button("🔄 데이터 강제 새로고침"):
    st.rerun()
