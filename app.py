import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os

# --- 1. 데이터베이스 설정 ---
DB_FILE = "delivery.db"

def get_db_connection():
    # 데이터베이스 파일 연결 (없으면 자동 생성)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    """앱 실행 시 테이블이 없으면 생성"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_date TEXT,
            department TEXT,
            user_name TEXT,
            restaurant TEXT,
            items TEXT,
            total_price INTEGER,
            delivery_fee INTEGER DEFAULT 0,
            over_price INTEGER DEFAULT 0,
            status TEXT DEFAULT '주문대기',
            batch_id TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

# 앱 시작 시 DB 초기화
init_db()

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
today_str = datetime.date.today().strftime('%Y-%m-%d')

st.title('🍱 인천생활과학고 "밥먹고 초근하자"')
st.markdown(f"### 📅 오늘은 **{today_str}** 입니다.")

tab1, tab2, tab3 = st.tabs(["🍴 맛있는 주문", "📋 관리자 데스크", "📜 지난 기록"])

# --- [Tab 1: 주문하기] ---
# --- [Tab 1: 주문하기] ---
with tab1:
    if staff_df.empty or menu_df.empty:
        st.error("🚨 staff.csv 또는 menu.csv 파일을 찾을 수 없습니다. GitHub에 파일이 업로드되었는지 확인해주세요.")
    else:
        st.info("💡 부서 → 이름 → 식당 순으로 선택 후 주문하세요.\n\n 💡 매일 16:00시에 일괄주문합니다. 그외는 개별 주문\n\n 💡 초근신청 확인(1시간 이상 근무 하실분), 배송료 고려 1인 9,000원이내\n\n 💡배송료는 업체마다 다름. 오르드브와 아말피 단체 4,000원, 장강 무료, 1인 주문시 2,000~3,000원 배달비 필요 단체주문 이득 ")
        
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

        # 여기서부터 들여쓰기가 매우 중요합니다! (모두 한 칸씩 안으로)
        if selected_res not in ["--- 식당 선택 ---", "이름 먼저 선택"]:
            res_menu = menu_df[menu_df['restaurant'] == selected_res]
            menu_options = [f"{row['item_name']} ({row['price']:,}원)" for _, row in res_menu.iterrows()]
            selected_display = st.multiselect("📝 메뉴 선택", menu_options)
            
            # 이 아래 if문은 위 selected_display와 왼쪽 끝 세로줄이 똑같아야 합니다.
            if selected_display and st.button("🚀 주문 확정하기", type="primary", use_container_width=True):
                try:
                    import time
                    conn = get_db_connection()
                    
                    # 중복 체크
                    existing = pd.read_sql("SELECT * FROM orders WHERE order_date=? AND user_name=?", conn, params=(today_str, user_name))
                    
                    if not existing.empty:
                        st.error("❌ 이미 오늘 주문하셨습니다!")
                    else:
                        # 데이터 계산 및 저장
                        total_food = sum([int(s.split('(')[1].replace('원)', '').replace(',', '')) for s in selected_display])
                        items_str = ", ".join([s.split(' (')[0] for s in selected_display])
                        order_id = str(datetime.datetime.now().timestamp())
                        
                        cur = conn.cursor()
                        cur.execute("INSERT INTO orders (id, order_date, department, user_name, restaurant, items, total_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (order_id, today_str, dept, user_name, selected_res, items_str, total_food))
                        conn.commit()
                        
                        # 🎉 풍선 효과와 성공 메시지
                        st.balloons()
                        st.success(f"✅ {user_name}님, 주문 완료!")
                        
                        # 잠시 대기 후 초기화 (rerun)
                        time.sleep(1.5)
                        st.rerun()
                    
                    conn.close()

                except Exception as e:
                    st.error(f"🚨 오류 발생: {e}")

# --- [Tab 2: 관리자 데스크] ---
with tab2:
    conn = get_db_connection()
    # 1. 오늘 날짜의 전체 데이터 읽기
    today_data = pd.read_sql("SELECT * FROM orders WHERE order_date=?", conn, params=(today_str,))
    
    if today_data.empty:
        st.info("오늘 접수된 주문이 없습니다.")
    else:
        # 2. 확정 대기 중인 주문 처리
        pending = today_data[today_data['status'] == '주문대기']
        if not pending.empty:
            st.markdown("#### ⏳ 확정 대기 목록")
            for res in pending['restaurant'].unique():
                res_orders = pending[pending['restaurant'] == res]
                with st.expander(f"📍 {res} (대기 {len(res_orders)}건)", expanded=True):
                    order_count = len(res_orders)
                    food_sum = res_orders['total_price'].sum()
                    
                    # 배달비 로직 (아말피, 오르드브 등 식당별 조건)
                    if res == '아말피': d_fee = 3000 if order_count == 1 else 4000
                    elif res == '오르드브': d_fee = 2000 if order_count == 1 else 4000
                    elif res == '장강': d_fee = 0
                    else: d_fee = 4000
                    if res == '오르드브' and food_sum >= 50000: d_fee = 0
                    
                    per_fee = d_fee // order_count
                    st.write(f"💰 예상 배달비: 총 {d_fee:,}원 (1인당 {per_fee:,}원)")
                    
                    # 선택된 주문 ID를 담을 리스트
                    to_action = []
                    for _, row in res_orders.iterrows():
                        if st.checkbox(f"{row['user_name']} | {row['items']} ({row['total_price']:,}원)", key=f"chk_{row['id']}"):
                            to_action.append(row['id'])
                    
                    # 확정 및 삭제 버튼
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button(f"✅ {res} 선택 확정", key=f"conf_{res}"):
                            if to_action:
                                cur = conn.cursor()
                                # 현재 완료된 차수 계산해서 다음 차수 이름 생성
                                done_batches = today_data[today_data['status']=='주문완료']['batch_id'].unique()
                                b_id = f"{len(done_batches)+1}차({res})"
                                
                                for tid in to_action:
                                    # 단일 값 추출을 위해 .item() 사용
                                    selected_row = res_orders[res_orders['id'] == tid]
                                    food_price = int(selected_row['total_price'].item())
                                    # 개인부담금 계산 (지원금 9,000원 기준)
                                    over = max(0, (food_price + per_fee) - 9000)
                                    cur.execute("UPDATE orders SET status='주문완료', batch_id=?, delivery_fee=?, over_price=? WHERE id=?", 
                                                (b_id, per_fee, int(over), tid))
                                conn.commit()
                                st.rerun()
                    with col_b2:
                        if st.button(f"🗑️ {res} 선택 삭제", key=f"del_{res}"):
                            if to_action:
                                cur = conn.cursor()
                                for tid in to_action:
                                    cur.execute("DELETE FROM orders WHERE id=?", (tid,))
                                conn.commit()
                                st.rerun()

        # 3. 이미 확정된 내역 출력 (차수별로 분리)
        done = today_data[today_data['status'] == '주문완료']
        if not done.empty:
            st.divider()
            st.subheader("✅ 오늘 주문 확정 내역")
            for batch in sorted(done['batch_id'].unique()):
                st.markdown(f"#### 🏷️ {batch}")
                batch_df = done[done['batch_id'] == batch].copy()
                display_df = batch_df[['department', 'user_name', 'items', 'total_price', 'delivery_fee', 'over_price']]
                display_df.columns = ['부서', '성함', '메뉴', '음식값', '배달비', '개인부담금']
                st.table(display_df)
                
                total_sum = batch_df['total_price'].sum() + batch_df['delivery_fee'].sum()
                st.caption(f"💰 {batch} 총결제액: {total_sum:,}원")

    # 4. [추가] 데이터 백업 (CSV 다운로드) - Reboot 대비용
    st.divider()
    st.subheader("📥 데이터 백업")
    full_data = pd.read_sql("SELECT * FROM orders ORDER BY order_date DESC", conn)
    
    if not full_data.empty:
        csv_data = full_data.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 전체 주문 내역 CSV 다운로드 (백업용)",
            data=csv_data,
            file_name=f"orders_backup_{today_str}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    conn.close()
    
# --- [Tab 3: 지난 기록] ---
with tab3:
    search_date = st.date_input("날짜 선택", datetime.date.today())
    conn = get_db_connection()
    history = pd.read_sql("SELECT * FROM orders WHERE order_date=? AND status='주문완료'", conn, params=(search_date.strftime('%Y-%m-%d'),))
    if not history.empty:
        st.table(history)
    else:
        st.write("해당 날짜의 기록이 없습니다.")
    conn.close()





