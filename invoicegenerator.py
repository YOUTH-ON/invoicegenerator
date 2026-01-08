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

# --- フォント設定 ---
FONT_NAME = 'JapaneseFont'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(CURRENT_DIR, 'ipaexg.ttf')

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except:
    st.error("ipaexg.ttf が見つかりません。リポジトリに配置してください。")

# --- 住所検索関数 ---
def get_address_from_zip(zipcode):
    zipcode = zipcode.replace("-", "")
    try:
        res = requests.get(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}")
        data = res.json()
        if data['results']:
            r = data['results'][0]
            return f"{r['address1']}{r['address2']}{r['address3']}"
    except: pass
    return ""

# --- PDF作成ロジック ---
def create_invoice_pdf(data, items):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    c.setFont(FONT_NAME, 10)
    c.drawString(400, height - 50, f"〒{data['issuer_zip']}")
    c.drawString(400, height - 65, data['issuer_address'])
    c.drawString(400, height - 80, f"登録番号: {data['issuer_reg_num']}")
    c.drawString(400, height - 95, data['issuer_name'])
    c.drawString(400, height - 110, f"発行年月日 {data['date']}")

    c.drawString(50, height - 130, f"〒{data['client_zip']}")
    c.drawString(50, height - 145, data['client_address'])
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 165, f"{data['client_name']} 御中")

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 210, "御 請 求 書")

    subtotal = sum(item['金額'] for item in items)
    tax = int(subtotal * 0.1)
    total = subtotal + tax

    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 260, f"御請求金額 {total:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 275, f"(内消費税等 {tax:,} 円)")

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
    c.drawString(380, curr_y - 30, "消費税(10%)")
    c.drawString(480, curr_y - 30, f"{tax:,}")
    c.drawString(380, curr_y - 45, "合計金額")
    c.drawString(480, curr_y - 45, f"{total:,}")

    c.drawString(50, curr_y - 80, f"支払期日 ：{data['due_date']}")
    c.drawString(50, curr_y - 95, f"振込先 ：{data['bank_info']}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- アプリ管理 ---
st.set_page_config(page_title="請求書ジェネレーター", layout="wide")

if 'items' not in st.session_state:
    st.session_state.items = []

st.title("請求書作成システム")

# 1. 基本情報
with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("発行者情報")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        i_zip = st.text_input("郵便番号", value="2040023", key="iz")
        if st.button("発行者住所を検索"):
            st.session_state.i_addr = get_address_from_zip(i_zip)
        issuer_address = st.text_input("発行者住所", value=st.session_state.get('i_addr', "東京都清瀬市竹丘2-33-23"))
        issuer_reg_num = st.text_input("適格請求書発行事業者登録番号", value="T1234567890123")
    with col2:
        st.subheader("取引先情報")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        c_zip = st.text_input("取引先郵便番号", value="1500043", key="cz")
        if st.button("取引先住所を検索"):
            st.session_state.c_addr = get_address_from_zip(c_zip)
        client_address = st.text_input("取引先住所", value=st.session_state.get('c_addr', "東京都渋谷区道玄坂1-21-1 SHIBUYA SOLASTA 3F"))

# 2. 明細入力
st.subheader("明細の追加")
with st.container(border=True):
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1: item_n = st.text_input("品目名", key="input_item_name")
    with c2: item_q = st.number_input("数量", min_value=1, value=1, key="input_item_qty")
    with c3: item_p = st.number_input("単価", min_value=0, value=0, step=1000, key="input_item_price")
    
    if st.button("明細をリストに追加"):
        if item_n:
            # 辞書形式で追加
            new_item = {"品目": item_n, "数量": item_q, "単価": item_p, "金額": int(item_q * item_p)}
            st.session_state.items.append(new_item)
            st.rerun()
        else:
            st.error("品目名を入力してください")

# 3. 明細一覧の表示 (ここが修正ポイント)
if len(st.session_state.items) > 0:
    st.subheader("現在の請求明細")
    df = pd.DataFrame(st.session_state.items)
    # インデックスを1から始める
    df.index = df.index + 1
    st.table(df)
    
    if st.button("明細をすべてリセット"):
        st.session_state.items = []
        st.rerun()
else:
    st.info("明細が追加されていません。上のフォームから追加してください。")

# 4. 発行設定とPDF出力
st.subheader("発行設定")
with st.container(border=True):
    col_d1, col_d2 = st.columns(2)
    with col_d1: date_val = st.date_input("発行年月日", datetime.now())
    with col_d2: due_val = st.date_input("お支払期限", datetime(2026, 1, 31))
    bank_val = st.text_input("お振込先口座情報", value="みずほ銀行清瀬支店 普通 1228611")

if st.button("請求書PDFを作成する", type="primary"):
    if not st.session_state.items:
        st.warning("明細を追加してから作成してください。")
    else:
        data = {
            'issuer_name': issuer_name, 'issuer_zip': i_zip, 'issuer_address': issuer_address,
            'issuer_reg_num': issuer_reg_num, 'client_name': client_name, 'client_zip': c_zip, 
            'client_address': client_address, 'date': date_val.strftime('%Y年%m月%d日'),
            'due_date': due_val.strftime('%Y年%m月%d日'), 'bank_info': bank_val
        }
        pdf = create_invoice_pdf(data, st.session_state.items)
        st.success("PDFの生成に成功しました。")
        st.download_button("PDFをダウンロード", data=pdf, file_name=f"請求書_{client_name}.pdf", mime="application/pdf")
