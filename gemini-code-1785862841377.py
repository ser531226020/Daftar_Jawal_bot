import os
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# 1. تهيئة الاتصال بـ Firebase
if not firebase_admin._apps:
  cred = credentials.Certificate("serviceAccountKey.json")
  firebase_admin.initialize_app(cred)

db = firestore.client()

excel_file = "المحاسب.xlsx"
xls = pd.ExcelFile(excel_file)

total_uploaded = 0

print("🚀 جاري بدء رفع البيانات من ملف الإكسل إلى Firebase...")

# المرور على كل الشيتات (الأوراق) في ملف الإكسل
for sheet_name in xls.sheet_names:
  # تخطي شيتات الملخص أو غير المطابقة إذا وجدت (مثل Mirror-2026 إذا لم يكن بيانات حركات يومية)
  if sheet_name == "Mirror-2026":
    continue

  print(f"📁 جاري معالجة الورقة (Sheet): {sheet_name}...")
  df = pd.read_excel(excel_file, sheet_name=sheet_name)

  # تنظيف أسماء الأعمدة (إزالة الفراغات الزائدة)
  df.columns = df.columns.str.strip()

  # التأكد من وجود الأعمدة الأساسية
  required_cols = ["التاريخ", "المبلغ", "النوع"]
  # التعامل مع اختلاف تسميات الأعمدة البسيط
  col_mapping = {}
  for col in df.columns:
    if "تاريخ" in col:
      col_mapping[col] = "التاريخ"
    elif "مبلغ" in col:
      col_mapping[col] = "المبلغ"
    elif "نوع" in col:
      col_mapping[col] = "النوع"
    elif "بيان" in col:
      col_mapping[col] = "البيان"
    elif "اليوم" in col:
      col_mapping[col] = "اليوم"

  df = df.rename(columns=col_mapping)

  if not all(col in df.columns for col in ["التاريخ", "المبلغ", "النوع"]):
    print(f"⚠️ تخطي الورقة {sheet_name} لعدم مطابقة الأعمدة الأساسية.")
    continue

  for index, row in df.iterrows():
    date_raw = row["التاريخ"]
    if pd.isna(date_raw):
      continue

    # تحويل التاريخ إلى صيغة نصية YYYY-MM-DD
    try:
      date_str = str(pd.to_datetime(date_raw)).split(" ")[0]
      year_val = int(date_str.split("-")[0])
      month_val = int(date_str.split("-")[1])
    except Exception:
      continue

    # تنظيف المبلغ (تجنب القيم الفارغة أو غير الرقمية)
    try:
      amount_val = float(row["المبلغ"])
      if pd.isna(amount_val):
        amount_val = 0.0
    except Exception:
      amount_val = 0.0

    # تنظيف البيان والنوع
    desc_val = (
        str(row["البيان"])
        if ("البيان" in df.columns and not pd.isna(row["البيان"]))
        else ""
    )
    type_val = (
        str(row["النوع"]).strip() if not pd.isna(row["النوع"]) else "إيراد"
    )

    transaction_data = {
        "date": date_str,
        "type": type_val,
        "amount": amount_val,
        "description": desc_val,
        "year": year_val,
        "month": month_val,
        "sheet_source": sheet_name,
    }

    # رفع السجل إلى مجموعة transactions في Firestore
    db.collection("transactions").add(transaction_data)
    total_uploaded += 1

print(
    f"\n✅ تم بنجاح رفع جميع البيانات التاريخية ({total_uploaded} حركة مالية) إلى"
    " قاعدة بيانات Firebase Firestore!"
)