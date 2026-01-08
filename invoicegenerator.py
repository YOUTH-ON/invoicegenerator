import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import requests
import pandas as pd
from datetime import datetime

# --- 1. アプリ初期設定とセッション初期化 ---
st.set_page_config(page_title="請求書ジェネレーター", layout="wide")

def initialize_session():
    if 'items' not in st.session_state:
        st.session_state['items'] = []
    if 'i_addr' not in st.session_state:
        st.session_state['i_addr'] = ""
    if 'c_addr' not in st.session_state:
        st.session_state['c_addr'] = ""

initialize_session()

# --- 2. 各種ボタンの動作関数 (Callbacks) ---
def add_item_callback():
    name = st.session_state.get('input_item_n', '')
    qty = st.session_state.get('input_item_q', 1)
    price = st.session_state.get('input_item_p', 0)
    if name:
        new_item = {"品目": name, "数量": qty, "単価": price, "金額": int(qty * price)}
        st.session_state['items'].append(new_item)
    else:
        st.warning("品目名を入力してください")

def search_issuer_address():
    zip_code = st.session_state.get('iz', '').replace("-", "").strip()
    addr = get_address_from_zip(zip_code)
    if addr: st.session_state['i_addr'] = addr
    else: st.warning("住所が見つかりませんでした")

def search_client_address():
    zip_code = st.session_state.get('cz', '').replace("-", "").strip()
    addr = get_address_from_zip(zip_code)
    if addr: st.session_state['c_addr'] = addr
    else: st.warning("住所が見つかりませんでした")

# --- 3. ロジック関数 ---
def get_address_from_zip(zipcode):
    try:
        res = requests.get(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}")
        data = res.json()
        if data['results']:
            r = data['results'][0]
            return f"{r['address1']}{r['address2']}{r['address3']}"
    except: pass
    return ""

def create_invoice_pdf(data, items):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # フォント登録
    FONT_NAME = 'JapaneseFont'
    pdfmetrics.registerFont(TTFont(FONT_NAME, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ipaexg.ttf')))
    
    # 発行者情報
    c.setFont(FONT_NAME, 10)
    c.drawString(400, height - 50, f"〒{data['issuer_zip']}")
    c.drawString(400, height - 65, data['issuer_address'])
    
    # ① 登録番号の表示制御
    y_offset = 80
    if not data['is_non_taxable']:
        c.drawString(400, height - y_offset, f"登録番号: {data['issuer_reg_num']}")
        y_offset += 15
    
    c.drawString(400, height - y_offset, data['issuer_name'])
    c.drawString(400, height - (y_offset + 15), f"発行年月日 {data['date']}")

    # 宛先情報
    c.drawString(50, height - 130, f"〒{data['client_zip']}")
    c.drawString(50, height - 145, data['client_address'])
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 165, f"{data['client_name']} 御中")

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 210, "御 請 求 書")

    # ② 税率計算
    subtotal = sum(item['金額'] for item in items)
    tax_rate = data['tax_rate'] / 100
    tax = int(subtotal * tax_rate)
    total = subtotal + tax

    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 260, f"御請求金額 {total:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 275, f"(内消費税等({data['tax_rate']}%) {tax:,} 円)")

    # 明細テーブル
    y = height - 310
    c.line(50, y, 550, y)
    c.drawString(60, y - 15, "品目")
    c.drawString(300, y - 15, "数量")
    c.drawString(380, y - 15, "単価")
    c.drawString(480, y - 15, "金額")
    c.line(50, y - 20, 550, y - 20)

    curr_y = y - 35
    for item in items:
        c.drawString(60, curr_y, item['品目'])
        c.drawString(300, curr_y, str(item['数量']))
        c.drawString(380, curr_y, f"{item['単価']:,}")
        c.drawString(480, curr_y, f"{item['金額']:,}")
        curr_y -= 20
    
    c.line(50, curr_y + 5, 550, curr_y + 5)
    c.drawString(380, curr_y - 15, "小計")
    c.drawString(480, curr_y - 15, f"{subtotal:,}")
    c.drawString(380, curr_y - 30, f"消費税({data['tax_rate']}%)")
    c.drawString(480, curr_y - 30, f"{tax:,}")
    c.drawString(380, curr_y - 45, "合計金額")
    c.drawString(480, curr_y - 45, f"{total:,}")

    # ③ 振込先と手数料の表示
    c.drawString(50, curr_y - 80, f"支払期日 ：{data['due_date']}")
    c.drawString(50, curr_y - 95, f"振込先 ：{data['bank_info']}")
    if data['fee_burden'] == "取引先負担":
        c.drawString(50, curr_y - 110, "その他 ：振込手数料は貴社負担でお願いいたします。")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- 4. メイン UI ---
st.title("請求書作成システム")

# 基本情報
with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("発行者情報")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        i_zip = st.text_input("郵便番号", value="2040023", key="iz")
        st.button("発行者住所を検索", on_click=search_issuer_address)
        issuer_address = st.text_input("発行者住所", value=st.session_state['i_addr'] if st.session_state['i_addr'] else "東京都清瀬市竹丘2-33-23")
        
        # ① 登録番号とチェックボックスの配置
        reg_col1, reg_col2 = st.columns([2, 1])
        with reg_col1:
            issuer_reg_num = st.text_input("適格請求書発行事業者登録番号", value="T1234567890123")
        with reg_col2:
            st.write("") # 位置調整用
            is_non_taxable = st.checkbox("登録番号なし")

    with col2:
        st.subheader("取引先情報")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        c_zip = st.text_input("取引先郵便番号", value="1500043", key="cz")
        st.button("取引先住所を検索", on_click=search_client_address)
        client_address = st.text_input("取引先住所", value=st.session_state['c_addr'] if st.session_state['c_addr'] else "東京都渋谷区道玄坂1-21-1 SHIBUYA SOLASTA 3F")

# 明細入力
st.subheader("明細の追加")
with st.container(border=True):
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: st.text_input("品目名", key="input_item_n")
    with c2: st.number_input("数量", min_value=1, value=1, key="input_item_q")
    with c3: st.number_input("単価", min_value=0, value=0, step=1000, key="input_item_p")
    st.button("明細をリストに追加", on_click=add_item_callback)

# 明細表示
current_items = st.session_state.get('items', [])
if len(current_items) > 0:
    st.subheader("現在の請求明細")
    df = pd.DataFrame(current_items)
    df.index = df.index + 1
    st.table(df)
    if st.button("明細をすべてリセット"):
        st.session_state['items'] = []
        st.rerun()

# ② & ③ 発行設定
st.subheader("発行設定")
with st.container(border=True):
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        date_val = st.date_input("発行年月日", datetime.now())
        due_val = st.date_input("お支払期限", datetime(2026, 1, 31))
    with col_s2:
        tax_rate = st.number_input("消費税率 (%)", min_value=0, max_value=100, value=10) # ② 税率
        fee_burden = st.radio("振込手数料の負担", ["発行者負担", "取引先負担"], index=1) # ③ 手数料
    with col_s3:
        bank_val = st.text_area("お振込先口座情報", value="みずほ銀行清瀬支店\n普通 1228611", height=100)

# PDF生成
if st.button("請求書PDFを作成する", type="primary"):
    if not st.session_state['items']:
        st.warning("明細を追加してから作成してください。")
    else:
        data = {
            'issuer_name': issuer_name, 'issuer_zip': i_zip, 'issuer_address': issuer_address,
            'issuer_reg_num': issuer_reg_num, 'is_non_taxable': is_non_taxable,
            'client_name': client_name, 'client_zip': c_zip, 'client_address': client_address,
            'date': date_val.strftime('%Y年%m月%d日'), 'due_date': due_val.strftime('%Y年%m月%d日'),
            'bank_info': bank_val.replace('\n', ' / '), 
            'tax_rate': tax_rate, 'fee_burden': fee_burden
        }
        pdf = create_invoice_pdf(data, st.session_state['items'])
        st.success("PDFの生成に成功しました。")
        st.download_button("PDFをダウンロード", data=pdf, file_name=f"請求書_{client_name}.pdf", mime="application/pdf")
