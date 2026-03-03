import streamlit as st
import pandas as pd
import datetime
import uuid
import time
from supabase import create_client, Client

# --- 1. 데이터베이스 설정 (Supabase) ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("🚨 Streamlit Secrets 설정을 확인해주세요! (SUPABASE_URL, SUPABASE_KEY)")
    st.stop()

# --- 2. 외부 CSV 파일 로드 ---
@st.cache_data
def load_external_data():
    try:
        staff = pd.read_csv('staff.csv')
        menu = pd.read_csv('menu.csv')
        return staff, menu
    except FileNotFoundError:
        st.error("🚨 staff.csv 또는 menu.csv 파일이 없습니다. 파일을 업로드해 주세요.")
        return pd.DataFrame(columns=['name', 'department']), pd.DataFrame(columns=['restaurant', 'item_name', 'price'])

staff_df, menu_df = load_external_data()

# --- 3. 앱 설정 및 스타일 ---
st.set_page_config(page_title='인천생활과학고 "밥먹고 초근하자"', page_icon="🍱", layout="wide")
today = datetime.date.today()
today_str = today.strftime('%Y-%m-%d')

st.title('🍱 인천생활과학고 "밥먹고 초근하자"')
st.markdown(f"### 📅 오늘은 **{today_str}** 입니다.")

# --- 중요: 앱이 실행될 때마다 최신 데이터를 DB에서 가져오기 ---
def get_today_data():
    res = supabase.table("orders").select("*").eq("order_date", today_str).execute()
    return pd.DataFrame(res.data)

today_data = get_today_data()

tab1, tab2, tab3 = st.tabs(["🍴 맛있는 주문", "📋 관리자 데스크", "📜 지난 기록"])

# --- [Tab 1: 주문하기] ---
with tab1:
    if staff_df.empty or menu_df.empty:
        st.error("🚨 staff.csv 또는 menu.csv 파일을 찾을 수 없습니다.")
    else:
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
            selected_display = st.multiselect("📝 메뉴 선택", menu_options)
            
            if selected_display and st.button("🚀 주문 확정하기", type="primary", use_container_width=True):
                now = datetime.datetime.now()
                limit_time = now.replace(hour=16, minute=30, second=0)
                
                if now > limit_time:
                    st.error("🚫 16:30 이후에는 시스템 주문이 불가합니다.")
                else:
                    # 중복 체크
                    existing = supabase.table("orders").select("*")\
                        .eq("order_date", today_str).eq("user_name", user_name).execute()
                    
                    if len(existing.data) > 0:
                        st.error("❌ 이미 오늘 주문하셨습니다!")
                    else:
                        total_food = sum([int(s.split('(')[1].replace('원)', '').replace(',', '')) for s in selected_display])
                        items_str = ", ".join([s.split(' (')[0] for s in selected_display])
                        
                        order_data = {
                            "id": str(uuid.uuid4()),
                            "order_date": today_str,
                            "department": dept,
                            "user_name": user_name,
                            "restaurant": selected_res,
                            "items": items_str,
                            "total_price": int(total_food),
                            "status": "주문대기"
                        }
                        supabase.table("orders").insert(order_data).execute()
                        st.balloons()
                        st.success(f"✅ {user_name}님, 주문 완료!")
                        time.sleep(1)
                        st.rerun()

# --- [Tab 2: 관리자 데스크] ---
with tab2:
    # 탭을 누를 때마다 최신 데이터 다시 로드
    today_data = get_today_data()
    
    if today_data.empty:
        st.info("오늘 접수된 주문이 없습니다.")
    else:
        pending = today_data[today_data['status'] == '주문대기']
        if not pending.empty:
            st.markdown("#### ⏳ 확정 대기 목록")
            for res_name in pending['restaurant'].unique():
                res_orders = pending[pending['restaurant'] == res_name]
                order_count = len(res_orders)
                food_sum = pd.to_numeric(res_orders['total_price']).sum()
                
                with st.expander(f"📍 {res_name} (대기 {order_count}건)", expanded=True):
                    if res_name == '아말피': d_fee = 3000 if order_count == 1 else 4000
                    elif res_name == '오르드브': d_fee = 2000 if order_count == 1 else 4000
                    elif res_name == '장강': d_fee = 0
                    else: d_fee = 4000
                    if res_name == '오르드브' and int(food_sum) >= 50000: d_fee = 0
                    
                    per_fee = d_fee // order_count
                    st.write(f"💰 예상 배달비: 총 {d_fee:,}원 (1인당 {per_fee:,}원)")
                    
                    to_action = []
                    for _, row in res_orders.iterrows():
                        if st.checkbox(f"{row['user_name']} | {row['items']} ({row['total_price']:,}원)", key=f"chk_{row['id']}"):
                            to_action.append(row['id'])
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(f"✅ {res_name} 확정", key=f"conf_{res_name}"):
                            if to_action:
                                done_batches = today_data[today_data['status']=='주문완료']['batch_id'].unique()
                                b_id = f"{len(done_batches)+1}차({res_name})"
                                for tid in to_action:
                                    row_data = res_orders[res_orders['id'] == tid].iloc[0]
                                    over = max(0, (int(row_data['total_price']) + per_fee) - 9000)
                                    supabase.table("orders").update({
                                        "status": "주문완료", "batch_id": b_id,
                                        "delivery_fee": int(per_fee), "over_price": int(over)
                                    }).eq("id", tid).execute()
                                st.rerun()
                    with c2:
                        if st.button(f"🗑️ {res_name} 삭제", key=f"del_{res_name}"):
                            for tid in to_action:
                                supabase.table("orders").delete().eq("id", tid).execute()
                            st.rerun()

        done = today_data[today_data['status'] == '주문완료']
        if not done.empty:
            st.divider()
            st.subheader("✅ 오늘 주문 확정 내역")
            for batch in sorted(done['batch_id'].unique()):
                st.markdown(f"#### 🏷️ {batch}")
                batch_df = done[done['batch_id'] == batch].copy()
                st.table(batch_df[['department', 'user_name', 'items', 'total_price', 'delivery_fee', 'over_price']])

    st.divider()
    if st.button("🔄 데이터 강제 새로고침"):
        st.rerun()

# --- [Tab 3: 지난 기록] ---
with tab3:
    search_date = st.date_input("날짜 선택", today)
    hist_res = supabase.table("orders").select("*").eq("order_date", str(search_date)).execute()
    if hist_res.data:
        st.write(f"### 📅 {search_date} 전체 내역")
        st.dataframe(pd.DataFrame(hist_res.data))
    else:
        st.write("해당 날짜의 기록이 없습니다.")
