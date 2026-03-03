import sqlite3
import pandas as pd

def init_db():
    conn = sqlite3.connect('meal_data.db')
    cursor = conn.cursor()

    # 기존 테이블 삭제
    cursor.execute('DROP TABLE IF EXISTS staff')
    cursor.execute('DROP TABLE IF EXISTS menu')
    cursor.execute('DROP TABLE IF EXISTS orders')

    # 1. 직원 정보 로드 (UTF-8 인코딩)
    try:
        staff_df = pd.read_csv('staff.csv', encoding='utf-8')
        staff_df.to_sql('staff', conn, index=False, if_exists='append')
    except Exception as e:
        print(f"staff.csv 로드 에러: {e}")

    # 2. 메뉴 정보 로드
    try:
        menu_df = pd.read_csv('menu.csv', encoding='utf-8')
        menu_df.to_sql('menu', conn, index=False, if_exists='append')
    except Exception as e:
        print(f"menu.csv 로드 에러: {e}")

    # 3. 주문 테이블 생성
    cursor.execute('''
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_date TEXT,
        department TEXT,
        user_name TEXT,
        restaurant TEXT,
        items TEXT,
        total_price INTEGER DEFAULT 0,
        delivery_fee INTEGER DEFAULT 0,
        over_price INTEGER DEFAULT 0,
        status TEXT DEFAULT '주문대기',
        batch_id TEXT DEFAULT ''
    )
    ''')

    conn.commit()
    conn.close()
    print("✅ staff.csv와 menu.csv를 읽어 DB 구축을 완료했습니다!")

if __name__ == "__main__":
    init_db()