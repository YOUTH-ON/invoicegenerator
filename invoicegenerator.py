import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
from datetime import datetime

# --- 日本語フォントの設定 ---
# GitHubリポジトリのルートに 'ipaexg.ttf' を置いている想定です
FONT_NAME = 'JapaneseFont'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(CURRENT_DIR, 'ipaexg.ttf')

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except Exception as e:
    st.error(f"フォントファイル(ipaexg.ttf)が見つかりません。リポジトリに配置してください。エラー内容: {e}")

def create_invoice_pdf(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- ヘッダー・発行者情報 ---
    c.setFont(FONT_NAME, 10)
    c.drawString(400, height - 50, f"〒{data['issuer_zip']}")
    c.drawString(400, height - 65, data['issuer_address'])
    c.drawString(400, height - 80, data['issuer_name'])
    c.drawString(400, height - 100, f"発行年月日 {data['date']}")

    # --- 宛先情報 ---
    c.drawString(50, height - 130, f"〒{data['client_zip']}")
    c.drawString(50, height - 145, data['client_address1'])
    c.drawString(50, height - 160, data['client_address2'])
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 180, f"{data['client_name']} 御中")

    # --- タイトル ---
    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 220, "御 請 求 書")

    # --- 請求金額 ---
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 260, "下記の通り御請求申し上げます。")
    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 290, f"御請求金額 {data['total_amount']:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 305, "(上記金額は消費税を含みます。)")

    # --- 明細テーブルの枠組み ---
    y = height - 340
    c.line(50, y, 550, y) # Top line
    c.drawString(60, y - 15, "品目")
    c.drawString(250, y - 15, "数量")
    c.drawString(350, y - 15, "単価")
    c.drawString(450, y - 15, "金額")
    c.line(50, y - 20, 550, y - 20)
    
    # 明細内容
    c.drawString(60, y - 35, data['item_name'])
    c.drawString(250, y - 35, data['item_quantity'])
    c.drawString(350, y - 35, f"{data['item_unit_price']:,}円")
    c.drawString(450, y - 35, f"{data['subtotal']:,}円")
    c.line(50, y - 45, 550, y - 45)

    # --- 合計欄 ---
    y_summary = y - 100
    c.drawString(350, y_summary, "小計")
    c.drawString(450, y_summary, f"{data['subtotal']:,}円")
    c.drawString(350, y_summary - 15, "消費税(10%)")
    c.drawString(450, y_summary - 15, f"{data['tax']:,}円")
    c.drawString(350, y_summary - 30, "総計")
    c.drawString(450, y_summary - 30, f"{data['total_amount']:,}円")

    # --- 振込先情報 ---
    y_bank = y_summary - 80
    c.drawString(50, y_bank, "下記の通りお振込下さいますようお願い致します。")
    c.drawString(50, y_bank - 20, f"支払期日 ：{data['due_date']}")
    c.drawString(50, y_bank - 35, f"振込先 ：{data['bank_info']}")
    c.drawString(50, y_bank - 50, "振込手数料：振込手数料は御社にて負担ください")
    c.drawString(105, y_bank - 65, "ますようお願いいたします。")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- Streamlit UI 構造 ---
st.title("請求書作成アプリ")

# 全ての入力欄をひとつのフォーム内に収めます
with st.form("invoice_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("発行者情報")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        issuer_zip = st.text_input("発行者郵便番号", value="204-0023")
        issuer_address = st.text_input("発行者住所", value="東京都清瀬市竹丘2-33-23")
        
    with col2:
        st.subheader("取引先情報")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        client_zip = st.text_input("取引先郵便番号", value="150-0043")
        client_address1 = st.text_input("取引先住所1", value="東京都渋谷区道玄坂1-21-1")
        client_address2 = st.text_input("取引先住所2", value="SHIBUYA SOLASTA 3F")

    st.subheader("明細情報")
    item_name = st.text_input("品目", value="請負成果物一式(イラスト)")
    item_unit_price = st.number_input("単価", value=20000)
    item_quantity = st.text_input("数量", value="1式")
    
    date = st.date_input("発行年月日", value=datetime(2025, 12, 15))
    due_date = st.date_input("支払期日", value=datetime(2026, 1, 31))
    bank_info = st.text_input("振込先", value="みずほ銀行清瀬支店 普通 1228611")

    # フォームを完了させるボタン
    submitted = st.form_submit_button("PDFを作成")

# ボタンが押されたときのみ、変数を処理してPDFを作成する
if submitted:
    subtotal = item_unit_price
    tax = int(subtotal * 0.1)
    total_amount = subtotal + tax

    data_to_pdf = {
        'issuer_name': issuer_name, 'issuer_zip': issuer_zip, 'issuer_address': issuer_address,
        'client_name': client_name, 'client_zip': client_zip, 
        'client_address1': client_address1, 'client_address2': client_address2,
        'date': date.strftime('%Y年%m月%d日'),
        'item_name': item_name, 'item_quantity': item_quantity, 'item_unit_price': item_unit_price,
        'subtotal': subtotal, 'tax': tax, 'total_amount': total_amount,
        'due_date': due_date.strftime('%Y年%m月%d日'),
        'bank_info': bank_info
    }

    try:
        pdf_file = create_invoice_pdf(data_to_pdf)
        st.success("PDFが正常に生成されました。")
        st.download_button(
            label="PDFをダウンロード",
            data=pdf_file,
            file_name=f"請求書_{client_name}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"PDF作成中にエラーが発生しました: {e}")
